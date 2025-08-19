#!/usr/bin/env python3
"""
ALi LCD Device Minimal Communication

This script focuses on getting a stable connection to the device and maintaining
it with minimal commands, before attempting to send any complex frames.
"""

import os
import sys
import time
import argparse
import logging

# Add the src directory to the path so we can import ali_lcd_device
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

# Import required modules
from ali_lcd_device.device import ALiLCDDevice
from ali_lcd_device.lifecycle import DeviceLifecycleState
from ali_lcd_device.commands import create_test_unit_ready, create_inquiry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def stabilize_connection(device, frames_dir=None):
    """
    Establish a stable connection with the device.
    
    Args:
        device (ALiLCDDevice): The device instance
        frames_dir (str): Directory containing binary frames
    """
    # Connect to the device
    logger.info("Connecting to device")
    device.connect()
    
    # Wait for Connected state
    logger.info("Waiting for device to reach Connected state (60 seconds)...")
    if not device._wait_for_connected_state(timeout=60):
        logger.warning("Failed to reach Connected state within timeout")
        return False
    
    logger.info(f"Current device state: {device.lifecycle_state}")
    
    # Once in Connected state, just maintain the connection with basic commands
    if device.lifecycle_state == DeviceLifecycleState.CONNECTED:
        logger.info("Maintaining Connected state with basic commands...")
        
        # Send regular TEST UNIT READY commands to keep the connection alive
        stable_seconds = 0
        start_time = time.time()
        keep_alive_count = 0
        inquiry_count = 0
        
        try:
            while stable_seconds < 30:  # Maintain stable connection for 30 seconds
                # Send TEST UNIT READY every second
                try:
                    success, _ = device._test_unit_ready()
                    keep_alive_count += 1
                    
                    # Every 5 commands, send an INQUIRY
                    if keep_alive_count % 5 == 0:
                        logger.info(f"Sending INQUIRY command ({inquiry_count})")
                        inquiry_success, _, inquiry_data = device._inquiry()
                        if inquiry_success and inquiry_data:
                            inquiry_count += 1
                            logger.info(f"INQUIRY successful: {inquiry_data[:16].hex()}")
                    
                    # Log status periodically
                    if keep_alive_count % 10 == 0:
                        logger.info(f"Maintaining connection: {keep_alive_count} commands sent, state: {device.lifecycle_state}")
                    
                    # Update stable connection time
                    stable_seconds = time.time() - start_time
                    
                    # Small delay between commands
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.warning(f"Error during keep-alive: {e}")
                    time.sleep(1)
            
            logger.info(f"Successfully maintained stable connection for {stable_seconds:.1f} seconds")
            return True
            
        except KeyboardInterrupt:
            logger.info("Operation interrupted by user")
            return False
    
    return False

def try_simple_commands(device):
    """
    Try sending simple commands to the device.
    """
    logger.info("Trying simple commands...")
    
    # First, just send some TEST UNIT READY commands
    for i in range(5):
        try:
            logger.info(f"Sending TEST UNIT READY command {i+1}/5")
            success, tag_mismatch = device._test_unit_ready()
            logger.info(f"Result: {'Success' if success else 'Failed'}, Tag mismatch: {tag_mismatch}")
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error sending TEST UNIT READY: {e}")
    
    # Try an INQUIRY command
    try:
        logger.info("Sending INQUIRY command")
        success, tag_mismatch, inquiry_data = device._inquiry()
        if success and inquiry_data:
            logger.info(f"INQUIRY successful: {inquiry_data[:16].hex()}")
            vendor = inquiry_data[8:16].decode('ascii', errors='replace').strip()
            product = inquiry_data[16:32].decode('ascii', errors='replace').strip()
            logger.info(f"Vendor: {vendor}, Product: {product}")
    except Exception as e:
        logger.error(f"Error sending INQUIRY: {e}")
    
    # Try getting sense data
    try:
        logger.info("Sending REQUEST SENSE command")
        from ali_lcd_device.commands import create_request_sense
        cmd, data_length, direction = create_request_sense()
        success, tag_mismatch, sense_data = device._send_command(cmd, data_length, direction)
        if success and sense_data:
            logger.info(f"REQUEST SENSE successful: {sense_data.hex()}")
            sense_key = sense_data[2] & 0x0F
            asc = sense_data[12] if len(sense_data) > 12 else 0
            ascq = sense_data[13] if len(sense_data) > 13 else 0
            logger.info(f"Sense Key: {sense_key}, ASC: {asc}, ASCQ: {ascq}")
    except Exception as e:
        logger.error(f"Error sending REQUEST SENSE: {e}")

def main():
    parser = argparse.ArgumentParser(description='ALi LCD Device Minimal Communication')
    parser.add_argument('--frames_dir', help='Directory containing frame binary files')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()
    
    # Set log level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("Starting minimal communication test")
    
    try:
        # Create device instance
        device = ALiLCDDevice()
        
        # Establish and maintain a stable connection
        if stabilize_connection(device, args.frames_dir):
            # If we've maintained a stable connection, try some simple commands
            try_simple_commands(device)
            
            # Now wait for user input before proceeding
            input("\nPress Enter to proceed with display initialization or Ctrl+C to exit...\n")
            
            # Try to initialize the display
            logger.info("Initializing display")
            if device.initialize_display():
                logger.info("Display initialized successfully")
                
                # Wait for user input before proceeding
                input("\nPress Enter to try sending a frame or Ctrl+C to exit...\n")
                
                # Try to send a simple test pattern
                logger.info("Sending a test pattern")
                if args.frames_dir and os.path.exists(args.frames_dir):
                    files = [f for f in os.listdir(args.frames_dir) if f.endswith('.bin')]
                    if files:
                        first_frame = os.path.join(args.frames_dir, files[0])
                        logger.info(f"Sending frame: {first_frame}")
                        
                        # Read the frame data
                        with open(first_frame, 'rb') as f:
                            frame_data = f.read()
                        
                        # Send display image command
                        from ali_lcd_device.commands import create_f5_display_image_command
                        cmd, data_length, direction = create_f5_display_image_command(width=480, height=480, x=0, y=0)
                        success, tag_mismatch, _ = device._send_command(cmd, len(frame_data), direction, frame_data)
                        
                        if success:
                            logger.info("Frame sent successfully")
                        else:
                            logger.warning(f"Failed to send frame (status != 0, tag_mismatch: {tag_mismatch})")
                    else:
                        logger.warning("No frame files found")
                else:
                    logger.warning("No frames directory specified")
            else:
                logger.warning("Failed to initialize display")
        
    except KeyboardInterrupt:
        logger.info("Operation interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        # Close the device connection
        if 'device' in locals():
            logger.info("Closing device connection")
            device.close()
    
    logger.info("Test completed")

if __name__ == '__main__':
    main()
