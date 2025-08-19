#!/usr/bin/env python3
"""
Example of using the ALi LCD API to display an image
"""

import os
import sys
import argparse
from PIL import Image, ImageDraw, ImageFont
import ali_lcd_api

def create_test_image(output_path, width=480, height=272):
    """Create a test image for the LCD display"""
    image = Image.new('RGB', (width, height), color='black')
    draw = ImageDraw.Draw(image)
    
    # Draw colored rectangles in the corners
    colors = ['red', 'green', 'blue', 'yellow']
    rect_size = 60
    
    # Top-left: Red
    draw.rectangle([(0, 0), (rect_size, rect_size)], fill=colors[0])
    
    # Top-right: Green
    draw.rectangle([(width - rect_size, 0), (width, rect_size)], fill=colors[1])
    
    # Bottom-left: Blue
    draw.rectangle([(0, height - rect_size), (rect_size, height)], fill=colors[2])
    
    # Bottom-right: Yellow
    draw.rectangle([(width - rect_size, height - rect_size), 
                    (width, height)], fill=colors[3])
    
    # Draw white crosshairs
    draw.line([(0, height // 2), (width, height // 2)], fill='white', width=2)
    draw.line([(width // 2, 0), (width // 2, height)], fill='white', width=2)
    
    # Draw text
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 24)
    except IOError:
        font = ImageFont.load_default()
    
    draw.text((width // 2 - 140, height // 2 - 50), 
              "ALi LCD Test Pattern", fill='white', font=font)
    draw.text((width // 2 - 100, height // 2 + 20), 
              f"{width}x{height}", fill='white', font=font)
    
    # Save the image
    image.save(output_path)
    print(f"Test pattern saved to {output_path}")
    return output_path

def main():
    parser = argparse.ArgumentParser(description='Display an image on the ALi LCD device')
    parser.add_argument('--image', help='Path to the image to display (if not specified, a test pattern will be created)')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    
    args = parser.parse_args()
    
    # Check if running with sudo
    if os.geteuid() != 0:
        print("This script must be run with sudo privileges.")
        sys.exit(1)
    
    # Create or use image
    if args.image:
        image_path = args.image
        if not os.path.exists(image_path):
            print(f"Error: Image file '{image_path}' not found")
            sys.exit(1)
    else:
        # Create a test pattern
        script_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(script_dir, "test_pattern.png")
        create_test_image(image_path)
    
    # Display the image
    print(f"Displaying image '{image_path}' on ALi LCD device...")
    
    try:
        if ali_lcd_api.display_image(image_path, args.debug):
            print("Image displayed successfully")
        else:
            print("Failed to display image")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
