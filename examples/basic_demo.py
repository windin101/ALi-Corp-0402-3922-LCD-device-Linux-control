#!/usr/bin/env python3
"""
Basic example showing how to connect to the ALi LCD device,
initialize it, and display a test pattern.
"""

import sys
import os
import logging
import time
import argparse

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from ali_lcd_device.device import ALiLCDDevice
from ali_lcd_device.image_utils import (
    create_gradient_pattern, create_checkerboard_pattern, create_color_bars
)
from ali_lcd_device.commands import create_image_header

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def display_test_pattern(device, pattern_type, width=320, height=320):
    """
    Display a test pattern on the device.
    
    Args:
        device: The ALi LCD device
        pattern_type: Type of pattern ('gradient', 'checkerboard', 'colorbars')
        width: Display width
        height: Display height
    """
    # Generate the pattern
    if pattern_type == 'gradient':
        pattern_data = create_gradient_pattern(width, height)
    elif pattern_type == 'checkerboard':
        pattern_data = create_checkerboard_pattern(width, height)
    elif pattern_type == 'colorbars':
        pattern_data = create_color_bars(width, height)
    else:
        raise ValueError(f"Unknown pattern type: {pattern_type}")
    
    # Create header
    header = create_image_header(width, height, 0, 0)
    
    # Combine header and pattern data
    data = header + pattern_data
    
    # Send display command
    from ali_lcd_device.commands import create_f5_display_image_command
    cmd, data_length, direction = create_f5_display_image_command(width, height, 0, 0)
    
    # Send the command
    device._send_command(cmd, len(data), direction, data)

def main():
    parser = argparse.ArgumentParser(description='ALi LCD Device Demo')
    parser.add_argument('--pattern', choices=['gradient', 'checkerboard', 'colorbars'],
                        default='gradient', help='Test pattern to display')
    parser.add_argument('--image', help='Path to image file to display')
    parser.add_argument('--width', type=int, default=320, help='Display width')
    parser.add_argument('--height', type=int, default=320, help='Display height')
    args = parser.parse_args()
    
    try:
        # Create device instance
        device = ALiLCDDevice()
        
        # Connect to the device
        print("Connecting to ALi LCD device...")
        device.connect(wait_for_stable=True)
        
        # Initialize the display
        print("Initializing display...")
        device.initialize_display()
        
        # Clear the screen
        print("Clearing screen...")
        device.clear_screen()
        
        # Display content
        if args.image:
            # Display image from file
            print(f"Displaying image: {args.image}")
            device.display_image(args.image)
        else:
            # Display test pattern
            print(f"Displaying {args.pattern} pattern...")
            display_test_pattern(device, args.pattern, args.width, args.height)
        
        print("Display complete. Press Ctrl+C to exit.")
        
        # Keep the program running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Exiting...")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
    finally:
        # Close the device connection
        if 'device' in locals():
            device.close()

if __name__ == "__main__":
    main()
