#!/usr/bin/env python3
"""
ALi LCD Device Communication Sequence Replicator

This script attempts to replicate the successful communication sequence
observed in Wireshark logs. It implements the full lifecycle from initial
animation state to connected state, and then sends the alternating image
data frames observed in successful captures.
"""

import os
import sys
import time
import argparse
import usb.core
import usb.util
from struct import pack, unpack

# Constants
VENDOR_ID = 0x0402
PRODUCT_ID = 0x3922
EP_OUT = 0x02
EP_IN = 0x81
CBW_SIGNATURE = 0x43425355  # "USBC" in little-endian
CSW_SIGNATURE = 0x53425355  # "USBS" in little-endian
MAX_RETRIES = 5

# F5 Subcommands
F5_RESET = 0x00
F5_INIT = 0x01
F5_ANIMATION_CONTROL = 0x10
F5_SET_MODE = 0x20
F5_GET_STATUS = 0x30
F5_CLEAR_SCREEN = 0xA0
F5_DISPLAY_IMAGE = 0xB0

# Lifecycle States
class DeviceState:
    ANIMATION = "ANIMATION"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"

class ALiLCDSequencer:
    def __init__(self, verbose=False, frames_dir=None):
        self.device = None
        self.tag = 1
        self.verbose = verbose
        self.state = DeviceState.ANIMATION
        self.connection_start_time = None
        self.last_command_time = None
        self.command_count = 0
        self.frames_dir = frames_dir
        self.frames = []
        
        if frames_dir and os.path.exists(frames_dir):
            self.load_frames(frames_dir)
    
    def log(self, message):
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(f"[{self.state}] {message}")
    
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
        """Connect to the ALi LCD device."""
        self.log("Searching for ALi LCD device...")
        self.device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        
        if self.device is None:
            raise ValueError("Device not found")
        
        self.log(f"Device found: {self.device}")
        
        # Detach kernel driver if active
        if self.device.is_kernel_driver_active(0):
            self.log("Detaching kernel driver")
            self.device.detach_kernel_driver(0)
        
        # Set configuration
        self.device.set_configuration()
        
        # Start tracking connection time
        self.connection_start_time = time.time()
        self.last_command_time = time.time()
        self.state = DeviceState.ANIMATION
        self.log("Device connected, entering ANIMATION state")
    
    def create_cbw(self, cmd, data_len=0, direction_in=False):
        """Create a Command Block Wrapper (CBW)."""
        flags = 0x80 if direction_in else 0x00
        cbw = pack('<IIIBBBB',
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
        
        signature, tag, data_residue, status = unpack('<IIIB', data)
        
        if signature != CSW_SIGNATURE:
            raise ValueError(f"Invalid CSW signature: 0x{signature:08X}")
        
        return {
            'signature': signature,
            'tag': tag,
            'data_residue': data_residue,
            'status': status
        }
    
    def send_command(self, cmd, data=None, read_len=0, validate_tag=True):
        """Send a command to the device and handle the response."""
        if data is None:
            data = b''
        
        data_len = len(data) if data else read_len
        direction_in = read_len > 0
        
        # Create CBW
        cbw = self.create_cbw(cmd, data_len, direction_in)
        expected_tag = self.tag
        self.tag = (self.tag + 1) & 0xFFFFFFFF  # Increment and wrap at 32 bits
        
        # Send CBW
        retry_count = 0
        while retry_count < MAX_RETRIES:
            try:
                # Send command
                self.log(f"Sending command: {' '.join(f'{b:02X}' for b in cmd)}")
                self.device.write(EP_OUT, cbw)
                
                # Send or receive data if needed
                if data:
                    self.log(f"Sending {len(data)} bytes of data")
                    self.device.write(EP_OUT, data)
                elif read_len:
                    self.log(f"Reading {read_len} bytes of data")
                    response_data = self.device.read(EP_IN, read_len)
                else:
                    response_data = None
                
                # Read CSW
                csw_data = self.device.read(EP_IN, 13)
                csw = self.parse_csw(csw_data)
                
                # Check status
                if csw['status'] != 0:
                    self.log(f"Command failed with status: {csw['status']}")
                    retry_count += 1
                    time.sleep(0.2 * retry_count)  # Exponential backoff
                    continue
                
                # Validate tag if required (depending on state)
                if validate_tag and self.state == DeviceState.CONNECTED:
                    if csw['tag'] != expected_tag:
                        self.log(f"Tag mismatch: expected {expected_tag}, got {csw['tag']}")
                        # In CONNECTED state, this is an error; in ANIMATION, it's expected
                        if self.state == DeviceState.CONNECTED:
                            retry_count += 1
                            time.sleep(0.2 * retry_count)
                            continue
                
                # Update timing and state tracking
                self.command_count += 1
                elapsed = time.time() - self.connection_start_time
                self.last_command_time = time.time()
                
                # Check for state transitions based on elapsed time
                if self.state == DeviceState.ANIMATION and elapsed >= 56:
                    self.state = DeviceState.CONNECTING
                    self.log(f"Transition to CONNECTING state after {elapsed:.1f} seconds")
                elif self.state == DeviceState.CONNECTING and elapsed >= 60:
                    self.state = DeviceState.CONNECTED
                    self.log(f"Transition to CONNECTED state after {elapsed:.1f} seconds")
                
                # Command successful
                return response_data, csw
                
            except usb.core.USBError as e:
                self.log(f"USB Error: {e}")
                
                # Handle pipe errors
                if "Pipe error" in str(e):
                    self.log("Clearing endpoint halts")
                    try:
                        self.device.clear_halt(EP_OUT)
                        self.device.clear_halt(EP_IN)
                    except:
                        self.log("Failed to clear halts")
                
                retry_count += 1
                time.sleep(0.2 * retry_count)  # Exponential backoff
        
        raise RuntimeError(f"Command failed after {MAX_RETRIES} retries")
    
    def test_unit_ready(self):
        """Send a TEST UNIT READY command."""
        cmd = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        return self.send_command(cmd, validate_tag=(self.state == DeviceState.CONNECTED))
    
    def inquiry(self):
        """Send an INQUIRY command."""
        cmd = bytes([0x12, 0x00, 0x00, 0x00, 0x36, 0x00])
        return self.send_command(cmd, read_len=36, validate_tag=(self.state == DeviceState.CONNECTED))
    
    def f5_command(self, subcommand, data=None, read_len=0):
        """Send a custom F5 command."""
        cmd = bytes([0xF5, subcommand]) + bytes(10)
        return self.send_command(cmd, data, read_len, validate_tag=(self.state == DeviceState.CONNECTED))
    
    def initialize_display(self):
        """Initialize the display."""
        self.log("Initializing display")
        # F5 init command
        self.f5_command(F5_INIT)
        
        # Set mode
        self.f5_command(F5_SET_MODE, bytes([0x05, 0x00, 0x00, 0x00]))
        
        # Stop animation
        self.f5_command(F5_ANIMATION_CONTROL, bytes([0x00]))
        
        # Clear screen
        self.f5_command(F5_CLEAR_SCREEN)
    
    def send_frame(self, frame_path):
        """Send a frame to the display."""
        self.log(f"Sending frame: {frame_path}")
        
        # Read the frame data
        with open(frame_path, 'rb') as f:
            frame_data = f.read()
        
        # Send display image command
        self.f5_command(F5_DISPLAY_IMAGE, frame_data)
    
    def run_animation_sequence(self, duration=300):
        """Run the animation sequence for the specified duration."""
        self.log(f"Running animation sequence for {duration} seconds")
        
        if not self.frames:
            self.log("No frames found, cannot run animation")
            return
        
        start_time = time.time()
        frame_index = 0
        
        while time.time() - start_time < duration:
            # Check if we need to send keep-alive commands
            if time.time() - self.last_command_time > 4:
                self.test_unit_ready()
            
            # Send next frame
            frame_path = self.frames[frame_index]
            self.send_frame(frame_path)
            
            # Move to next frame
            frame_index = (frame_index + 1) % len(self.frames)
            
            # Small delay between frames
            time.sleep(0.1)
    
    def run_initialization_sequence(self):
        """Run the initialization sequence to reach CONNECTED state."""
        self.log("Starting initialization sequence")
        
        # Connect to the device
        self.connect()
        
        # Start sending commands until we reach CONNECTED state
        start_time = time.time()
        
        while self.state != DeviceState.CONNECTED:
            # Send test unit ready command
            self.test_unit_ready()
            
            # Send inquiry every 5 commands
            if self.command_count % 5 == 0:
                self.inquiry()
            
            # Add delay based on state
            if self.state == DeviceState.ANIMATION:
                time.sleep(0.2)  # Longer delay in ANIMATION state
            else:
                time.sleep(0.05)  # Shorter delay in other states
            
            # Check for timeout
            if time.time() - start_time > 120:
                raise TimeoutError("Failed to reach CONNECTED state within 120 seconds")
        
        self.log("Reached CONNECTED state")
        
        # Initialize display
        self.initialize_display()
    
    def close(self):
        """Close the connection to the device."""
        if self.device:
            # No specific cleanup needed for this device
            self.log("Closing connection")

def main():
    parser = argparse.ArgumentParser(description='ALi LCD Device Communication Sequence Replicator')
    parser.add_argument('--frames', help='Directory containing frame binary files')
    parser.add_argument('--duration', type=int, default=300, help='Duration to run the animation sequence (seconds)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()
    
    sequencer = ALiLCDSequencer(verbose=args.verbose, frames_dir=args.frames)
    
    try:
        # Run initialization sequence
        sequencer.run_initialization_sequence()
        
        # Run animation sequence
        sequencer.run_animation_sequence(duration=args.duration)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
        
    finally:
        sequencer.close()
    
    print("Sequence completed successfully")

if __name__ == '__main__':
    main()
