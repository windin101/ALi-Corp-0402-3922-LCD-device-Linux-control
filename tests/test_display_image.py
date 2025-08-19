#!/usr/bin/env python3
"""
Test script for ALi LCD device display functionality.
This script:
1. Puts the device in a state ready to receive data
2. Sends a simple test image formatted in the correct way
"""

import os
import sys
import time
import logging
import argparse
from PIL import Image, ImageDraw

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from ali_lcd_device.device import ALiLCDDevice
from ali_lcd_device.lifecycle import DeviceLifecycleState
from ali_lcd_device.image_utils import convert_image_to_rgb565

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_image(size=(320, 320), filename='test_image.png'):
    """
    Create a simple test image with colored rectangles and text.
    
    Args:
        size (tuple): Width and height of the image
        filename (str): Output filename
        
    Returns:
        str: Path to the created image
    """
    # Create a new image with white background
    img = Image.new('RGB', size, color='white')
    draw = ImageDraw.Draw(img)
    
    # Draw a red rectangle
    draw.rectangle([(10, 10), (size[0]//2 - 10, size[1]//2 - 10)], fill='red')
    
    # Draw a green rectangle
    draw.rectangle([(size[0]//2 + 10, 10), (size[0] - 10, size[1]//2 - 10)], fill='green')
    
    # Draw a blue rectangle
    draw.rectangle([(10, size[1]//2 + 10), (size[0]//2 - 10, size[1] - 10)], fill='blue')
    
    # Draw a yellow rectangle
    draw.rectangle([(size[0]//2 + 10, size[1]//2 + 10), (size[0] - 10, size[1] - 10)], fill='yellow')
    
    # Save the image
    filepath = os.path.join(os.path.dirname(__file__), filename)
    img.save(filepath)
    logger.info(f"Created test image: {filepath}")
    
    return filepath

def test_display_image(args):
    """
    Test the display functionality of the ALi LCD device.
    
    Args:
        args: Command line arguments
    """
    logger.info("Starting ALi LCD device display test")
    
    # Create device instance
    device = ALiLCDDevice(vendor_id=0x0402, product_id=0x3922)
    
    try:
        # Connect to the device
        logger.info("Connecting to ALi LCD device")
        device.connect(wait_for_stable=args.wait_for_stable)
        
        # Wait for device to be in the appropriate state
        if device.lifecycle_state != DeviceLifecycleState.CONNECTED and args.wait_for_stable:
            logger.info("Waiting for device to reach Connected state")
            device._wait_for_connected_state(timeout=70)
        
        # Report device state
        logger.info(f"Device is in {device.lifecycle_state.name} state")
        
        # Initialize the display
        logger.info("Initializing the display")
        success = device.initialize_display()
        if not success:
            logger.error("Failed to initialize display")
            return False
        
        # Prepare for image display
        logger.info("Preparing for image display")
        
        # Stop any active animation
        logger.info("Stopping animation")
        device.control_animation(False)
        
        # Set display mode
        logger.info("Setting display mode")
        device.set_display_mode(5)  # Standard mode
        
        # Clear the screen
        logger.info("Clearing screen")
        device.clear_screen()
        
        # Create or use test image
        if args.image_path:
            image_path = args.image_path
            logger.info(f"Using provided image: {image_path}")
        else:
            image_path = create_test_image()
        
        # Display the image
        logger.info("Displaying test image")
        success = device.display_image(image_path, x=0, y=0)
        
        if success:
            logger.info("Successfully displayed the image!")
        else:
            logger.error("Failed to display the image")
        
        return success
    
    except Exception as e:
        logger.error(f"Error during display test: {e}")
        return False
    
    finally:
        # Clean up
        logger.info("Closing device connection")
        device.close()

def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(description='Test ALi LCD device display functionality')
    parser.add_argument('--image-path', type=str, help='Path to test image (will create one if not provided)')
    parser.add_argument('--wait-for-stable', action='store_true', help='Wait for device to reach stable state')
    
    args = parser.parse_args()
    
    success = test_display_image(args)
    
    if success:
        logger.info("Display test completed successfully")
        return 0
    else:
        logger.error("Display test failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
