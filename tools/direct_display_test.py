#!/usr/bin/env python3
"""
Direct display test that bypasses some error checks
"""

import sys
import os
import time
import logging
from PIL import Image, ImageDraw, ImageFont
import struct

# Configure logging
logging.basicConfig(level=logging.INFO)

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import necessary modules
try:
    import usb.core
    import usb.util
    from src.ali_lcd_device.device import ALiLCDDevice
    from src.ali_lcd_device.commands import (
        create_f5_init_command, create_f5_display_image_command,
        create_image_header
    )
    from src.ali_lcd_device.image_utils import convert_image_to_rgb565
except ImportError as e:
    print(f"Error importing required modules: {e}")
    sys.exit(1)

# Vendor and product IDs for the ALi LCD device
VENDOR_ID = 0x0402
PRODUCT_ID = 0x3922

def create_test_pattern():
    """Create a colorful test pattern"""
    width, height = 480, 272
    image = Image.new('RGB', (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Draw color bars
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]
    bar_width = width // len(colors)
    
    for i, color in enumerate(colors):
        draw.rectangle([i * bar_width, 0, (i + 1) * bar_width, height // 3], fill=color)
    
    # Draw white rectangle in the middle
    draw.rectangle([50, height // 3 + 20, width - 50, height - 20], outline=(255, 255, 255), width=2)
    
    # Add text
    try:
        font = ImageFont.load_default()
        text = "DIRECT DISPLAY TEST"
        draw.text((width // 2 - 80, height // 2), text, fill=(255, 255, 255))
        
        # Add timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        draw.text((10, height - 20), timestamp, fill=(255, 255, 255))
    except Exception as e:
        print(f"Error drawing text: {e}")
    
    # Save the image to a temporary file
    temp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "direct_test.png")
    image.save(temp_file)
    print(f"Test pattern saved to {temp_file}")
    return temp_file

def send_raw_command(device, command, data_length=0, data=None):
    """Send a raw command to the device"""
    try:
        # Command phase
        device.ep_out.write(command)
        
        # Data phase (if applicable)
        if data and data_length > 0:
            device.ep_out.write(data)
        
        # Status phase
        csw = device.ep_in.read(13)
        
        # Parse status
        status = csw[12]
        return True, status
    except Exception as e:
        print(f"Error sending command: {e}")
        return False, None

def direct_display_test():
    """Test displaying an image directly to the device"""
    print("\n=== ALi LCD Direct Display Test ===\n")
    
    # Create a test pattern
    image_path = create_test_pattern()
    
    # Connect to the device
    try:
        # Find the device
        device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if device is None:
            print("ALi LCD device not found!")
            return False
        
        print(f"Found ALi LCD device: {device}")
        
        # Create ALiLCDDevice instance
        ali_device = ALiLCDDevice()
        
        # Connect to the device
        print("Connecting to device...")
        ali_device.connect(wait_for_stable=True)
        print(f"Connected to device in state: {ali_device.lifecycle_manager.get_state().name}")
        
        # Run display initialization sequence (regardless of errors)
        print("\nSending display initialization commands...")
        cmd, data_length, direction = create_f5_init_command()
        success, status = send_raw_command(ali_device, cmd, data_length)
        print(f"F5 init command result: success={success}, status={status}")
        
        # Convert image
        print("\nConverting image to RGB565 format...")
        image_data, width, height = convert_image_to_rgb565(image_path)
        
        # Create image header
        header = create_image_header(width, height, 0, 0)
        
        # Combine header and image data
        data = header + image_data
        
        # Send display image command
        print(f"\nSending display image command for {width}x{height} image...")
        cmd, data_length, direction = create_f5_display_image_command(width, height, 0, 0)
        
        success, status = send_raw_command(ali_device, cmd, len(data), data)
        print(f"Display image command result: success={success}, status={status}")
        
        # Keep connection open for a while
        print("\nKeeping image displayed for 30 seconds...")
        for i in range(30):
            time.sleep(1)
            sys.stdout.write(f"\rTime remaining: {30-i} seconds")
            sys.stdout.flush()
            
            # Send test unit ready every 5 seconds to keep connection alive
            if i % 5 == 0:
                ali_device._test_unit_ready()
        
        print("\nClosing connection...")
        ali_device.close()
        print("Connection closed")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    direct_display_test()
