#!/usr/bin/env python3
"""
ALi LCD Device Initialization and Frame Replay

This script first initializes the ALi LCD device using the proven methods from
init_command_test.py to get it into the "Waiting for Connection" state, and then
replays the binary frames from the Hex Dumps folder.
"""

import os
import sys
import time
import argparse
import logging
import usb.core
import usb.util
from struct import pack, unpack

# Add the src directory to the path so we can import ali_lcd_device
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

# Import the ALi LCD device class
from ali_lcd_device.device import ALiLCDDevice
from ali_lcd_device.lifecycle import DeviceLifecycleState
from ali_lcd_device.commands import create_f5_display_image_command

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Constants for frame replay
F5_DISPLAY_IMAGE = 0xB0

class FrameReplayer:
    def __init__(self, frames_dir, device=None, verbose=False):
        """
        Initialize the frame replayer.
        
        Args:
            frames_dir (str): Directory containing binary frame files
            device (ALiLCDDevice): Pre-initialized ALi LCD device
            verbose (bool): Enable verbose logging
        """
        self.frames_dir = frames_dir
        self.frames = []
        self.device = device
        self.verbose = verbose
        
        # Load frames from directory
        self.load_frames()
    
    def log(self, message):
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            logger.info(message)
        else:
            logger.debug(message)
    
    def load_frames(self):
        """Load binary frames from the specified directory."""
        if not os.path.exists(self.frames_dir):
            raise ValueError(f"Frames directory not found: {self.frames_dir}")
        
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
    
    def replay_frames(self, cycles=1, delay=0.1):
        """
        Replay the frames in sequence.
        
        Args:
            cycles (int): Number of times to cycle through all frames
            delay (float): Delay between frames in seconds
        """
        if not self.frames:
            logger.warning("No frames to replay")
            return
        
        logger.info(f"Replaying {len(self.frames)} frames for {cycles} cycles with {delay}s delay")
        
        for cycle in range(cycles):
            logger.info(f"Starting cycle {cycle+1}/{cycles}")
            
            for i, frame_path in enumerate(self.frames):
                # Read frame data
                with open(frame_path, 'rb') as f:
                    frame_data = f.read()
                
                logger.info(f"Sending frame {i+1}/{len(self.frames)}: {os.path.basename(frame_path)} ({len(frame_data)} bytes)")
                
                # Use our device instance to send the frame
                try:
                    # Create F5 display image command
                    cmd, data_length, direction = create_f5_display_image_command(
                        width=480, height=480, x=0, y=0)
                    
                    # Send the command and data
                    success, tag_mismatch, _ = self.device._send_command(
                        cmd, len(frame_data), direction, frame_data)
                    
                    if not success:
                        logger.warning(f"Failed to send frame {i+1} (status != 0)")
                    elif tag_mismatch:
                        logger.warning(f"Tag mismatch when sending frame {i+1}")
                    else:
                        logger.info(f"Frame {i+1} sent successfully")
                    
                except Exception as e:
                    logger.error(f"Error sending frame: {e}")
                
                # Wait before sending next frame
                time.sleep(delay)
                
                # Send TEST UNIT READY occasionally to maintain connection
                if i % 3 == 0:
                    try:
                        self.device._test_unit_ready()
                    except Exception as e:
                        logger.warning(f"Error in keep-alive command: {e}")

def initialize_device():
    """
    Initialize the ALi LCD device and wait for it to reach the Connected state.
    
    Returns:
        ALiLCDDevice: Initialized device
    """
    logger.info("Initializing ALi LCD device")
    device = ALiLCDDevice()
    
    try:
        # Connect to the device
        logger.info("Connecting to device")
        device.connect()
        
        # Wait for the device to reach the Connected state
        logger.info("Waiting for device to reach Connected state (60 seconds)...")
        if not device._wait_for_connected_state(timeout=60):
            logger.warning("Failed to reach Connected state within timeout")
            # Continue anyway as the device might still be usable
        
        # Check the current state
        logger.info(f"Current device state: {device.lifecycle_state}")
        
        # Initialize the display
        if device.lifecycle_state == DeviceLifecycleState.CONNECTED:
            logger.info("Initializing display")
            if not device.initialize_display():
                logger.warning("Failed to initialize display")
        
        return device
        
    except Exception as e:
        logger.error(f"Error initializing device: {e}")
        device.close()
        raise

def main():
    parser = argparse.ArgumentParser(description='ALi LCD Device Initialization and Frame Replay')
    parser.add_argument('frames_dir', help='Directory containing frame binary files')
    parser.add_argument('--cycles', type=int, default=1, help='Number of replay cycles')
    parser.add_argument('--delay', type=float, default=0.1, help='Delay between frames (seconds)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()
    
    try:
        # First initialize the device using the proven method
        device = initialize_device()
        
        # Then use the frame replayer to send the binary frames
        replayer = FrameReplayer(args.frames_dir, device, args.verbose)
        replayer.replay_frames(cycles=args.cycles, delay=args.delay)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
        
    finally:
        # Close the device connection
        if 'device' in locals():
            logger.info("Closing device connection")
            device.close()
    
    logger.info("Frame replay completed successfully")

if __name__ == '__main__':
    main()
