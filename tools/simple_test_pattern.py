#!/usr/bin/env python3
"""
Simple script to display a test pattern on the ALi LCD device
"""

import sys
import os
import logging
import time
from PIL import Image, ImageDraw, ImageFont

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import the device class
try:
    from src.ali_lcd_device.device import ALiLCDDevice
except ImportError as e:
    print(f"Error importing ALiLCDDevice: {e}")
    sys.exit(1)

def create_test_pattern():
    """Create a simple test pattern image"""
    # Create a new RGB image with white background
    width, height = 480, 272
    image = Image.new('RGB', (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Draw colored rectangles
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]
    rect_width = width // len(colors)
    
    for i, color in enumerate(colors):
        draw.rectangle([i * rect_width, 0, (i + 1) * rect_width, height // 3], fill=color)
    
    # Draw a white rectangle in the middle
    draw.rectangle([50, height // 3 + 20, width - 50, height - 20], outline=(255, 255, 255), width=2)
    
    # Add text
    try:
        font = ImageFont.load_default()
        text = "ALi LCD Display Test"
        text_width = draw.textlength(text, font=font)
        draw.text(((width - text_width) // 2, height // 2), text, font=font, fill=(255, 255, 255))
        
        # Add timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        draw.text((10, height - 20), timestamp, fill=(255, 255, 255))
    except Exception as e:
        print(f"Error drawing text: {e}")
    
    # Save the image to a temporary file
    temp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_pattern.png")
    try:
        image.save(temp_file)
        print(f"Test pattern saved to {temp_file}")
        return temp_file
    except Exception as e:
        print(f"Error saving image: {e}")
        return None

def main():
    """Main function to display the test pattern"""
    print("Starting ALi LCD test pattern display")
    
    # Create test pattern
    image_path = create_test_pattern()
    if not image_path:
        print("Failed to create test pattern")
        return
    
    # Connect to the device
    try:
        print("Connecting to ALi LCD device...")
        device = ALiLCDDevice()
        device.connect(wait_for_stable=True)
        print("Connected to device")
        
        # Initialize the display
        print("Initializing display...")
        device.initialize_display()
        print("Display initialized")
        
        # Display the image
        print("Displaying test pattern...")
        device.display_image(image_path)
        print("Test pattern displayed")
        
        # Keep the connection open for a while
        print("Keeping image displayed for 30 seconds...")
        for i in range(30):
            time.sleep(1)
            sys.stdout.write(f"\rTime remaining: {30-i} seconds")
            sys.stdout.flush()
        print("\nClosing connection")
        
        # Close the connection
        device.close()
        print("Connection closed")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
