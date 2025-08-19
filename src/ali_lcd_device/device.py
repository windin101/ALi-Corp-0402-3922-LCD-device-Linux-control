#!/usr/bin/env python3
"""
Main device implementation for ALi LCD device.
"""

import usb.core
import usb.util
import time
import threading
import logging
import os

from .lifecycle import DeviceLifecycleState, TagMonitor, LifecycleManager
from .usb_comm import (
    create_cbw, parse_csw, RobustUSBSession, 
    USBError, TagMismatchError, PipeError, DeviceNotFoundError
)
from .commands import (
    create_test_unit_ready, create_inquiry, create_request_sense,
    create_f5_init_command, create_f5_animation_command, 
    create_f5_set_mode_command, create_f5_clear_screen_command,
    create_f5_display_image_command, create_image_header
)
from .image_utils import convert_image_to_rgb565

logger = logging.getLogger(__name__)

class ALiLCDDevice:
    """
    Main class for controlling the ALi LCD device.
    
    This class provides high-level methods for initializing the device,
    controlling its state, and displaying images.
    """
    
    def __init__(self, vendor_id=0x0402, product_id=0x3922):
        """
        Initialize the ALi LCD device.
        
        Args:
            vendor_id (int): USB vendor ID (default: 0x0402 for ALi)
            product_id (int): USB product ID (default: 0x3922)
        """
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.device = None
        self.ep_out = None
        self.ep_in = None
        self.interface = None
        self.tag_monitor = TagMonitor()
        self.lifecycle_manager = None
        self.session = RobustUSBSession()
        self.lock = threading.Lock()
        self.initialized = False
        self.display_initialized = False
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    @property
    def lifecycle_state(self):
        """Get the current lifecycle state."""
        if self.lifecycle_manager:
            return self.lifecycle_manager.get_state()
        return DeviceLifecycleState.UNKNOWN
    
    @lifecycle_state.setter
    def lifecycle_state(self, state):
        """Set the lifecycle state."""
        if self.lifecycle_manager:
            self.lifecycle_manager.set_state(state)
    
    def connect(self, wait_for_stable=False):
        """
        Connect to the ALi LCD device.
        
        Args:
            wait_for_stable (bool): If True, wait for the device to reach the
                Connected state before returning
                
        Returns:
            bool: True if connection was successful
            
        Raises:
            DeviceNotFoundError: If the device could not be found
        """
        try:
            logger.info("Connecting to ALi LCD device (0x%04x:0x%04x)",
                      self.vendor_id, self.product_id)
            
            # Find the device
            self.device = usb.core.find(idVendor=self.vendor_id, 
                                        idProduct=self.product_id)
            
            if self.device is None:
                raise DeviceNotFoundError("ALi LCD device not found")
            
            # Set configuration
            try:
                self.device.set_configuration()
            except usb.core.USBError:
                # Device may already be configured
                pass
            
            # Get the first configuration
            cfg = self.device.get_active_configuration()
            
            # Get the interface
            self.interface = cfg[(0, 0)]
            
            # Check for kernel driver
            if self.device.is_kernel_driver_active(self.interface.bInterfaceNumber):
                logger.debug("Detaching kernel driver")
                try:
                    self.device.detach_kernel_driver(self.interface.bInterfaceNumber)
                except usb.core.USBError as e:
                    if "busy" in str(e).lower():
                        logger.error("Device is busy - another application may be using it")
                        logger.error("Try closing other applications or unplugging and reconnecting the device")
                        raise USBError("Device is busy - another application may be using it") from e
                    else:
                        raise
            
            # Claim the interface
            try:
                usb.util.claim_interface(self.device, self.interface.bInterfaceNumber)
            except usb.core.USBError as e:
                if "busy" in str(e).lower():
                    logger.error("Failed to claim interface - device is busy")
                    logger.error("Try closing other applications or unplugging and reconnecting the device")
                    raise USBError("Failed to claim interface - device is busy") from e
                else:
                    raise
            
            # Find the endpoints
            for ep in self.interface:
                if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
                    self.ep_out = ep
                elif usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
                    self.ep_in = ep
            
            if self.ep_out is None or self.ep_in is None:
                raise USBError("Could not find required endpoints")
            
            # Initialize tag monitor and lifecycle manager
            self.tag_monitor.reset()
            self.lifecycle_manager = LifecycleManager(self)
            self.lifecycle_manager.start_monitoring()
            
            # Mark as initialized
            self.initialized = True
            self.display_initialized = False
            
            logger.info("Successfully connected to ALi LCD device")
            
            # Wait for stable connection if requested
            if wait_for_stable:
                logger.info("Waiting for stable connection (60s)...")
                self._wait_for_connected_state()
            
            return True
            
        except Exception as e:
            logger.error("Error connecting to device: %s", str(e))
            self.close()
            raise
    
    def close(self):
        """Close the connection to the device and release resources."""
        logger.info("Closing ALi LCD device connection")
        
        if self.lifecycle_manager:
            try:
                self.lifecycle_manager.stop_monitoring()
            except Exception as e:
                logger.debug(f"Error stopping lifecycle manager: {e}")
            self.lifecycle_manager = None
        
        if self.device and self.interface:
            try:
                # First release the interface
                usb.util.release_interface(self.device, self.interface.bInterfaceNumber)
                logger.debug("Released USB interface")
                
                # Then reattach the kernel driver if needed
                try:
                    self.device.attach_kernel_driver(self.interface.bInterfaceNumber)
                    logger.debug("Reattached kernel driver")
                except (usb.core.USBError, AttributeError):
                    # Not all devices support reattaching or need it
                    pass
                    
            except Exception as e:
                logger.debug(f"Error releasing interface: {e}")
                # Continue with cleanup despite errors
        
        # Explicitly release device resources
        if self.device:
            try:
                usb.util.dispose_resources(self.device)
                logger.debug("Disposed USB device resources")
            except Exception as e:
                logger.debug(f"Error disposing USB resources: {e}")
        
        # Clear all references
        self.ep_in = None
        self.ep_out = None
        self.interface = None
        self.device = None
        self.initialized = False
        self.display_initialized = False
        
        logger.info("Connection closed and resources released")
        self.interface = None
        self.initialized = False
        self.display_initialized = False
    
    def _send_command(self, command, data_length=0, direction='none', 
                     data_out=None, check_tag=True, lun=0):
        """
        Send a SCSI command to the device.
        
        Args:
            command (bytes): SCSI command bytes
            data_length (int): Expected data transfer length
            direction (str): Data direction ('in', 'out', or 'none')
            data_out (bytes): Data to send (for 'out' direction)
            check_tag (bool): Whether to validate the returned tag
            lun (int): Logical Unit Number
            
        Returns:
            tuple: (success, tag_mismatch, data_in)
                success (bool): True if command succeeded
                tag_mismatch (bool): True if tag mismatched
                data_in (bytes): Data received (for 'in' direction)
                
        Raises:
            USBError: If a USB error occurs
        """
        if not self.initialized:
            raise USBError("Device not initialized")
        
        with self.lock:
            # Get the next tag
            tag = self.tag_monitor.get_next_tag()
            
            # Create CBW
            cbw = create_cbw(tag, data_length, direction, lun, command)
            
            # Send CBW
            logger.debug("Sending CBW (tag=%d, cmd=0x%02x)", tag, command[0])
            try:
                self.session.with_retry(self.device.write, self.ep_out, cbw)
            except USBError as e:
                # If in Animation state, handle errors more gracefully
                if self.lifecycle_state == DeviceLifecycleState.ANIMATION:
                    logger.debug("USB error sending CBW in Animation state: %s", str(e))
                    # Record command in lifecycle manager despite error
                    if self.lifecycle_manager:
                        self.lifecycle_manager.record_command()
                    return False, False, None
                else:
                    raise
            
            # Data phase (if applicable)
            data_in = None
            
            if direction.lower() == 'out' and data_out:
                try:
                    logger.debug("Sending data (%d bytes)", len(data_out))
                    self.session.with_retry(self.device.write, self.ep_out, data_out)
                except USBError as e:
                    # In Animation state, data errors are common
                    if self.lifecycle_state == DeviceLifecycleState.ANIMATION:
                        logger.debug("USB error sending data in Animation state: %s", str(e))
                        if self.lifecycle_manager:
                            self.lifecycle_manager.record_command()
                        return False, False, None
                    else:
                        raise
                    
            elif direction.lower() == 'in':
                try:
                    logger.debug("Reading data (%d bytes)", data_length)
                    data_in = self.session.with_retry(
                        self.device.read, self.ep_in, data_length)
                except Exception as e:
                    logger.warning("Error reading data: %s", str(e))
                    # In Animation state, continue to status phase even if data phase failed
                    if self.lifecycle_state != DeviceLifecycleState.ANIMATION:
                        # For other states, re-raise the exception
                        raise
            
            # Status phase (read CSW)
            try:
                logger.debug("Reading CSW")
                csw_data = self.session.with_retry(self.device.read, self.ep_in, 13)
                
                # Parse CSW
                csw_signature, csw_tag, csw_data_residue, csw_status = parse_csw(csw_data)
                
                # Check tag if requested
                tag_mismatch = csw_tag != tag
                if tag_mismatch:
                    logger.debug("Tag mismatch: expected %d, got %d", tag, csw_tag)
                    
                    # Detect tag reset
                    self.tag_monitor.detect_tag_reset(csw_tag)
                    
                    # Validate based on lifecycle state
                    if check_tag and not self.tag_monitor.validate_tag(
                            tag, csw_tag, self.lifecycle_state):
                        raise TagMismatchError(
                            f"Tag mismatch: expected {tag}, got {csw_tag}")
                
                # Check command status
                success = csw_status == 0
                if not success:
                    # In Animation state, command failures are common and expected
                    if self.lifecycle_state == DeviceLifecycleState.ANIMATION:
                        logger.debug("Command failed with status %d in Animation state", csw_status)
                    else:
                        logger.warning("Command failed with status %d", csw_status)
                
                # Record command in lifecycle manager
                if self.lifecycle_manager:
                    self.lifecycle_manager.record_command()
                
                # Apply command delay based on state
                if self.lifecycle_manager:
                    time.sleep(self.lifecycle_manager.get_command_delay())
                
                return success, tag_mismatch, data_in
                
            except Exception as e:
                # In Animation state, CSW errors are common
                if self.lifecycle_state == DeviceLifecycleState.ANIMATION:
                    logger.debug("Error in status phase during Animation state: %s", str(e))
                    # Record command attempt despite error
                    if self.lifecycle_manager:
                        self.lifecycle_manager.record_command()
                    return False, False, None
                else:
                    logger.error("Error in status phase: %s", str(e))
                    raise
    
    def _test_unit_ready(self):
        """
        Send a TEST UNIT READY command.
        
        Returns:
            tuple: (success, tag_mismatch)
        """
        cmd, data_length, direction = create_test_unit_ready()
        success, tag_mismatch, _ = self._send_command(cmd, data_length, direction)
        
        # In Animation state, command failures are expected and should be ignored
        if not success and self.lifecycle_state == DeviceLifecycleState.ANIMATION:
            logger.debug("TEST UNIT READY command failed in Animation state (expected)")
            # Return success=True when in Animation state to continue the connection process
            return True, tag_mismatch
            
        return success, tag_mismatch
    
    def _inquiry(self):
        """
        Send an INQUIRY command.
        
        Returns:
            tuple: (success, tag_mismatch, inquiry_data)
        """
        cmd, data_length, direction = create_inquiry()
        return self._send_command(cmd, data_length, direction)
    
    def _request_sense(self):
        """
        Send a REQUEST SENSE command.
        
        Returns:
            tuple: (success, tag_mismatch, sense_data)
        """
        cmd, data_length, direction = create_request_sense()
        return self._send_command(cmd, data_length, direction)
    
    def _wait_for_connected_state(self, timeout=70):
        """
        Wait for the device to reach the Connected state.
        
        Args:
            timeout (int): Maximum time to wait (seconds)
            
        Returns:
            bool: True if Connected state was reached
        """
        logger.info("Waiting for device to reach Connected state...")
        start_time = time.time()
        command_count = 0
        success_count = 0
        last_state_log = start_time
        
        while time.time() - start_time < timeout:
            # Send TEST UNIT READY command
            try:
                success, _ = self._test_unit_ready()
                command_count += 1
                
                if success:
                    success_count += 1
                
                # Log state periodically
                current_time = time.time()
                if current_time - last_state_log > 5.0:  # Log every 5 seconds
                    elapsed = current_time - start_time
                    logger.info("State: %s, Commands: %d, Success rate: %.1f%%, Elapsed: %.1fs",
                               self.lifecycle_state, command_count,
                               (success_count / command_count * 100) if command_count else 0,
                               elapsed)
                    last_state_log = current_time
                
                # Check if we've transitioned to Connected state
                if self.lifecycle_state == DeviceLifecycleState.CONNECTED:
                    logger.info("Device reached Connected state after %.1f seconds",
                              time.time() - start_time)
                    return True
                
                # Adaptive sleep based on state
                if self.lifecycle_state == DeviceLifecycleState.ANIMATION:
                    time.sleep(0.2)
                else:
                    time.sleep(0.1)
                    
            except Exception as e:
                # Log error but continue trying
                logger.warning("Error during connection wait: %s", str(e))
                time.sleep(0.5)  # Wait a bit longer after an error
        
        logger.warning("Timeout waiting for Connected state")
        return False
    
    def initialize_display(self):
        """
        Initialize the display.
        
        Returns:
            bool: True if initialization was successful
        """
        if not self.initialized:
            raise USBError("Device not initialized")
        
        # Wait for Connected state if not already
        if self.lifecycle_state != DeviceLifecycleState.CONNECTED:
            logger.info("Waiting for Connected state before initializing display")
            if not self._wait_for_connected_state():
                logger.warning("Could not reach Connected state, attempting anyway")
        
        try:
            logger.info("Initializing display")
            
            # Send F5 init command
            cmd, data_length, direction = create_f5_init_command()
            success, _, _ = self._send_command(cmd, data_length, direction)
            
            if not success:
                logger.warning("F5 init command failed")
                return False
            
            # Set display mode
            cmd, data_length, direction, data = create_f5_set_mode_command(mode=5)
            success, _, _ = self._send_command(cmd, data_length, direction, data)
            
            if not success:
                logger.warning("Set mode command failed")
                return False
            
            # Stop animation
            cmd, data_length, direction, data = create_f5_animation_command(False)
            success, _, _ = self._send_command(cmd, data_length, direction, data)
            
            if not success:
                logger.warning("Animation control command failed")
                return False
            
            # Clear screen
            cmd, data_length, direction = create_f5_clear_screen_command()
            success, _, _ = self._send_command(cmd, data_length, direction)
            
            if not success:
                logger.warning("Clear screen command failed")
                return False
            
            # Mark display as initialized
            self.display_initialized = True
            logger.info("Display initialized successfully")
            
            return True
            
        except Exception as e:
            logger.error("Error initializing display: %s", str(e))
            return False
    
    def display_image(self, image_path, x=0, y=0, resize=None):
        """
        Display an image on the LCD.
        
        Args:
            image_path (str): Path to the image file
            x (int): X coordinate to start displaying
            y (int): Y coordinate to start displaying
            resize (tuple, optional): (width, height) to resize the image
            
        Returns:
            bool: True if successful
        """
        if not self.initialized:
            raise USBError("Device not initialized")
        
        # Initialize display if not already
        if not self.display_initialized:
            logger.info("Display not initialized, initializing...")
            if not self.initialize_display():
                logger.error("Failed to initialize display")
                return False
        
        try:
            # Convert image to RGB565
            logger.info("Converting image to RGB565 format")
            image_data, width, height = convert_image_to_rgb565(image_path, resize)
            
            # Create image header
            header = create_image_header(width, height, x, y)
            
            # Combine header and image data
            data = header + image_data
            
            # Send display image command
            logger.info("Sending display image command (%dx%d at %d,%d)", 
                      width, height, x, y)
            cmd, data_length, direction = create_f5_display_image_command(
                width, height, x, y)
            
            success, _, _ = self._send_command(cmd, len(data), direction, data)
            
            if not success:
                logger.warning("Display image command failed")
                return False
            
            logger.info("Image displayed successfully")
            return True
            
        except Exception as e:
            logger.error("Error displaying image: %s", str(e))
            return False
    
    def clear_screen(self):
        """
        Clear the display.
        
        Returns:
            bool: True if successful
        """
        if not self.initialized:
            raise USBError("Device not initialized")
        
        try:
            logger.info("Clearing screen")
            cmd, data_length, direction = create_f5_clear_screen_command()
            success, _, _ = self._send_command(cmd, data_length, direction)
            
            return success
            
        except Exception as e:
            logger.error("Error clearing screen: %s", str(e))
            return False
    
    def control_animation(self, start_animation):
        """
        Control the built-in animation.
        
        Args:
            start_animation (bool): True to start animation, False to stop
            
        Returns:
            bool: True if successful
        """
        if not self.initialized:
            raise USBError("Device not initialized")
        
        try:
            logger.info("%s animation", "Starting" if start_animation else "Stopping")
            cmd, data_length, direction, data = create_f5_animation_command(start_animation)
            success, _, _ = self._send_command(cmd, data_length, direction, data)
            
            return success
            
        except Exception as e:
            logger.error("Error controlling animation: %s", str(e))
            return False
    
    def set_display_mode(self, mode=5):
        """
        Set the display mode.
        
        Args:
            mode (int): The mode value (typically 5)
            
        Returns:
            bool: True if successful
        """
        if not self.initialized:
            raise USBError("Device not initialized")
        
        try:
            logger.info("Setting display mode to %d", mode)
            cmd, data_length, direction, data = create_f5_set_mode_command(mode)
            success, _, _ = self._send_command(cmd, data_length, direction, data)
            
            return success
            
        except Exception as e:
            logger.error("Error setting display mode: %s", str(e))
            return False
