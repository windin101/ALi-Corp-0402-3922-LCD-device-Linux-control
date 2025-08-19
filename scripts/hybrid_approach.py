#!/usr/bin/env python3
"""
ALi LCD Device Hybrid Approach

This script combines the successful elements from both minimal_connection.py and
exact_sequence.py, with improved error handling and recovery mechanisms.
"""

import os
import sys
import time
import struct
import argparse
import logging
from typing import Optional, Tuple, Dict, List, Any
import usb.core
import usb.util

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
CBW_SIGNATURE = 0x43425355  # "USBC" in little-endian
CSW_SIGNATURE = 0x53425355  # "USBS" in little-endian

class DeviceLifecycleState:
    ANIMATION = "Animation"
    CONNECTING = "Connecting"
    CONNECTED = "Connected"

class HybridApproach:
    def __init__(self, frames_dir=None, verbose=False):
        """Initialize the class with optional frame directory."""
        self.device = None
        self.frames_dir = frames_dir
        self.frames = []
        self.verbose = verbose
        self.tag = 1
        self.state = DeviceLifecycleState.ANIMATION
        self.command_count = 0
        self.state_transition_times = {
            DeviceLifecycleState.ANIMATION: 0,
            DeviceLifecycleState.CONNECTING: 0,
            DeviceLifecycleState.CONNECTED: 0
        }
        
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
        """Connect to the ALi LCD device with robust error handling."""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                self.log(f"Searching for ALi LCD device (attempt {retry_count + 1}/{max_retries})...")
                self.device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
                
                if self.device is None:
                    self.log("Device not found", logging.WARNING)
                    retry_count += 1
                    time.sleep(1)
                    continue
                
                self.log(f"Device found: {self.device}")
                
                # Detach kernel driver if active
                for config in self.device:
                    for interface in range(config.bNumInterfaces):
                        if self.device.is_kernel_driver_active(interface):
                            self.log(f"Detaching kernel driver from interface {interface}")
                            try:
                                self.device.detach_kernel_driver(interface)
                            except usb.core.USBError as e:
                                self.log(f"Warning: Failed to detach kernel driver: {e}", logging.WARNING)
                
                # Set configuration
                try:
                    self.device.set_configuration()
                except usb.core.USBError as e:
                    self.log(f"Warning: Failed to set configuration: {e}", logging.WARNING)
                
                # Get active configuration
                cfg = self.device.get_active_configuration()
                
                # Find the interface we need
                interface = cfg[(0,0)]
                
                # Claim the interface
                try:
                    usb.util.claim_interface(self.device, interface.bInterfaceNumber)
                except usb.core.USBError as e:
                    self.log(f"Warning: Failed to claim interface: {e}", logging.WARNING)
                    # Try to continue anyway
                
                self.log("Device connected successfully")
                self.state = DeviceLifecycleState.ANIMATION
                self.state_transition_times[DeviceLifecycleState.ANIMATION] = time.time()
                return True
                
            except usb.core.USBError as e:
                self.log(f"USB Error during connect: {e}", logging.ERROR)
                retry_count += 1
                time.sleep(1)
            
            except Exception as e:
                self.log(f"Unexpected error during connect: {e}", logging.ERROR)
                retry_count += 1
                time.sleep(1)
        
        self.log("Failed to connect to device after multiple attempts", logging.ERROR)
        return False
    
    def create_cbw(self, cmd, data_len=0, direction_in=False):
        """Create a Command Block Wrapper (CBW)."""
        flags = 0x80 if direction_in else 0x00
        cbw = struct.pack('<IIIBBBB',
                   CBW_SIGNATURE,    # dCBWSignature
                   self.tag,         # dCBWTag
                   data_len,         # dCBWDataTransferLength
                   flags,            # bmCBWFlags
                   0,                # bCBWLUN
                   len(cmd),         # bCBWCBLength
                   0)                # reserved
        cbw += cmd + bytes(16 - len(cmd))  # Pad to 16 bytes
        return cbw
    
    def parse_csw(self, data):
        """Parse a Command Status Wrapper (CSW)."""
        if len(data) != 13:
            raise ValueError(f"Invalid CSW length: {len(data)}")
        
        signature, tag, data_residue, status = struct.unpack('<IIIB', data)
        
        if signature != CSW_SIGNATURE:
            raise ValueError(f"Invalid CSW signature: 0x{signature:08X}")
        
        return {
            'signature': signature,
            'tag': tag,
            'data_residue': data_residue,
            'status': status
        }
    
    def send_command(self, cmd, data=None, read_len=0, retry_count=3, ignore_errors=False, timeout=5000):
        """Send a command to the device and handle the response with improved error handling."""
        if self.device is None:
            self.log("Error: Device not connected", logging.ERROR)
            return None, None
        
        if data is None:
            data = b''
        
        data_len = len(data) if data else read_len
        direction_in = read_len > 0
        
        # Create CBW
        cbw = self.create_cbw(cmd, data_len, direction_in)
        current_tag = self.tag
        self.tag = (self.tag + 1) & 0xFFFFFFFF  # Increment and wrap at 32 bits
        
        # Send CBW
        attempts = 0
        while attempts < retry_count:
            try:
                # Send command
                cmd_hex = ' '.join(f'{b:02X}' for b in cmd)
                self.log(f"Sending command: {cmd_hex} (tag={current_tag})", logging.DEBUG)
                self.device.write(EP_OUT, cbw, timeout=timeout)
                
                # Send or receive data if needed
                if data:
                    self.log(f"Sending {len(data)} bytes of data", logging.DEBUG)
                    self.device.write(EP_OUT, data, timeout=timeout)
                elif read_len:
                    self.log(f"Reading {read_len} bytes of data", logging.DEBUG)
                    response_data = self.device.read(EP_IN, read_len, timeout=timeout)
                else:
                    response_data = None
                
                # Read CSW
                csw_data = self.device.read(EP_IN, 13, timeout=timeout)
                csw = self.parse_csw(csw_data)
                
                # Update command counter
                self.command_count += 1
                
                # Check status
                if csw['status'] != 0 and not ignore_errors:
                    self.log(f"Command failed with status: {csw['status']}", logging.DEBUG)
                    if attempts < retry_count - 1:
                        attempts += 1
                        time.sleep(0.1 * (attempts + 1))  # Exponential backoff
                        continue
                
                # Check tag mismatch
                if csw['tag'] != current_tag:
                    self.log(f"Tag mismatch: expected {current_tag}, got {csw['tag']}", logging.WARNING)
                
                # Return response and CSW
                return response_data, csw
                
            except usb.core.USBError as e:
                self.log(f"USB Error: {e}", logging.DEBUG)
                
                # Handle pipe errors
                if "Pipe error" in str(e):
                    self.log("Clearing endpoint halts", logging.DEBUG)
                    try:
                        self.device.clear_halt(EP_OUT)
                        self.device.clear_halt(EP_IN)
                    except:
                        self.log("Failed to clear halts", logging.DEBUG)
                
                # Check if device is still connected
                if "No such device" in str(e):
                    self.log("Device disconnected", logging.WARNING)
                    self.device = None
                    return None, None
                
                # Retry or raise
                if attempts < retry_count - 1:
                    attempts += 1
                    time.sleep(0.1 * (attempts + 1))  # Exponential backoff
                else:
                    if ignore_errors:
                        return None, None
                    raise
            
            except Exception as e:
                self.log(f"Unexpected error: {e}", logging.ERROR)
                if attempts < retry_count - 1:
                    attempts += 1
                    time.sleep(0.1 * (attempts + 1))
                else:
                    if ignore_errors:
                        return None, None
                    raise
        
        if ignore_errors:
            return None, None
        raise RuntimeError(f"Command failed after {retry_count} retries")
    
    def test_unit_ready(self, ignore_errors=True, expect_failure=False):
        """Send a TEST UNIT READY command and interpret the results."""
        cmd = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        _, csw = self.send_command(cmd, retry_count=1, ignore_errors=ignore_errors)
        
        if csw is None:
            return False, False
        
        # Status 0 = success, 1 = failure
        success = (csw['status'] == 0)
        tag_match = (csw['tag'] == self.tag - 1)
        
        if expect_failure and not success:
            # This is expected in certain states
            return True, tag_match
        
        return success, tag_match
    
    def inquiry(self, allocation_length=36):
        """Send an INQUIRY command."""
        cmd = bytes([0x12, 0x00, 0x00, 0x00, allocation_length, 0x00])
        data, csw = self.send_command(cmd, read_len=allocation_length, retry_count=2, ignore_errors=True)
        
        if data is None or csw is None:
            return None
        
        return data
    
    def detect_state_transition(self):
        """Detect state transitions based on command responses."""
        # Check for transitions
        now = time.time()
        
        if self.state == DeviceLifecycleState.ANIMATION:
            # After about 55 seconds, transition to CONNECTING state
            if now - self.state_transition_times[DeviceLifecycleState.ANIMATION] >= 55:
                self.state = DeviceLifecycleState.CONNECTING
                self.state_transition_times[DeviceLifecycleState.CONNECTING] = now
                self.log(f"State transition: {DeviceLifecycleState.ANIMATION} → {DeviceLifecycleState.CONNECTING}")
                return True
        
        elif self.state == DeviceLifecycleState.CONNECTING:
            # After about 3 seconds in CONNECTING, transition to CONNECTED state
            if now - self.state_transition_times[DeviceLifecycleState.CONNECTING] >= 3:
                self.state = DeviceLifecycleState.CONNECTED
                self.state_transition_times[DeviceLifecycleState.CONNECTED] = now
                self.log(f"State transition: {DeviceLifecycleState.CONNECTING} → {DeviceLifecycleState.CONNECTED}")
                return True
        
        return False
    
    def wait_for_animation_phase(self):
        """Wait during the animation phase, sending TEST UNIT READY commands."""
        self.log("Phase 1: Animation state (waiting for ~55 seconds)")
        start_time = time.time()
        animation_end_time = start_time + 55
        
        while time.time() < animation_end_time and self.device is not None:
            try:
                # Send TEST UNIT READY every 200ms
                success, tag_match = self.test_unit_ready(expect_failure=True)
                
                if self.command_count % 10 == 0:
                    elapsed = time.time() - start_time
                    self.log(f"Animation state: {self.command_count} commands sent, elapsed: {elapsed:.1f}s")
                
                # Check for state transition
                if self.detect_state_transition():
                    break
                
                # Sleep 200ms between commands
                time.sleep(0.2)
                
            except Exception as e:
                self.log(f"Error in Animation state: {e}", logging.WARNING)
                time.sleep(0.5)
                
                # Try to reconnect if needed
                if self.device is None:
                    self.log("Device disconnected, attempting to reconnect...", logging.WARNING)
                    if not self.connect():
                        self.log("Failed to reconnect, exiting Animation phase", logging.ERROR)
                        return False
        
        return self.device is not None
    
    def wait_for_connecting_phase(self):
        """Wait during the connecting phase."""
        if self.state != DeviceLifecycleState.CONNECTING:
            self.log(f"Expected CONNECTING state, but current state is {self.state}", logging.WARNING)
            return False
        
        self.log("Phase 2: Connecting state (waiting for ~3 seconds)")
        start_time = time.time()
        connecting_end_time = start_time + 3
        
        while time.time() < connecting_end_time and self.device is not None:
            try:
                # Send TEST UNIT READY every 100ms
                success, tag_match = self.test_unit_ready()
                
                # Check for state transition
                if self.detect_state_transition():
                    break
                
                # Sleep 100ms between commands
                time.sleep(0.1)
                
            except Exception as e:
                self.log(f"Error in Connecting state: {e}", logging.WARNING)
                time.sleep(0.2)
                
                # Try to reconnect if needed
                if self.device is None:
                    self.log("Device disconnected, attempting to reconnect...", logging.WARNING)
                    if not self.connect():
                        self.log("Failed to reconnect, exiting Connecting phase", logging.ERROR)
                        return False
        
        return self.device is not None
    
    def stabilize_connection(self, duration=10):
        """Stabilize the connection by sending simple commands."""
        if self.state != DeviceLifecycleState.CONNECTED:
            self.log(f"Expected CONNECTED state, but current state is {self.state}", logging.WARNING)
            return False
        
        self.log(f"Phase 3: Connected state - Stabilizing connection for {duration} seconds")
        start_time = time.time()
        end_time = start_time + duration
        
        self.log("Sending TEST UNIT READY commands to maintain connection...")
        
        while time.time() < end_time and self.device is not None:
            try:
                # Send TEST UNIT READY every 500ms
                success, tag_match = self.test_unit_ready()
                
                # Sleep 500ms between commands
                time.sleep(0.5)
                
            except Exception as e:
                self.log(f"Error while stabilizing connection: {e}", logging.WARNING)
                
                # Try to reconnect if needed
                if self.device is None:
                    self.log("Device disconnected, attempting to reconnect...", logging.WARNING)
                    if not self.connect():
                        self.log("Failed to reconnect, exiting stabilization phase", logging.ERROR)
                        return False
        
        self.log(f"Connection stabilized for {duration} seconds")
        return self.device is not None
    
    def initialize_display(self):
        """Initialize the display with a careful approach."""
        if self.state != DeviceLifecycleState.CONNECTED:
            self.log(f"Expected CONNECTED state, but current state is {self.state}", logging.WARNING)
            return False
        
        self.log("Phase 4: Connected state - Initializing display")
        
        # Wait a bit before sending initialization
        time.sleep(1)
        
        try:
            # Test with simple commands first
            self.log("Testing with TEST UNIT READY before display initialization")
            for i in range(5):
                success, tag_match = self.test_unit_ready()
                self.log(f"TEST UNIT READY {i+1}/5: Success={success}, Tag Match={tag_match}")
                time.sleep(0.5)
            
            # Try an INQUIRY command as a test
            self.log("Sending INQUIRY command")
            inquiry_data = self.inquiry()
            if inquiry_data is not None:
                self.log(f"INQUIRY successful, received {len(inquiry_data)} bytes")
            else:
                self.log("INQUIRY failed", logging.WARNING)
                # Continue anyway
            
            # Send initialization commands with careful timing and error handling
            self.log("Sending F5 01 (Initialize Display)")
            cmd = bytes([0xF5, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            _, csw = self.send_command(cmd, retry_count=1, ignore_errors=True, timeout=2000)
            
            # Check if device is still connected
            if self.device is None:
                self.log("Device disconnected after F5 01 command", logging.ERROR)
                return False
            
            # Sleep longer between commands
            time.sleep(1)
            
            # Send TEST UNIT READY to check device still responds
            success, tag_match = self.test_unit_ready()
            self.log(f"TEST UNIT READY after F5 01: Success={success}, Tag Match={tag_match}")
            
            # Send F5 20 (Set Mode)
            self.log("Sending F5 20 (Set Mode)")
            cmd = bytes([0xF5, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            data = bytes([0x05, 0x00, 0x00, 0x00])
            _, csw = self.send_command(cmd, data=data, retry_count=1, ignore_errors=True, timeout=2000)
            
            # Check if device is still connected
            if self.device is None:
                self.log("Device disconnected after F5 20 command", logging.ERROR)
                return False
            
            # Sleep longer between commands
            time.sleep(1)
            
            # Send TEST UNIT READY to check device still responds
            success, tag_match = self.test_unit_ready()
            self.log(f"TEST UNIT READY after F5 20: Success={success}, Tag Match={tag_match}")
            
            # Send F5 10 (Stop Animation)
            self.log("Sending F5 10 (Stop Animation)")
            cmd = bytes([0xF5, 0x10, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            data = bytes([0x00])
            _, csw = self.send_command(cmd, data=data, retry_count=1, ignore_errors=True, timeout=2000)
            
            # Check if device is still connected
            if self.device is None:
                self.log("Device disconnected after F5 10 command", logging.ERROR)
                return False
            
            # Sleep longer between commands
            time.sleep(1)
            
            # Send TEST UNIT READY to check device still responds
            success, tag_match = self.test_unit_ready()
            self.log(f"TEST UNIT READY after F5 10: Success={success}, Tag Match={tag_match}")
            
            # Send F5 A0 (Clear Screen)
            self.log("Sending F5 A0 (Clear Screen)")
            cmd = bytes([0xF5, 0xA0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            _, csw = self.send_command(cmd, retry_count=1, ignore_errors=True, timeout=2000)
            
            # Check if device is still connected
            if self.device is None:
                self.log("Device disconnected after F5 A0 command", logging.ERROR)
                return False
            
            # Sleep longer
            time.sleep(2)
            
            # Send TEST UNIT READY to check device still responds
            success, tag_match = self.test_unit_ready()
            self.log(f"TEST UNIT READY after F5 A0: Success={success}, Tag Match={tag_match}")
            
            self.log("Display initialization completed")
            return True
            
        except Exception as e:
            self.log(f"Error initializing display: {e}", logging.ERROR)
            return False
    
    def send_frames(self, max_frames=None):
        """Send frames to the display."""
        if not self.frames:
            self.log("No frames available to send", logging.WARNING)
            return False
        
        if self.state != DeviceLifecycleState.CONNECTED:
            self.log(f"Expected CONNECTED state, but current state is {self.state}", logging.WARNING)
            return False
        
        self.log(f"Phase 5: Sending frames")
        
        frames_to_send = self.frames
        if max_frames is not None and max_frames > 0:
            frames_to_send = self.frames[:max_frames]
        
        self.log(f"Will send {len(frames_to_send)} frames")
        
        for i, frame_path in enumerate(frames_to_send):
            try:
                # Read frame data
                with open(frame_path, 'rb') as f:
                    frame_data = f.read()
                
                # Send Display Image command
                frame_name = os.path.basename(frame_path)
                self.log(f"Sending frame {i+1}/{len(frames_to_send)}: {frame_name} ({len(frame_data)} bytes)")
                
                cmd = bytes([0xF5, 0xB0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
                _, csw = self.send_command(cmd, data=frame_data, retry_count=1, ignore_errors=True, timeout=5000)
                
                # Check if device is still connected
                if self.device is None:
                    self.log(f"Device disconnected while sending frame {i+1}", logging.ERROR)
                    return False
                
                # Wait between frames
                if i < 3:
                    time.sleep(0.5)  # Shorter delay for first few frames
                else:
                    time.sleep(1.0)  # Longer delay for later frames
                
                # Send a TEST UNIT READY every 2 frames to maintain connection
                if i % 2 == 0:
                    success, tag_match = self.test_unit_ready()
                    self.log(f"TEST UNIT READY between frames: Success={success}, Tag Match={tag_match}")
                
            except Exception as e:
                self.log(f"Error sending frame {i+1}: {e}", logging.ERROR)
                # Continue with next frame
                continue
        
        self.log("Frame sending completed")
        return True
    
    def run_hybrid_approach(self, interactive=False):
        """Run the hybrid approach combining elements from both scripts."""
        self.log("Starting ALi LCD Device Hybrid Approach")
        
        try:
            # Step 1: Connect to the device
            if not self.connect():
                self.log("Failed to connect to device", logging.ERROR)
                return False
            
            # Step 2: Wait through the Animation phase
            if not self.wait_for_animation_phase():
                self.log("Failed during Animation phase", logging.ERROR)
                return False
            
            # Step 3: Wait through the Connecting phase
            if not self.wait_for_connecting_phase():
                self.log("Failed during Connecting phase", logging.ERROR)
                return False
            
            # Step 4: Stabilize the connection
            if not self.stabilize_connection(duration=15):
                self.log("Failed to stabilize connection", logging.ERROR)
                return False
            
            # Interactive pause if requested
            if interactive:
                input("Device has reached Connected state and connection is stabilized. Press Enter to proceed with display initialization...")
            
            # Step 5: Initialize the display
            if not self.initialize_display():
                self.log("Failed to initialize display", logging.ERROR)
                return False
            
            # Interactive pause if requested
            if interactive:
                input("Display initialization complete. Press Enter to proceed with sending frames...")
            
            # Step 6: Send frames
            if self.frames and not self.send_frames():
                self.log("Failed to send frames", logging.ERROR)
                return False
            
            self.log("Hybrid approach completed successfully")
            return True
            
        except Exception as e:
            self.log(f"Error during hybrid approach: {e}", logging.ERROR)
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
    parser = argparse.ArgumentParser(description='ALi LCD Device Hybrid Approach')
    parser.add_argument('frames_dir', help='Directory containing frame binary files')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--interactive', action='store_true', help='Enable interactive pauses')
    parser.add_argument('--max-frames', type=int, help='Maximum number of frames to send')
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    hybrid = HybridApproach(args.frames_dir, args.verbose)
    hybrid.run_hybrid_approach(interactive=args.interactive)

if __name__ == '__main__':
    main()
