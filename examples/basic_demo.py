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
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger('ali_lcd_device').setLevel(logging.DEBUG)
    
    try:
        # Create device instance
        device = ALiLCDDevice()
        
        # Connect to the device
        print("Connecting to ALi LCD device...")
        print("This will take about 60 seconds to reach the Connected state.")
        print("Command failures during the Animation state are normal and expected.")
        print("Press Ctrl+C at any time to exit.")
        
        try:
            device.connect(wait_for_stable=True)
        except KeyboardInterrupt:
            print("\nConnection process interrupted by user.")
            device.close()
            return
            
        # Check if we reached the Connected state
        if device.lifecycle_state != device.lifecycle_manager.state:
            print(f"Warning: Internal state inconsistency detected.")
            print(f"Device state: {device.lifecycle_state}, Manager state: {device.lifecycle_manager.state}")
            
        if device.lifecycle_state.name == 'CONNECTED':
            print("Successfully reached Connected state!")
        else:
            print(f"Warning: Device is in {device.lifecycle_state.name} state, not Connected.")
            print("Proceeding anyway, but commands may fail.")
        
        # Initialize the display
        print("\nInitializing display...")
        if device.initialize_display():
            print("Display initialized successfully.")
        else:
            print("Warning: Display initialization may have issues.")
        
        # Clear the screen
        print("\nClearing screen...")
        if device.clear_screen():
            print("Screen cleared successfully.")
        else:
            print("Warning: Screen clear command may have issues.")
        
        # Display content
        if args.image:
            # Display image from file
            print(f"\nDisplaying image: {args.image}")
            if device.display_image(args.image):
                print("Image displayed successfully.")
            else:
                print("Warning: Image display may have issues.")
        else:
            # Display test pattern
            print(f"\nDisplaying {args.pattern} pattern...")
            try:
                display_test_pattern(device, args.pattern, args.width, args.height)
                print("Pattern displayed successfully.")
            except Exception as e:
                print(f"Error displaying pattern: {str(e)}")
        
        print("\nDisplay complete. Press Ctrl+C to exit.")
        
        # Keep the program running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nExiting...")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
    finally:
        # Close the device connection
        if 'device' in locals():
            print("Closing device connection...")
            device.close()
            print("Connection closed.")

if __name__ == "__main__":
    main()
