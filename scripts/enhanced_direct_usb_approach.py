#!/usr/bin/env python3
"""
ALi LCD Device - Enhanced Direct Low Level USB Approach

This script uses a low-level approach directly with pyusb to communicate with the device,
avoiding the SCSI/Mass Storage protocol entirely. This version includes enhanced timing,
more robust error handling, and a longer initialization sequence to improve stability.
"""

import os
import sys
import time
import struct
import argparse
import logging
import usb.core
import usb.util
import usb.backend.libusb1
from collections import deque

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Constants
VENDOR_ID = 0x0402
PRODUCT_ID = 0x3922
EP_OUT = 0x02
EP_IN = 0x81

class EnhancedDirectUSBApproach:
    def __init__(self, frames_dir=None, verbose=False, stabilization_time=30):
        """Initialize the class with optional frame directory."""
        self.device = None
        self.frames_dir = frames_dir
        self.frames = []
        self.verbose = verbose
        self.backend = usb.backend.libusb1.get_backend()
        self.stabilization_time = stabilization_time
        self.tag_history = deque(maxlen=10)
        self.current_tag = 1
        
        if frames_dir and os.path.exists(frames_dir):
            self.load_frames(frames_dir)
    
    def log(self, message, level=logging.INFO):
        """Log message with appropriate level."""
        if level == logging.DEBUG and not self.verbose:
            return
        
        logger.log(level, message)
    
    def load_frames(self, directory):
        """Load binary frames from the specified directory."""
        self.log(f"Loading frames from {directory}")
        files = [f for f in os.listdir(directory) if f.endswith('.bin')]
        files.sort()  # Sort to ensure consistent order
        
        for file in files:
            filepath = os.path.join(directory, file)
            size = os.path.getsize(filepath)
            self.log(f"Found frame: {file} ({size} bytes)")
            self.frames.append(filepath)
    
    def connect(self):
        """Connect to the ALi LCD device with enhanced USB settings."""
        # Set libusb options for more robust connection
        os.environ['LIBUSB_DEBUG'] = '3' if self.verbose else '0'
        
        # Try multiple times to establish a stable connection
        for attempt in range(3):
            try:
                self.log(f"Connection attempt {attempt+1}/3...")
                
                # Find the device
                self.log("Searching for ALi LCD device...")
                self.device = usb.core.find(
                    backend=self.backend,
                    idVendor=VENDOR_ID, 
                    idProduct=PRODUCT_ID
                )
                
                if self.device is None:
                    self.log("Device not found", logging.ERROR)
                    time.sleep(2)
                    continue
                
                self.log(f"Device found: {self.device}")
                
                # More careful reset process
                self.log("Performing controlled device reset...")
                try:
                    # Clear endpoints first
                    try:
                        self.device.clear_halt(EP_IN)
                        self.device.clear_halt(EP_OUT)
                    except:
                        pass
                    time.sleep(1)
                    
                    # Then reset
                    self.device.reset()
                    time.sleep(3)  # Longer delay after reset
                    
                    # Find the device again after reset
                    self.device = usb.core.find(
                        backend=self.backend,
                        idVendor=VENDOR_ID, 
                        idProduct=PRODUCT_ID
                    )
                    
                    if self.device is None:
                        self.log("Device disappeared after reset, retrying...", logging.WARNING)
                        time.sleep(3)
                        continue
                        
                except usb.core.USBError as e:
                    self.log(f"Reset warning (non-fatal): {e}", logging.WARNING)
                
                # Detach kernel driver if active
                for config in self.device:
                    for interface in range(config.bNumInterfaces):
                        if self.device.is_kernel_driver_active(interface):
                            self.log(f"Detaching kernel driver from interface {interface}")
                            try:
                                self.device.detach_kernel_driver(interface)
                            except usb.core.USBError as e:
                                self.log(f"Warning: Failed to detach kernel driver: {e}", logging.WARNING)
                
                # Set configuration with careful error handling
                try:
                    self.log("Setting device configuration...")
                    self.device.set_configuration()
                    time.sleep(1)  # Give device more time to configure
                except usb.core.USBError as e:
                    self.log(f"Warning: Failed to set configuration: {e}", logging.WARNING)
                    # Try explicit configuration
                    try:
                        self.device.set_configuration(1)
                        time.sleep(1)
                    except:
                        self.log("Failed to set explicit configuration", logging.WARNING)
                
                # Get active configuration
                try:
                    cfg = self.device.get_active_configuration()
                except usb.core.USBError as e:
                    self.log(f"Warning: Failed to get active configuration: {e}", logging.WARNING)
                    # Try to set configuration 1 explicitly
                    try:
                        self.device.set_configuration(1)
                        time.sleep(1)
                        cfg = self.device.get_active_configuration()
                    except:
                        self.log("Failed to set explicit configuration", logging.WARNING)
                        # Continue anyway - we'll try with default interface
                        cfg = None
                
                # Find the interface we need
                if cfg:
                    try:
                        interface = cfg[(0,0)]
                        
                        # Claim the interface
                        try:
                            usb.util.claim_interface(self.device, interface.bInterfaceNumber)
                            time.sleep(0.5)
                        except usb.core.USBError as e:
                            self.log(f"Warning: Failed to claim interface: {e}", logging.WARNING)
                            # Try to force claim the interface
                            try:
                                self.device._ctx.managed_claim_interface(interface.bInterfaceNumber)
                            except:
                                self.log("Failed to force claim interface", logging.WARNING)
                    except:
                        self.log("Failed to get interface, using default interface 0", logging.WARNING)
                else:
                    self.log("No active configuration, trying to claim interface 0", logging.WARNING)
                
                # Clear any stall conditions
                try:
                    self.device.clear_halt(EP_OUT)
                    self.device.clear_halt(EP_IN)
                except:
                    self.log("Warning: Failed to clear endpoint halts", logging.WARNING)
                
                # Verify connection
                try:
                    self.log("Verifying USB connection...")
                    test_data = bytes([0x00] * 8)
                    self.device.write(EP_OUT, test_data, timeout=1000)
                    self.log("Connection verified successfully")
                except usb.core.USBError as e:
                    self.log(f"Connection verification failed: {e}", logging.WARNING)
                    if "No such device" in str(e):
                        self.log("Device disappeared during verification, retrying...", logging.WARNING)
                        time.sleep(3)
                        continue
                
                self.log("Device connected successfully")
                return True
                    
            except usb.core.USBError as e:
                self.log(f"USB Error during connect attempt {attempt+1}: {e}", logging.ERROR)
                # If device is gone, wait and retry
                if "No such device" in str(e):
                    self.log("Device disconnected, waiting before retry...", logging.WARNING)
                    time.sleep(3)
                # For other errors, try to clean up before retry
                else:
                    try:
                        if self.device:
                            usb.util.dispose_resources(self.device)
                    except:
                        pass
                    time.sleep(2)
                self.device = None
                
            except Exception as e:
                self.log(f"Unexpected error during connect attempt {attempt+1}: {e}", logging.ERROR)
                try:
                    if self.device:
                        usb.util.dispose_resources(self.device)
                except:
                    pass
                self.device = None
                time.sleep(2)
        
        self.log("Failed to establish a stable connection after 3 attempts", logging.ERROR)
        return False
    
    def direct_write(self, data, timeout=5000, retries=5):
        """Write data directly to the device with enhanced error handling."""
        if self.device is None:
            self.log("Error: Device not connected", logging.ERROR)
            return False
        
        attempt = 0
        while attempt < retries:
            try:
                self.log(f"Writing {len(data)} bytes directly to EP_OUT", logging.DEBUG)
                bytes_written = self.device.write(EP_OUT, data, timeout=timeout)
                self.log(f"Successfully wrote {bytes_written} bytes", logging.DEBUG)
                return True
            except usb.core.USBError as e:
                self.log(f"USB Error on write attempt {attempt+1}/{retries}: {e}", logging.WARNING)
                
                # Handle pipe errors
                if "Pipe error" in str(e):
                    self.log("Clearing endpoint halts and waiting before retry", logging.DEBUG)
                    try:
                        self.device.clear_halt(EP_OUT)
                        self.device.clear_halt(EP_IN)
                    except:
                        self.log("Failed to clear halts", logging.DEBUG)
                    time.sleep(2)  # Longer wait after pipe error
                
                # Check if device is still connected
                if "No such device" in str(e):
                    self.log("Device disconnected", logging.WARNING)
                    self.device = None
                    return False
                
                attempt += 1
                time.sleep(attempt * 0.5)  # Exponential backoff
            
            except Exception as e:
                self.log(f"Unexpected error: {e}", logging.ERROR)
                attempt += 1
                time.sleep(attempt * 0.5)
        
        return False
    
    def direct_read(self, length, timeout=5000, retries=5):
        """Read data directly from the device with enhanced error handling."""
        if self.device is None:
            self.log("Error: Device not connected", logging.ERROR)
            return None
        
        attempt = 0
        while attempt < retries:
            try:
                self.log(f"Reading {length} bytes directly from EP_IN", logging.DEBUG)
                data = self.device.read(EP_IN, length, timeout=timeout)
                self.log(f"Successfully read {len(data)} bytes", logging.DEBUG)
                return data
            except usb.core.USBError as e:
                self.log(f"USB Error on read attempt {attempt+1}/{retries}: {e}", logging.WARNING)
                
                # Handle pipe errors
                if "Pipe error" in str(e):
                    self.log("Clearing endpoint halts and waiting before retry", logging.DEBUG)
                    try:
                        self.device.clear_halt(EP_IN)
                        self.device.clear_halt(EP_OUT)
                    except:
                        self.log("Failed to clear halts", logging.DEBUG)
                    time.sleep(2)  # Longer wait after pipe error
                
                # Handle timeouts
                if "Operation timed out" in str(e):
                    self.log("Read timed out, may be normal for some commands", logging.DEBUG)
                    # For timeouts, try returning an empty array instead of None
                    if attempt == retries - 1:
                        return bytes([])
                
                # Check if device is still connected
                if "No such device" in str(e):
                    self.log("Device disconnected", logging.WARNING)
                    self.device = None
                    return None
                
                attempt += 1
                time.sleep(attempt * 0.5)  # Exponential backoff
            
            except Exception as e:
                self.log(f"Unexpected error: {e}", logging.ERROR)
                attempt += 1
                time.sleep(attempt * 0.5)
        
        return None

    def send_test_unit_ready(self, tag=None):
        """Send a TEST UNIT READY command to help stabilize the device."""
        if tag is None:
            tag = self.current_tag
            self.current_tag = (self.current_tag + 1) % 65536
        
        cmd = bytes([
            0x55, 0x53, 0x42, 0x43,                                  # USBC signature
            tag & 0xFF, (tag >> 8) & 0xFF, 0x00, 0x00,               # Tag
            0x00, 0x00, 0x00, 0x00,                                  # Data length
            0x00,                                                     # Flags (direction out)
            0x00,                                                     # LUN
            0x06,                                                     # Command length
            0x00,                                                     # Reserved
            # Command data (TEST UNIT READY)
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            # Padding to 31 bytes
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        ])
        
        success = self.direct_write(cmd)
        if success:
            # Try to read CSW with shorter timeout
            csw = self.direct_read(13, timeout=1000)
            if csw:
                self.log(f"TEST UNIT READY Response: {' '.join([f'{b:02X}' for b in csw])}", logging.DEBUG)
                self.tag_history.append(tag)
                # Return status (last byte)
                return csw[-1] == 0
        
        return False

    def stabilize_device(self):
        """Send a series of commands to stabilize the device state."""
        self.log(f"Beginning device stabilization phase ({self.stabilization_time} seconds)...")
        
        start_time = time.time()
        command_count = 0
        success_count = 0
        
        # Send TEST UNIT READY commands for the specified time
        while time.time() - start_time < self.stabilization_time:
            if self.device is None:
                self.log("Device disconnected during stabilization", logging.ERROR)
                return False
            
            result = self.send_test_unit_ready()
            command_count += 1
            
            if result:
                success_count += 1
            
            # Variable delay based on elapsed time
            elapsed = time.time() - start_time
            if elapsed < 20:
                # Slower in the beginning (Animation state)
                time.sleep(0.5)
            elif elapsed < 40:
                # Medium pace in the middle (transition phase)
                time.sleep(0.3)
            else:
                # Faster near the end (approaching Connected state)
                time.sleep(0.2)
            
            # Progress indicator every 10 commands
            if command_count % 10 == 0:
                elapsed = time.time() - start_time
                remaining = max(0, self.stabilization_time - elapsed)
                self.log(f"Stabilization progress: {elapsed:.1f}s elapsed, {remaining:.1f}s remaining, {success_count}/{command_count} successful")
        
        success_rate = (success_count / command_count) * 100 if command_count > 0 else 0
        self.log(f"Stabilization complete: {command_count} commands sent, {success_rate:.1f}% success rate")
        
        # Additional verification that we've reached a stable state
        time.sleep(2)
        verify_success = 0
        for i in range(5):
            if self.send_test_unit_ready():
                verify_success += 1
            time.sleep(0.5)
        
        if verify_success >= 3:
            self.log("Device appears to be in a stable state")
            return True
        else:
            self.log("Device may not be in a fully stable state yet", logging.WARNING)
            return False
    
    def send_init_sequence(self):
        """Send an enhanced initialization sequence directly over USB."""
        if not self.device:
            self.log("Cannot send init sequence - device not connected", logging.ERROR)
            return False
        
        self.log("Starting device stabilization...")
        if not self.stabilize_device():
            self.log("Device stabilization incomplete, continuing anyway", logging.WARNING)
        
        self.log("Sending enhanced initialization sequence...")
        
        # Send F5 01 command directly (Initialize Display)
        try:
            self.log("Sending direct F5 01 command (Initialize Display)...")
            init_cmd = bytes([
                0x55, 0x53, 0x42, 0x43,  # USBC signature
                0x01, 0x00, 0x00, 0x00,  # Tag
                0x00, 0x00, 0x00, 0x00,  # Data length
                0x00,                    # Flags (direction out)
                0x00,                    # LUN
                0x0C,                    # Command length
                0x00,                    # Reserved
                # Command data
                0xF5, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                # Padding to 31 bytes
                0x00, 0x00, 0x00, 0x00
            ])
            
            if not self.direct_write(init_cmd):
                self.log("Failed to send F5 01 command", logging.WARNING)
                return False
            
            # Try to read CSW with longer timeout
            time.sleep(2)
            csw = self.direct_read(13, timeout=3000)
            if csw:
                self.log(f"Got CSW response: {' '.join([f'{b:02X}' for b in csw])}")
                # Check status code
                if csw[-1] != 0:
                    self.log(f"Warning: F5 01 command failed with status {csw[-1]}", logging.WARNING)
            else:
                self.log("No CSW response (might be normal)")
            
            # Longer wait between commands
            time.sleep(5)
            
            # Verify device is still responsive
            if not self.send_test_unit_ready():
                self.log("Device not responsive after F5 01 command", logging.WARNING)
                time.sleep(2)
            
            # Send F5 20 command directly (Set Mode)
            self.log("Sending direct F5 20 command (Set Mode)...")
            mode_cmd = bytes([
                0x55, 0x53, 0x42, 0x43,  # USBC signature
                0x02, 0x00, 0x00, 0x00,  # Tag
                0x04, 0x00, 0x00, 0x00,  # Data length (4 bytes)
                0x00,                    # Flags (direction out)
                0x00,                    # LUN
                0x0C,                    # Command length
                0x00,                    # Reserved
                # Command data
                0xF5, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                # Padding to 31 bytes
                0x00, 0x00, 0x00, 0x00
            ])
            
            if not self.direct_write(mode_cmd):
                self.log("Failed to send F5 20 command", logging.WARNING)
                return False
            
            # Send mode data
            mode_data = bytes([0x05, 0x00, 0x00, 0x00])
            if not self.direct_write(mode_data):
                self.log("Failed to send mode data", logging.WARNING)
                return False
            
            # Try to read CSW with longer timeout
            time.sleep(2)
            csw = self.direct_read(13, timeout=3000)
            if csw:
                self.log(f"Got CSW response: {' '.join([f'{b:02X}' for b in csw])}")
                # Check status code
                if csw[-1] != 0:
                    self.log(f"Warning: F5 20 command failed with status {csw[-1]}", logging.WARNING)
            else:
                self.log("No CSW response (might be normal)")
            
            # Much longer wait after mode setting
            time.sleep(5)
            
            # Verify device is still responsive
            if not self.send_test_unit_ready():
                self.log("Device not responsive after F5 20 command", logging.WARNING)
                time.sleep(2)
            
            # Send F5 A0 command directly (Clear Screen)
            self.log("Sending direct F5 A0 command (Clear Screen)...")
            clear_cmd = bytes([
                0x55, 0x53, 0x42, 0x43,  # USBC signature
                0x03, 0x00, 0x00, 0x00,  # Tag
                0x00, 0x00, 0x00, 0x00,  # Data length
                0x00,                    # Flags (direction out)
                0x00,                    # LUN
                0x0C,                    # Command length
                0x00,                    # Reserved
                # Command data
                0xF5, 0xA0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                # Padding to 31 bytes
                0x00, 0x00, 0x00, 0x00
            ])
            
            if not self.direct_write(clear_cmd):
                self.log("Failed to send F5 A0 command", logging.WARNING)
                return False
            
            # Try to read CSW with longer timeout
            time.sleep(2)
            csw = self.direct_read(13, timeout=3000)
            if csw:
                self.log(f"Got CSW response: {' '.join([f'{b:02X}' for b in csw])}")
                # Check status code
                if csw[-1] != 0:
                    self.log(f"Warning: F5 A0 command failed with status {csw[-1]}", logging.WARNING)
            else:
                self.log("No CSW response (might be normal)")
            
            # Allow more time after screen clear
            time.sleep(5)
            
            # Verify device is still responsive
            if not self.send_test_unit_ready():
                self.log("Device not responsive after F5 A0 command", logging.WARNING)
                time.sleep(2)
            
            self.log("Enhanced initialization sequence completed")
            return True
            
        except Exception as e:
            self.log(f"Error during initialization: {e}", logging.ERROR)
            return False
    
    def send_frames(self, max_frames=None):
        """Send frames to the display using direct USB commands with enhanced error handling."""
        if not self.frames:
            self.log("No frames available to send", logging.WARNING)
            return False
        
        if not self.device:
            self.log("Device not connected", logging.ERROR)
            return False
        
        frames_to_send = self.frames
        if max_frames is not None and max_frames > 0:
            frames_to_send = self.frames[:max_frames]
        
        self.log(f"Sending {len(frames_to_send)} frames...")
        
        for i, frame_path in enumerate(frames_to_send):
            try:
                # Verify device is still connected before each frame
                if not self.send_test_unit_ready():
                    self.log("Device not responsive before sending frame", logging.WARNING)
                    time.sleep(2)
                    if not self.send_test_unit_ready():
                        self.log("Device appears disconnected, aborting frame send", logging.ERROR)
                        return False
                
                # Read frame data
                with open(frame_path, 'rb') as f:
                    frame_data = f.read()
                
                frame_name = os.path.basename(frame_path)
                self.log(f"Sending frame {i+1}/{len(frames_to_send)}: {frame_name} ({len(frame_data)} bytes)")
                
                # Construct F5 B0 command (Display Image)
                display_cmd = bytes([
                    0x55, 0x53, 0x42, 0x43,  # USBC signature
                    (i+4) & 0xFF, ((i+4) >> 8) & 0xFF, ((i+4) >> 16) & 0xFF, ((i+4) >> 24) & 0xFF,  # Tag
                    len(frame_data) & 0xFF, (len(frame_data) >> 8) & 0xFF, 
                    (len(frame_data) >> 16) & 0xFF, (len(frame_data) >> 24) & 0xFF,  # Data length
                    0x00,                    # Flags (direction out)
                    0x00,                    # LUN
                    0x0C,                    # Command length
                    0x00,                    # Reserved
                    # Command data
                    0xF5, 0xB0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                    # Padding to 31 bytes
                    0x00, 0x00, 0x00, 0x00
                ])
                
                # Send command
                if not self.direct_write(display_cmd):
                    self.log(f"Failed to send display command for frame {i+1}", logging.ERROR)
                    continue
                
                # Send frame data in smaller chunks with more time between chunks
                chunk_size = 2048  # Smaller 2KB chunks
                for j in range(0, len(frame_data), chunk_size):
                    chunk = frame_data[j:j+chunk_size]
                    if not self.direct_write(chunk):
                        self.log(f"Failed to send frame data chunk {j//chunk_size + 1}", logging.ERROR)
                        break
                    
                    # More delay between chunks
                    time.sleep(0.05)
                
                # Try to read CSW with longer timeout
                time.sleep(1)
                csw = self.direct_read(13, timeout=3000)
                if csw:
                    self.log(f"Got CSW response: {' '.join([f'{b:02X}' for b in csw])}")
                    # Check status code
                    if csw[-1] != 0:
                        self.log(f"Warning: Display command failed with status {csw[-1]}", logging.WARNING)
                else:
                    self.log("No CSW response (might be normal)")
                
                # Longer wait between frames
                time.sleep(3)
                
            except Exception as e:
                self.log(f"Error sending frame {i+1}: {e}", logging.ERROR)
                continue
        
        self.log("Finished sending frames")
        return True
    
    def run_enhanced_approach(self):
        """Run the enhanced direct USB approach to communicate with the device."""
        self.log("Starting Enhanced Direct USB Approach")
        
        try:
            # Connect to the device
            if not self.connect():
                self.log("Failed to connect to device", logging.ERROR)
                return False
            
            # Send initialization sequence with extended stabilization
            if not self.send_init_sequence():
                self.log("Failed during initialization", logging.ERROR)
                return False
            
            # Send frames if available
            if self.frames and not self.send_frames():
                self.log("Failed to send frames", logging.ERROR)
                return False
            
            self.log("Enhanced direct USB approach completed successfully")
            return True
            
        except Exception as e:
            self.log(f"Error during enhanced approach: {e}", logging.ERROR)
            return False
        finally:
            # Close the connection
            self.close()
    
    def close(self):
        """Close the connection to the device."""
        if self.device:
            try:
                # Release all resources
                usb.util.dispose_resources(self.device)
                self.log("Device connection closed")
            except Exception as e:
                self.log(f"Error closing device: {e}", logging.ERROR)
            
            self.device = None

def main():
    parser = argparse.ArgumentParser(description='ALi LCD Device Enhanced Direct USB Approach')
    parser.add_argument('frames_dir', help='Directory containing frame binary files')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--stabilization-time', type=int, default=60, 
                        help='Time in seconds to run stabilization commands (default: 60)')
    parser.add_argument('--max-frames', type=int, help='Maximum number of frames to send')
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    direct = EnhancedDirectUSBApproach(args.frames_dir, args.verbose, args.stabilization_time)
    direct.run_enhanced_approach()

if __name__ == '__main__':
    main()
