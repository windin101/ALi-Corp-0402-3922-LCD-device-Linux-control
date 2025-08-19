#!/usr/bin/env python3
"""
Final robust test for ALi LCD device
"""

import usb.core
import usb.util
import time
import sys
import os
import struct
from PIL import Image, ImageDraw, ImageFont
import random

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
    
    # Draw color bars with random colors
    colors = []
    for _ in range(6):
        colors.append((random.randint(100, 255), random.randint(100, 255), random.randint(100, 255)))
    
    bar_width = width // len(colors)
    
    for i, color in enumerate(colors):
        draw.rectangle([i * bar_width, 0, (i + 1) * bar_width, height // 3], fill=color)
    
    # Draw a white rectangle in the middle
    draw.rectangle([50, height // 3 + 20, width - 50, height - 20], outline=(255, 255, 255), width=2)
    
    # Add text
    try:
        font = ImageFont.load_default()
        text = "FINAL DISPLAY TEST"
        draw.text((width // 2 - 80, height // 2), text, fill=(255, 255, 255))
        
        # Add timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        draw.text((10, height - 20), timestamp, fill=(255, 255, 255))
    except Exception as e:
        print(f"Error drawing text: {e}")
    
    # Save the image to a temporary file
    temp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "final_test.png")
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

def create_test_unit_ready():
    """Create Test Unit Ready command"""
    command = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    return command

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

def send_command_with_retry(ep_out, ep_in, command, data=None, max_retries=5, retry_delay=1, timeout=5000):
    """Send a command with retry logic"""
    for attempt in range(max_retries):
        try:
            # Send command
            ep_out.write(command, timeout=timeout)
            
            # Send data if provided
            if data:
                # Send in chunks to avoid buffer issues
                chunk_size = 4096
                for i in range(0, len(data), chunk_size):
                    chunk = data[i:i+chunk_size]
                    ep_out.write(chunk, timeout=timeout)
            
            # Read CSW
            csw = ep_in.read(13, timeout=timeout)
            
            # Parse CSW
            csw_signature = int.from_bytes(csw[0:4], byteorder='little')
            csw_tag = int.from_bytes(csw[4:8], byteorder='little')
            csw_data_residue = int.from_bytes(csw[8:12], byteorder='little')
            csw_status = csw[12]
            
            return True, csw_status, csw
            
        except usb.core.USBError as e:
            print(f"USB error on attempt {attempt+1}/{max_retries}: {e}")
            
            if "pipe" in str(e).lower():
                print("Pipe error detected, clearing endpoints...")
                try:
                    # Try to clear endpoints
                    device = ep_out.device
                    device.clear_halt(ep_out.bEndpointAddress)
                    device.clear_halt(ep_in.bEndpointAddress)
                except Exception as e2:
                    print(f"Error clearing endpoints: {e2}")
            
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 1.5  # Increase delay with each retry
            else:
                print("Maximum retries exceeded")
                return False, None, None

def final_display_test():
    """Run the final display test with robust error handling"""
    print("\n=== ALi LCD Final Display Test ===\n")
    
    # Create test pattern
    image_path = create_test_pattern()
    
    try:
        # Find the device
        print("Looking for ALi LCD device...")
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
            
            # Find the device again after reset
            device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
            if device is None:
                print("Device not found after reset!")
                return False
        except Exception as e:
            print(f"Error resetting device: {e}")
            print("Continuing anyway...")
        
        # Set configuration
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
        
        # Step 1: Warm up with Test Unit Ready
        print("\nStep 1: Sending Test Unit Ready commands...")
        
        for i in range(3):
            print(f"Test Unit Ready {i+1}/3...")
            test_unit_ready = create_test_unit_ready()
            cbw = create_cbw(tag=i+1, data_length=0, direction='none', cmd_length=6, command=test_unit_ready)
            
            success, status, _ = send_command_with_retry(ep_out, ep_in, cbw)
            if success:
                print(f"Command completed with status: {status}")
            else:
                print("Command failed")
            
            time.sleep(1)
        
        # Step 2: Send F5 init command
        print("\nStep 2: Sending F5 init command...")
        
        f5_init = create_f5_init_command()
        cbw = create_cbw(tag=10, data_length=0, direction='none', cmd_length=16, command=f5_init)
        
        success, status, _ = send_command_with_retry(ep_out, ep_in, cbw)
        if success:
            print(f"F5 init command completed with status: {status}")
        else:
            print("F5 init command failed, but continuing anyway...")
        
        # Step 3: Convert image
        print("\nStep 3: Converting image...")
        image_data, width, height = convert_image_to_rgb565(image_path)
        print(f"Converted image: {width}x{height}, {len(image_data)} bytes")
        
        # Create image header
        header = create_image_header(width, height, 0, 0)
        
        # Combine header and image data
        data = header + image_data
        
        # Step 4: Send display image command
        print("\nStep 4: Sending display image command...")
        
        f5_display = create_f5_display_image_command(width, height)
        cbw = create_cbw(tag=11, data_length=len(data), direction='out', cmd_length=16, command=f5_display)
        
        success, status, _ = send_command_with_retry(ep_out, ep_in, cbw, data)
        if success:
            print(f"Display image command completed with status: {status}")
            if status == 0:
                print("Image should now be displayed on the device!")
            else:
                print("Command completed with non-zero status, but image might still be displayed")
        else:
            print("Display image command failed")
        
        # Keep the connection open for a while
        print("\nKeeping connection open for 30 seconds...")
        for i in range(30):
            sys.stdout.write(f"\rTime remaining: {30-i} seconds")
            sys.stdout.flush()
            
            # Send test unit ready every 5 seconds to keep the connection alive
            if i % 5 == 0 and i > 0:
                test_unit_ready = create_test_unit_ready()
                cbw = create_cbw(tag=20+i, data_length=0, direction='none', cmd_length=6, command=test_unit_ready)
                try:
                    ep_out.write(cbw)
                    ep_in.read(13)
                except:
                    pass  # Ignore errors during keepalive
            
            time.sleep(1)
        
        # Release interface
        print("\nReleasing interface...")
        usb.util.release_interface(device, interface.bInterfaceNumber)
        
        print("\nTest complete!")
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    final_display_test()
