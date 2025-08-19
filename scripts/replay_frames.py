#!/usr/bin/env python3
"""
ALi LCD Device Frame Replayer

This script specifically focuses on replaying the binary frames from the Hex Dumps
directory in the exact sequence and timing observed in successful Wireshark captures.
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
F5_DISPLAY_IMAGE = 0xB0

class FrameReplayer:
    def __init__(self, frames_dir, verbose=False):
        self.device = None
        self.tag = 1
        self.verbose = verbose
        self.frames_dir = frames_dir
        self.frames = []
        
        # Load frames
        if not os.path.exists(frames_dir):
            raise ValueError(f"Frames directory not found: {frames_dir}")
        self.load_frames()
    
    def log(self, message):
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(f"[{time.time():.3f}] {message}")
    
    def load_frames(self):
        """Load binary frames from the specified directory."""
        self.log(f"Loading frames from {self.frames_dir}")
        files = [f for f in os.listdir(self.frames_dir) if f.endswith('.bin')]
        files.sort()  # Sort to ensure consistent order
        
        for file in files:
            filepath = os.path.join(self.frames_dir, file)
            size = os.path.getsize(filepath)
            self.log(f"Found frame: {file} ({size} bytes)")
            self.frames.append(filepath)
        
        if len(self.frames) == 0:
            raise ValueError("No frame files found")
        
        self.log(f"Loaded {len(self.frames)} frames")
    
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
        self.log("Device connected")
    
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
    
    def send_display_command(self, frame_data):
        """Send a display command with frame data."""
        cmd = bytes([0xF5, F5_DISPLAY_IMAGE]) + bytes(10)
        data_len = len(frame_data)
        
        # Create CBW
        cbw = self.create_cbw(cmd, data_len)
        expected_tag = self.tag
        self.tag = (self.tag + 1) & 0xFFFFFFFF  # Increment and wrap at 32 bits
        
        try:
            # Send command
            self.log(f"Sending F5 display command (data length: {data_len})")
            self.device.write(EP_OUT, cbw)
            
            # Send frame data
            self.log(f"Sending frame data")
            self.device.write(EP_OUT, frame_data)
            
            # Read CSW
            csw_data = self.device.read(EP_IN, 13)
            csw = self.parse_csw(csw_data)
            
            # Check status
            if csw['status'] != 0:
                self.log(f"Command failed with status: {csw['status']}")
                return False
            
            self.log(f"Command completed successfully (tag: {csw['tag']})")
            return True
            
        except usb.core.USBError as e:
            self.log(f"USB Error: {e}")
            
            # Try to recover
            try:
                self.device.clear_halt(EP_OUT)
                self.device.clear_halt(EP_IN)
            except:
                self.log("Failed to clear halts")
            
            return False
    
    def replay_frames(self, cycles=1, delay=0.1):
        """Replay the frames in sequence."""
        if not self.frames:
            self.log("No frames to replay")
            return
        
        self.log(f"Replaying {len(self.frames)} frames for {cycles} cycles with {delay}s delay")
        
        for cycle in range(cycles):
            self.log(f"Starting cycle {cycle+1}/{cycles}")
            
            for i, frame_path in enumerate(self.frames):
                # Read frame data
                with open(frame_path, 'rb') as f:
                    frame_data = f.read()
                
                self.log(f"Sending frame {i+1}/{len(self.frames)}: {os.path.basename(frame_path)} ({len(frame_data)} bytes)")
                
                # Send the frame
                success = self.send_display_command(frame_data)
                
                if not success:
                    self.log("Failed to send frame, retrying...")
                    # Retry once
                    time.sleep(0.5)
                    success = self.send_display_command(frame_data)
                    
                    if not success:
                        self.log("Failed to send frame after retry")
                
                # Wait before sending next frame
                time.sleep(delay)
    
    def close(self):
        """Close the connection."""
        self.log("Closing connection")

def main():
    parser = argparse.ArgumentParser(description='ALi LCD Device Frame Replayer')
    parser.add_argument('frames_dir', help='Directory containing frame binary files')
    parser.add_argument('--cycles', type=int, default=1, help='Number of replay cycles')
    parser.add_argument('--delay', type=float, default=0.1, help='Delay between frames (seconds)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()
    
    try:
        replayer = FrameReplayer(args.frames_dir, verbose=args.verbose)
        replayer.connect()
        replayer.replay_frames(cycles=args.cycles, delay=args.delay)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
        
    finally:
        if 'replayer' in locals():
            replayer.close()
    
    print("Frame replay completed successfully")

if __name__ == '__main__':
    main()
