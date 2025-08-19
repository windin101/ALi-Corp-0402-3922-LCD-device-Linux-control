#!/usr/bin/env python3
"""
Test displaying an image on the ALi LCD device
"""

import sys
import os
import logging
import time
import argparse
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the device class
from src.ali_lcd_device.device import ALiLCDDevice
from src.ali_lcd_device.lifecycle import DeviceLifecycleState

def create_test_image(text="Hello, World!", size=(480, 272), color=(255, 255, 255), bg_color=(0, 0, 0)):
    """Create a test image with text"""
    image = Image.new('RGB', size, bg_color)
    draw = ImageDraw.Draw(image)
    
    # Try to load a font, or use default
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 24)
    except IOError:
        font = ImageFont.load_default()
    
    # Calculate text position
    text_width = draw.textlength(text, font=font)
    text_height = 24  # Approximate height
    position = ((size[0] - text_width) // 2, (size[1] - text_height) // 2)
    
    # Draw text
    draw.text(position, text, font=font, fill=color)
    
    # Add timestamp
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    draw.text((10, size[1] - 20), timestamp, font=font, fill=color)
    
    # Add decorative elements
    draw.rectangle((10, 10, size[0] - 10, size[1] - 10), outline=color)
    
    return image

def display_image_on_device(image_path=None, text=None):
    """Display an image on the ALi LCD device"""
    
    print("\n=== ALi LCD Device Image Display Test ===\n")
    
    # Create or load image
    if image_path and os.path.exists(image_path):
        print(f"Loading image from {image_path}")
        image = Image.open(image_path).convert('RGB')
        
        # Resize image to fit LCD if needed
        if image.size != (480, 272):
            print(f"Resizing image from {image.size} to (480, 272)")
            image = image.resize((480, 272), Image.Resampling.LANCZOS)
    else:
        if text is None:
            text = "ALi LCD Test"
        print(f"Creating test image with text: {text}")
        image = create_test_image(text=text)
    
    # Save temporary image
    temp_path = os.path.join(os.path.dirname(__file__), "temp_image.png")
    image.save(temp_path)
    print(f"Saved temporary image to {temp_path}")
    
    # Connect to device and display image
    device = ALiLCDDevice()
    print(f"Created device instance with VID:PID = {device.vendor_id:04x}:{device.product_id:04x}")
    
    try:
        # Connect and wait for stable state
        print("\nConnecting to device and waiting for Connected state...")
        device.connect(wait_for_stable=True)
        print(f"Connected. Current state: {device.lifecycle_manager.get_state().name}")
        
        # Initialize display
        print("\nInitializing display...")
        device.initialize_display()
        print("Display initialized")
        
        # Display the image
        print("\nDisplaying image...")
        device.display_image(temp_path)
        print("Image displayed successfully")
        
        # Keep the image displayed for a while
        print("\nKeeping image displayed for 10 seconds...")
        for i in range(10):
            time.sleep(1)
            print(f"Time remaining: {10-i} seconds")
        
        # Clean up
        print("\nClosing connection...")
        device.close()
        print("Connection closed")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n=== Image Display Test Completed ===")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Display an image on the ALi LCD device")
    parser.add_argument("--image", "-i", help="Path to image file to display")
    parser.add_argument("--text", "-t", help="Text to display on a generated test image")
    
    args = parser.parse_args()
    display_image_on_device(image_path=args.image, text=args.text)
