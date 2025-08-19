#!/usr/bin/env python3
"""
Improved test script for ALi LCD device with more detailed error handling
and debugging for display initialization.
"""

import sys
import os
import time
import logging
import argparse
import numpy as np
from PIL import Image

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from ali_lcd_device.device import ALiLCDDevice
from ali_lcd_device.lifecycle import DeviceLifecycleState
from ali_lcd_device.usb_comm import USBError, TagMismatchError, PipeError

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_image(width=320, height=320):
    """Create a simple test image with colored rectangles."""
    # Create blank RGB image
    image = Image.new('RGB', (width, height), color=(0, 0, 0))
    
    # Calculate dimensions
    rect_width = width // 4
    rect_height = height // 4
    
    colors = [
        (255, 0, 0),    # Red
        (0, 255, 0),    # Green
        (0, 0, 255),    # Blue
        (255, 255, 0),  # Yellow
        (255, 0, 255),  # Magenta
        (0, 255, 255),  # Cyan
        (255, 255, 255),# White
        (128, 128, 128) # Gray
    ]
    
    # Draw colored rectangles
    for i in range(8):
        x = (i % 4) * rect_width
        y = (i // 4) * rect_height
        color = colors[i]
        
        for px in range(x, x + rect_width):
            for py in range(y, y + rect_height):
                if px < width and py < height:
                    image.putpixel((px, py), color)
    
    # Draw a border
    for i in range(width):
        for j in range(height):
            if i < 3 or i >= width-3 or j < 3 or j >= height-3:
                image.putpixel((i, j), (255, 255, 255))
    
    # Save and return path
    temp_path = os.path.join(os.path.dirname(__file__), 'temp_test_image.png')
    image.save(temp_path)
    return temp_path

def direct_initialize_display(device):
    """
    Directly send the raw F5 init command with detailed debugging.
    This bypasses the higher level methods to get more insight.
    """
    logger.info("Attempting direct display initialization")
    
    # Manual F5 init command construction
    cmd = bytearray([0xF5, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    data_length = 0
    direction = 'out'
    
    # Try with different delays and retries
    for attempt in range(5):
        logger.info(f"Direct init attempt {attempt+1}/5")
        
        # Send command and check response
        success, tag_mismatch, response = device._send_command(cmd, data_length, direction)
        
        if success:
            logger.info("Direct display init succeeded!")
            return True
        else:
            logger.warning(f"Direct init attempt {attempt+1} failed")
            
            # Request sense data to see what went wrong
            sense_cmd = bytearray([0x03, 0x00, 0x00, 0x00, 0x12, 0x00])
            sense_success, _, sense_data = device._send_command(sense_cmd, 18, 'in')
            
            if sense_success and sense_data:
                logger.info(f"Sense data: {', '.join([f'0x{b:02x}' for b in sense_data])}")
                
            # Add a delay between attempts
            time.sleep(0.5)
    
    logger.error("All direct initialization attempts failed")
    return False

def direct_set_mode(device, mode=5):
    """
    Directly send the raw F5 mode command with detailed debugging.
    """
    logger.info(f"Attempting to directly set mode to {mode}")
    
    # Manual F5 set mode command construction
    cmd = bytearray([0xF5, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    data = bytearray([mode, 0x00, 0x00, 0x00])
    data_length = len(data)
    direction = 'out'
    
    # Try with different delays and retries
    for attempt in range(5):
        logger.info(f"Direct set mode attempt {attempt+1}/5")
        
        # Send command and check response
        success, tag_mismatch, response = device._send_command(cmd, data_length, direction, data)
        
        if success:
            logger.info("Direct set mode succeeded!")
            return True
        else:
            logger.warning(f"Direct set mode attempt {attempt+1} failed")
            time.sleep(0.5)
    
    logger.error("All set mode attempts failed")
    return False

def direct_animation_control(device, start_animation=False):
    """
    Directly send the raw F5 animation control command with detailed debugging.
    """
    logger.info(f"Attempting to directly {'start' if start_animation else 'stop'} animation")
    
    # Manual F5 animation control command construction
    cmd = bytearray([0xF5, 0x10, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    data = bytearray([0x01 if start_animation else 0x00])
    data_length = len(data)
    direction = 'out'
    
    # Send command and check response
    success, tag_mismatch, response = device._send_command(cmd, data_length, direction, data)
    
    if success:
        logger.info("Animation control succeeded!")
    else:
        logger.warning("Animation control failed")
    
    return success

def direct_clear_screen(device):
    """
    Directly send the raw F5 clear screen command with detailed debugging.
    """
    logger.info("Attempting to directly clear screen")
    
    # Manual F5 clear screen command construction
    cmd = bytearray([0xF5, 0xA0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    data_length = 0
    direction = 'out'
    
    # Send command and check response
    success, tag_mismatch, response = device._send_command(cmd, data_length, direction)
    
    if success:
        logger.info("Clear screen succeeded!")
    else:
        logger.warning("Clear screen failed")
    
    return success

def direct_display_image(device, image_path, x=0, y=0):
    """
    Directly send the raw F5 display image command with detailed debugging.
    """
    from ali_lcd_device.image_utils import convert_image_to_rgb565
    from ali_lcd_device.commands import create_image_header
    
    logger.info(f"Attempting to directly display image {image_path}")
    
    try:
        # Convert image to RGB565
        image_data, width, height = convert_image_to_rgb565(image_path)
        
        # Create image header
        header = create_image_header(width, height, x, y)
        
        # Combine header and image data
        data = header + image_data
        
        # Manual F5 display image command construction
        cmd = bytearray([0xF5, 0xB0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        data_length = len(data)
        direction = 'out'
        
        logger.info(f"Sending display command for {width}x{height} image at ({x},{y})")
        logger.info(f"Header: {', '.join([f'0x{b:02x}' for b in header])}")
        logger.info(f"Data size: {len(image_data)} bytes")
        
        # Send in chunks if necessary
        max_chunk = 16384  # 16KB chunks
        
        if len(data) > max_chunk:
            logger.info(f"Image data too large, sending in chunks")
            
            chunks = [data[i:i+max_chunk] for i in range(0, len(data), max_chunk)]
            logger.info(f"Splitting into {len(chunks)} chunks")
            
            for i, chunk in enumerate(chunks):
                logger.info(f"Sending chunk {i+1}/{len(chunks)} ({len(chunk)} bytes)")
                success, tag_mismatch, response = device._send_command(cmd, len(chunk), direction, chunk)
                
                if not success:
                    logger.error(f"Chunk {i+1} failed")
                    return False
                
                logger.info(f"Chunk {i+1} sent successfully")
                time.sleep(0.2)  # Small delay between chunks
                
            return True
        else:
            # Send command and check response
            success, tag_mismatch, response = device._send_command(cmd, data_length, direction, data)
            
            if success:
                logger.info("Display image succeeded!")
            else:
                logger.warning("Display image failed")
            
            return success
            
    except Exception as e:
        logger.error(f"Error displaying image: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='ALi LCD device display test with improved error handling')
    parser.add_argument('--image-path', help='Path to image file to display')
    parser.add_argument('--wait-for-stable', action='store_true', help='Wait for device to reach stable state')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode with more verbose output')
    parser.add_argument('--direct', action='store_true', help='Use direct command mode for more detailed debugging')
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("Starting improved ALi LCD device display test")
    
    # Use provided image or create a test image
    image_path = args.image_path
    if not image_path:
        logger.info("No image provided, creating test image")
        image_path = create_test_image()
        logger.info(f"Created test image at {image_path}")
    
    # Initialize device
    device = None
    try:
        logger.info("Connecting to ALi LCD device")
        device = ALiLCDDevice()
        device.connect(wait_for_stable=args.wait_for_stable)
        
        # Check the lifecycle state
        logger.info(f"Device is in {device.lifecycle_state.name} state")
        
        if device.lifecycle_state != DeviceLifecycleState.CONNECTED:
            logger.info("Waiting for device to reach Connected state")
            if not device._wait_for_connected_state():
                logger.warning("Could not reach Connected state, attempting anyway")
        
        # Use direct command mode if requested
        if args.direct:
            logger.info("Using direct command mode")
            
            # Perform direct initialization
            if not direct_initialize_display(device):
                logger.error("Direct display initialization failed")
                return
            
            # Set mode
            if not direct_set_mode(device, mode=5):
                logger.error("Failed to set display mode")
                return
            
            # Stop animation
            if not direct_animation_control(device, start_animation=False):
                logger.warning("Failed to stop animation, continuing anyway")
            
            # Clear screen
            if not direct_clear_screen(device):
                logger.warning("Failed to clear screen, continuing anyway")
            
            # Display image
            if not direct_display_image(device, image_path):
                logger.error("Failed to display image")
                return
            
        else:
            # Use the high-level methods
            logger.info("Initializing the display")
            if not device.initialize_display():
                logger.error("Failed to initialize display")
                return
            
            logger.info("Stopping animation")
            device.control_animation(False)
            
            logger.info("Setting display mode")
            device.set_display_mode(5)
            
            logger.info("Clearing screen")
            device.clear_screen()
            
            logger.info(f"Displaying image: {image_path}")
            if not device.display_image(image_path):
                logger.error("Failed to display image")
                return
        
        logger.info("Display test completed successfully")
        
        # Keep connection open for a moment to observe the display
        logger.info("Keeping connection active for 10 seconds...")
        for i in range(10):
            device._test_unit_ready()  # Send keep-alive command
            time.sleep(1)
        
    except Exception as e:
        logger.error(f"Error during display test: {e}")
    finally:
        if device:
            logger.info("Closing device connection")
            device.close()
            logger.info("Test complete")

if __name__ == "__main__":
    main()
