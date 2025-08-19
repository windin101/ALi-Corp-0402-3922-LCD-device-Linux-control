#!/usr/bin/env python3
"""
ALi LCD Device Exact Sequence Replicator

This script attempts to exactly replicate the command sequence seen in the Wireshark
captures, with precise command ordering, timing and payload sizes. It doesn't try
to be smart about state transitions, but simply replays the exact sequence that
worked in the capture.
"""

import os
import sys
import time
import struct
import argparse
import logging
import usb.core
import usb.util

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Constants
VENDOR_ID = 0x0402
PRODUCT_ID = 0x3922
EP_OUT = 0x02
EP_IN = 0x81
CBW_SIGNATURE = 0x43425355  # "USBC" in little-endian
CSW_SIGNATURE = 0x53425355  # "USBS" in little-endian

class ExactSequencer:
    def __init__(self, frames_dir=None, verbose=False):
        self.device = None
        self.frames_dir = frames_dir
        self.frames = []
        self.verbose = verbose
        self.tag = 1
        
        if frames_dir and os.path.exists(frames_dir):
            self.load_frames(frames_dir)
    
    def log(self, message):
        """Print message if verbose mode is enabled."""
        if self.verbose:
            logger.info(message)
        else:
            logger.debug(message)
    
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
        try:
            self.device.set_configuration()
        except:
            # Device might already be configured
            pass
        
        # Get active configuration
        cfg = self.device.get_active_configuration()
        
        # Find the interface we need
        interface = cfg[(0,0)]
        
        # Claim the interface
        usb.util.claim_interface(self.device, interface.bInterfaceNumber)
        
        self.log("Device connected successfully")
    
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
    
    def send_command(self, cmd, data=None, read_len=0, retry_count=3, ignore_errors=False):
        """Send a command to the device and handle the response."""
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
                self.log(f"Sending command: {' '.join(f'{b:02X}' for b in cmd)} (tag={current_tag})")
                self.device.write(EP_OUT, cbw)
                
                # Send or receive data if needed
                if data:
                    self.log(f"Sending {len(data)} bytes of data")
                    self.device.write(EP_OUT, data)
                elif read_len:
                    self.log(f"Reading {read_len} bytes of data")
                    response_data = self.device.read(EP_IN, read_len, timeout=5000)
                else:
                    response_data = None
                
                # Read CSW
                csw_data = self.device.read(EP_IN, 13, timeout=5000)
                csw = self.parse_csw(csw_data)
                
                # Check status
                if csw['status'] != 0 and not ignore_errors:
                    self.log(f"Command failed with status: {csw['status']}")
                    if attempts < retry_count - 1:
                        attempts += 1
                        time.sleep(0.2 * (attempts + 1))  # Exponential backoff
                        continue
                
                # Return response and CSW
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
                
                # Retry or raise
                if attempts < retry_count - 1:
                    attempts += 1
                    time.sleep(0.2 * (attempts + 1))  # Exponential backoff
                else:
                    if ignore_errors:
                        return None, None
                    raise
        
        raise RuntimeError(f"Command failed after {retry_count} retries")
    
    def run_exact_sequence(self):
        """
        Run the exact sequence of commands observed in the Wireshark capture.
        """
        logger.info("Starting exact sequence replication")
        
        try:
            # Connect to the device
            self.connect()
            
            # Phase 1: Initial animation state (0-55 seconds)
            # Just send TEST UNIT READY commands every 200ms for the first 55 seconds
            logger.info("Phase 1: Animation state (0-55 seconds)")
            start_time = time.time()
            animation_end_time = start_time + 55
            
            cmd_count = 0
            while time.time() < animation_end_time:
                try:
                    cmd = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00])  # TEST UNIT READY
                    _, csw = self.send_command(cmd, retry_count=1, ignore_errors=True)
                    cmd_count += 1
                    
                    if cmd_count % 10 == 0:
                        elapsed = time.time() - start_time
                        logger.info(f"Animation state: {cmd_count} commands sent, elapsed: {elapsed:.1f}s")
                    
                    # Sleep 200ms between commands
                    time.sleep(0.2)
                except Exception as e:
                    logger.warning(f"Error in Animation state: {e}")
                    time.sleep(0.5)
            
            # Phase 2: Connecting state (55-58 seconds)
            # Send TEST UNIT READY commands every 100ms for 3 seconds
            logger.info("Phase 2: Connecting state (55-58 seconds)")
            connecting_end_time = animation_end_time + 3
            
            while time.time() < connecting_end_time:
                try:
                    cmd = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00])  # TEST UNIT READY
                    _, csw = self.send_command(cmd, retry_count=1, ignore_errors=True)
                    
                    # Sleep 100ms between commands
                    time.sleep(0.1)
                except Exception as e:
                    logger.warning(f"Error in Connecting state: {e}")
                    time.sleep(0.2)
            
            # Phase 3: Connected state - First, try to initialize the display
            logger.info("Phase 3: Connected state - Initializing display")
            
            # Wait 1 second before sending initialization
            time.sleep(1)
            
            # Send F5 01 (Initialize Display)
            try:
                logger.info("Sending F5 01 (Initialize Display)")
                cmd = bytes([0xF5, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
                _, csw = self.send_command(cmd, retry_count=2, ignore_errors=True)
                
                # Wait 500ms
                time.sleep(0.5)
                
                # Send F5 20 (Set Mode)
                logger.info("Sending F5 20 (Set Mode)")
                cmd = bytes([0xF5, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
                data = bytes([0x05, 0x00, 0x00, 0x00])
                _, csw = self.send_command(cmd, data=data, retry_count=2, ignore_errors=True)
                
                # Wait 500ms
                time.sleep(0.5)
                
                # Send F5 10 (Stop Animation)
                logger.info("Sending F5 10 (Stop Animation)")
                cmd = bytes([0xF5, 0x10, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
                data = bytes([0x00])
                _, csw = self.send_command(cmd, data=data, retry_count=2, ignore_errors=True)
                
                # Wait 500ms
                time.sleep(0.5)
                
                # Send F5 A0 (Clear Screen)
                logger.info("Sending F5 A0 (Clear Screen)")
                cmd = bytes([0xF5, 0xA0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
                _, csw = self.send_command(cmd, retry_count=2, ignore_errors=True)
                
                # Wait 1 second
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error initializing display: {e}")
            
            # Phase 4: Send frames if available
            if self.frames:
                logger.info(f"Phase 4: Sending {len(self.frames)} frames")
                
                # Alternate frame sizes pattern:
                # Send frames in the exact alternating pattern seen in the captures
                for i, frame_path in enumerate(self.frames):
                    try:
                        # Read frame data
                        with open(frame_path, 'rb') as f:
                            frame_data = f.read()
                        
                        # Send Display Image command
                        logger.info(f"Sending frame {i+1}/{len(self.frames)}: {os.path.basename(frame_path)} ({len(frame_data)} bytes)")
                        cmd = bytes([0xF5, 0xB0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
                        _, csw = self.send_command(cmd, data=frame_data, retry_count=1, ignore_errors=True)
                        
                        # Wait between frames
                        # Use a shorter delay for the first few frames
                        if i < 3:
                            time.sleep(0.2)
                        else:
                            time.sleep(0.5)
                        
                        # Send a TEST UNIT READY every 3 frames to maintain connection
                        if i % 3 == 0:
                            cmd = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00])  # TEST UNIT READY
                            self.send_command(cmd, retry_count=1, ignore_errors=True)
                        
                    except Exception as e:
                        logger.error(f"Error sending frame {i+1}: {e}")
                        # Continue with next frame
                        continue
            
            logger.info("Sequence completed successfully")
            
        except Exception as e:
            logger.error(f"Error during sequence: {e}")
        finally:
            # Close the connection
            self.close()
    
    def close(self):
        """Close the connection to the device."""
        if self.device:
            try:
                # Release all resources
                usb.util.dispose_resources(self.device)
                logger.info("Device connection closed")
            except Exception as e:
                logger.error(f"Error closing device: {e}")
            
            self.device = None

def main():
    parser = argparse.ArgumentParser(description='ALi LCD Device Exact Sequence Replicator')
    parser.add_argument('frames_dir', help='Directory containing frame binary files')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    sequencer = ExactSequencer(args.frames_dir, args.verbose)
    sequencer.run_exact_sequence()

if __name__ == '__main__':
    main()
