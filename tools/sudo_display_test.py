#!/usr/bin/env python3
"""
Low-level display test with sudo
"""

import usb.core
import usb.util
import time
import sys
import os
import struct
from PIL import Image, ImageDraw, ImageFont

# ALi LCD device identifiers
VENDOR_ID = 0x0402
PRODUCT_ID = 0x3922

# USB constants for BOT protocol
CBW_SIGNATURE = 0x43425355  # 'USBC' in little-endian
CSW_SIGNATURE = 0x53425355  # 'USBS' in little-endian

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
        text = "ALi LCD SUDO TEST"
        draw.text((width // 2 - 80, height // 2), text, fill=(255, 255, 255))
        
        # Add timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        draw.text((10, height - 20), timestamp, fill=(255, 255, 255))
    except Exception as e:
        print(f"Error drawing text: {e}")
    
    # Save the image to a temporary file
    temp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sudo_test.png")
    image.save(temp_file)
    print(f"Test pattern saved to {temp_file}")
    return temp_file

def convert_image_to_rgb565(image_path):
    """Convert an image to RGB565 format"""
    # Open the image
    image = Image.open(image_path).convert('RGB')
    width, height = image.size
    
    # Convert to RGB565
    rgb565_data = bytearray(width * height * 2)
    pixels = image.load()
    
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            
            # Convert to RGB565
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            
            # Store in little-endian
            idx = (y * width + x) * 2
            rgb565_data[idx] = rgb565 & 0xFF
            rgb565_data[idx + 1] = (rgb565 >> 8) & 0xFF
    
    return bytes(rgb565_data), width, height

def create_cbw(tag, data_length, direction, cmd_length, command, lun=0):
    """Create a Command Block Wrapper (CBW)"""
    # Direction flags
    flags = 0
    if direction.lower() == 'in':
        flags = 0x80
    
    # Create CBW
    cbw = (
        CBW_SIGNATURE.to_bytes(4, byteorder='little') +
        tag.to_bytes(4, byteorder='little') +
        data_length.to_bytes(4, byteorder='little') +
        bytes([flags, lun, cmd_length]) +
        command
    )
    
    return cbw

def create_f5_init_command():
    """Create F5 init command"""
    # F5 command (subcommand 0x03 = init)
    command = bytes([0xF5, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    return command

def create_f5_display_image_command(width, height, x=0, y=0):
    """Create F5 display image command"""
    # F5 command (subcommand 0x01 = display image)
    command = bytes([0xF5, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    return command

def create_image_header(width, height, x=0, y=0):
    """Create image header for display command"""
    # Image header format:
    # 2 bytes: X position (little-endian)
    # 2 bytes: Y position (little-endian)
    # 2 bytes: Width (little-endian)
    # 2 bytes: Height (little-endian)
    # 4 bytes: Unknown (always 0)
    
    header = struct.pack("<HHHHI", x, y, width, height, 0)
    return header

def basic_display_test():
    """Run a basic display test"""
    print("\n=== ALi LCD Basic Display Test ===\n")
    
    # Generate test pattern
    image_path = create_test_pattern()
    
    # Find the device
    device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if device is None:
        print("Device not found!")
        return False
    
    print(f"Found device: {device}")
    
    # Reset the device
    try:
        print("Resetting device...")
        device.reset()
        print("Device reset successful")
        time.sleep(2)  # Give it time to re-enumerate
    except Exception as e:
        print(f"Error resetting device: {e}")
        print("Continuing anyway...")
    
    # Try to set configuration
    try:
        print("Setting device configuration...")
        device.set_configuration()
        print("Configuration set successfully")
    except Exception as e:
        print(f"Error setting configuration: {e}")
        print("Continuing anyway...")
    
    # Get configuration
    cfg = device.get_active_configuration()
    
    # Get interface
    interface = cfg[(0, 0)]
    
    # Detach kernel driver if active
    if device.is_kernel_driver_active(interface.bInterfaceNumber):
        print("Detaching kernel driver...")
        device.detach_kernel_driver(interface.bInterfaceNumber)
    
    # Claim interface
    print("Claiming interface...")
    usb.util.claim_interface(device, interface.bInterfaceNumber)
    
    # Find endpoints
    ep_out = None
    ep_in = None
    for ep in interface:
        if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
            ep_out = ep
        elif usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
            ep_in = ep
    
    if ep_out is None or ep_in is None:
        print("Could not find required endpoints")
        return False
    
    print(f"Found endpoints: OUT=0x{ep_out.bEndpointAddress:02x}, IN=0x{ep_in.bEndpointAddress:02x}")
    
    try:
        # Step 1: Send F5 init command
        print("\nStep 1: Sending F5 init command...")
        
        f5_init = create_f5_init_command()
        cbw = create_cbw(tag=1, data_length=0, direction='none', cmd_length=16, command=f5_init)
        
        print(f"CBW: {' '.join([f'{b:02x}' for b in cbw])}")
        ep_out.write(cbw)
        
        # Read CSW
        csw = ep_in.read(13)
        csw_hex = ' '.join([f'{b:02x}' for b in csw])
        print(f"CSW: {csw_hex}")
        
        # Parse CSW
        csw_status = csw[12]
        print(f"Command status: {csw_status}")
        
        # Step 2: Convert image
        print("\nStep 2: Converting image...")
        image_data, width, height = convert_image_to_rgb565(image_path)
        print(f"Converted image: {width}x{height}, {len(image_data)} bytes")
        
        # Create image header
        header = create_image_header(width, height, 0, 0)
        print(f"Image header: {' '.join([f'{b:02x}' for b in header])}")
        
        # Combine header and image data
        data = header + image_data
        data_length = len(data)
        
        # Step 3: Send display image command
        print("\nStep 3: Sending display image command...")
        
        f5_display = create_f5_display_image_command(width, height)
        cbw = create_cbw(tag=2, data_length=data_length, direction='out', cmd_length=16, command=f5_display)
        
        print(f"CBW: {' '.join([f'{b:02x}' for b in cbw])}")
        ep_out.write(cbw)
        
        # Send image data
        print(f"Sending {data_length} bytes of image data...")
        # Send in chunks to avoid buffer issues
        chunk_size = 4096
        for i in range(0, data_length, chunk_size):
            chunk = data[i:i+chunk_size]
            ep_out.write(chunk)
        
        # Read CSW
        csw = ep_in.read(13)
        csw_hex = ' '.join([f'{b:02x}' for b in csw])
        print(f"CSW: {csw_hex}")
        
        # Parse CSW
        csw_status = csw[12]
        print(f"Command status: {csw_status}")
        
        print("\nImage display command complete!")
        
        # Keep the connection open for a while
        print("\nKeeping image displayed for 30 seconds...")
        for i in range(30):
            time.sleep(1)
            sys.stdout.write(f"\rTime remaining: {30-i} seconds")
            sys.stdout.flush()
            
            # Send test unit ready command every 5 seconds to keep connection alive
            if i % 5 == 0:
                # Test Unit Ready command
                cmd = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
                cbw = create_cbw(tag=i+3, data_length=0, direction='none', cmd_length=6, command=cmd)
                ep_out.write(cbw)
                csw = ep_in.read(13)
        
        # Release interface
        print("\nReleasing interface...")
        usb.util.release_interface(device, interface.bInterfaceNumber)
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Try to release interface
        try:
            usb.util.release_interface(device, interface.bInterfaceNumber)
        except:
            pass
            
        return False

if __name__ == "__main__":
    basic_display_test()
