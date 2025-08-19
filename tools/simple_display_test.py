#!/usr/bin/env python3
"""
Simple display test for ALi LCD device
Focuses on basic operations with more robust error handling
"""

import os
import sys
import time
import usb.core
import usb.util
from PIL import Image, ImageDraw, ImageFont

# ALi LCD Device constants
VENDOR_ID = 0x0402
PRODUCT_ID = 0x3922
DISPLAY_WIDTH = 480
DISPLAY_HEIGHT = 272

# SCSI/USB Commands
TEST_UNIT_READY = 0x00
F5_INIT_COMMAND = 0xF5
F5_SUBCOMMAND_INIT = 0x03
F5_SUBCOMMAND_DISPLAY = 0x06
F5_SUBCOMMAND_CLEAR = 0x07
F5_SUBCOMMAND_MODE = 0x08

# CBW (Command Block Wrapper) Constants
CBW_SIGNATURE = 0x43425355  # USBC in ASCII
CBW_FLAGS_DATA_IN = 0x80
CBW_FLAGS_DATA_OUT = 0x00
CBW_LUN = 0x00
CBWCB_LEN = 0x10  # SCSI command length for our device

# CSW (Command Status Wrapper) Constants
CSW_SIGNATURE = 0x53425355  # USBS in ASCII
CSW_STATUS_SUCCESS = 0
CSW_STATUS_FAIL = 1
CSW_STATUS_PHASE_ERROR = 2

def generate_test_pattern(filename):
    """Generate a simple test pattern image"""
    image = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color='black')
    draw = ImageDraw.Draw(image)
    
    # Draw colored rectangles in the corners
    colors = ['red', 'green', 'blue', 'yellow']
    rect_size = 60
    
    # Top-left: Red
    draw.rectangle([(0, 0), (rect_size, rect_size)], fill=colors[0])
    
    # Top-right: Green
    draw.rectangle([(DISPLAY_WIDTH - rect_size, 0), (DISPLAY_WIDTH, rect_size)], fill=colors[1])
    
    # Bottom-left: Blue
    draw.rectangle([(0, DISPLAY_HEIGHT - rect_size), (rect_size, DISPLAY_HEIGHT)], fill=colors[2])
    
    # Bottom-right: Yellow
    draw.rectangle([(DISPLAY_WIDTH - rect_size, DISPLAY_HEIGHT - rect_size), 
                    (DISPLAY_WIDTH, DISPLAY_HEIGHT)], fill=colors[3])
    
    # Draw white crosshairs
    draw.line([(0, DISPLAY_HEIGHT // 2), (DISPLAY_WIDTH, DISPLAY_HEIGHT // 2)], fill='white', width=2)
    draw.line([(DISPLAY_WIDTH // 2, 0), (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT)], fill='white', width=2)
    
    # Draw text
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 24)
    except IOError:
        font = ImageFont.load_default()
    
    draw.text((DISPLAY_WIDTH // 2 - 140, DISPLAY_HEIGHT // 2 - 50), 
              "ALi LCD Test Pattern", fill='white', font=font)
    draw.text((DISPLAY_WIDTH // 2 - 100, DISPLAY_HEIGHT // 2 + 20), 
              f"{DISPLAY_WIDTH}x{DISPLAY_HEIGHT}", fill='white', font=font)
    
    # Save the image
    image.save(filename)
    print(f"Test pattern saved to {filename}")
    return image

def rgb_to_rgb565(image):
    """Convert RGB image to RGB565 format for the display"""
    width, height = image.size
    pixels = image.load()
    rgb565_data = bytearray(width * height * 2)
    
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            # Convert RGB888 to RGB565: RRRRRGGGGGGBBBBB
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            pos = (y * width + x) * 2
            rgb565_data[pos] = rgb565 & 0xFF  # Low byte
            rgb565_data[pos + 1] = (rgb565 >> 8) & 0xFF  # High byte
    
    return rgb565_data

def build_cbw(tag, transfer_length, flags, cb_data):
    """Build a Command Block Wrapper (CBW)"""
    cbw = bytearray(31)  # CBW is always 31 bytes
    
    # CBW Signature: 'USBC'
    cbw[0:4] = CBW_SIGNATURE.to_bytes(4, byteorder='little')
    
    # Command tag
    cbw[4:8] = tag.to_bytes(4, byteorder='little')
    
    # Transfer length
    cbw[8:12] = transfer_length.to_bytes(4, byteorder='little')
    
    # Flags (direction)
    cbw[12] = flags
    
    # LUN (Logical Unit Number)
    cbw[13] = CBW_LUN
    
    # CB Length (Command Block Length)
    cbw[14] = CBWCB_LEN
    
    # Command Block data
    cbw[15:31] = cb_data
    
    return cbw

def parse_csw(data):
    """Parse a Command Status Wrapper (CSW)"""
    if len(data) < 13:
        return None, None, None
    
    signature = int.from_bytes(data[0:4], byteorder='little')
    tag = int.from_bytes(data[4:8], byteorder='little')
    residue = int.from_bytes(data[8:12], byteorder='little')
    status = data[12]
    
    if signature != CSW_SIGNATURE:
        print(f"Warning: Invalid CSW signature: {signature:08X}, expected: {CSW_SIGNATURE:08X}")
    
    return tag, residue, status

def clear_stall(device, endpoint):
    """Clear a stall condition on the specified endpoint"""
    try:
        device.clear_halt(endpoint)
        print(f"Stall condition cleared on endpoint 0x{endpoint:02X}")
        return True
    except usb.core.USBError as e:
        print(f"Error clearing stall: {e}")
        return False

def send_command_with_retry(device, endpoint_out, endpoint_in, command, data=None, max_retries=5):
    """Send a command with retry logic"""
    tag = 1
    retries = 0
    backoff = 1.0  # Start with 1 second backoff
    
    while retries < max_retries:
        try:
            # Send the CBW
            bytes_written = device.write(endpoint_out, command)
            print(f"Sent command: {' '.join(f'{b:02X}' for b in command[:16])}...")
            
            # Send data if provided
            if data:
                chunks = [data[i:i+4096] for i in range(0, len(data), 4096)]
                for chunk in chunks:
                    device.write(endpoint_out, chunk)
                print(f"Sent {len(data)} bytes of data")
            
            # Read the CSW
            csw_data = device.read(endpoint_in, 13, timeout=5000)
            csw_tag, csw_residue, csw_status = parse_csw(csw_data)
            
            print(f"Command completed with status: {csw_status}")
            return csw_status
            
        except usb.core.USBError as e:
            print(f"USB error on attempt {retries+1}/{max_retries}: {e}")
            
            if "Pipe error" in str(e):
                print("Pipe error detected, clearing endpoints...")
                clear_stall(device, endpoint_in)
                clear_stall(device, endpoint_out)
            
            retries += 1
            if retries < max_retries:
                print(f"Retrying in {backoff} seconds...")
                time.sleep(backoff)
                backoff *= 1.5  # Exponential backoff
            else:
                print("Maximum retries exceeded")
                return None
    
    return None

def test_unit_ready(device, endpoint_out, endpoint_in):
    """Send Test Unit Ready command"""
    print("Sending Test Unit Ready command...")
    
    # Prepare the CBWCB (Command Block)
    cb_data = bytearray(16)
    cb_data[0] = TEST_UNIT_READY  # Test Unit Ready opcode
    
    # Build the CBW
    cbw = build_cbw(0x12345678, 0, CBW_FLAGS_DATA_IN, cb_data)
    
    # Send the command
    return send_command_with_retry(device, endpoint_out, endpoint_in, cbw)

def send_f5_command(device, endpoint_out, endpoint_in, subcommand):
    """Send an F5 command with the specified subcommand"""
    print(f"Sending F5 command with subcommand 0x{subcommand:02X}...")
    
    # Prepare the CBWCB (Command Block)
    cb_data = bytearray(16)
    cb_data[0] = F5_INIT_COMMAND  # F5 command
    cb_data[1] = subcommand       # Subcommand
    
    # Build the CBW
    cbw = build_cbw(0x12345679, 0, CBW_FLAGS_DATA_IN, cb_data)
    
    # Send the command
    return send_command_with_retry(device, endpoint_out, endpoint_in, cbw)

def send_display_image(device, endpoint_out, endpoint_in, image_data):
    """Send an image to the display"""
    print("Sending display image command...")
    data_length = len(image_data)
    
    # Prepare the CBWCB (Command Block)
    cb_data = bytearray(16)
    cb_data[0] = F5_INIT_COMMAND       # F5 command
    cb_data[1] = F5_SUBCOMMAND_DISPLAY # Display subcommand
    
    # Build the CBW with data out flag and transfer length
    cbw = build_cbw(0x1234567A, data_length, CBW_FLAGS_DATA_OUT, cb_data)
    
    # Send the command and data
    return send_command_with_retry(device, endpoint_out, endpoint_in, cbw, image_data)

def simple_display_test():
    """Run a simple display test with the ALi LCD device"""
    print("\n=== ALi LCD Simple Display Test ===\n")
    
    # Generate test pattern
    image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simple_test.png")
    image = generate_test_pattern(image_path)
    
    # Find the device
    print("Looking for ALi LCD device...")
    device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    
    if device is None:
        print("Error: ALi LCD device not found")
        return False
    
    print(f"Found ALi LCD device at address {device.address}")
    
    try:
        # Reset the device
        print("Resetting device...")
        device.reset()
        
        # Detach kernel driver if active
        if device.is_kernel_driver_active(0):
            print("Detaching kernel driver...")
            device.detach_kernel_driver(0)
        
        # Set configuration
        print("Setting device configuration...")
        device.set_configuration()
        
        # Get the active configuration
        cfg = device.get_active_configuration()
        
        # Get the first interface
        interface = cfg[(0,0)]
        
        # Find the endpoints
        endpoint_out = None
        endpoint_in = None
        
        for ep in interface:
            if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
                endpoint_out = ep.bEndpointAddress
            elif usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
                endpoint_in = ep.bEndpointAddress
        
        if endpoint_out is None or endpoint_in is None:
            print("Error: Could not find required endpoints")
            return False
        
        print(f"Found endpoints: OUT=0x{endpoint_out:02X}, IN=0x{endpoint_in:02X}")
        
        # Claim the interface
        print("Claiming interface...")
        usb.util.claim_interface(device, interface)
        
        # Step 1: Test Unit Ready command (to check device status)
        print("\nStep 1: Sending Test Unit Ready command...")
        status = test_unit_ready(device, endpoint_out, endpoint_in)
        
        # Step 2: Initialize with F5 init command
        print("\nStep 2: Sending F5 init command...")
        status = send_f5_command(device, endpoint_out, endpoint_in, F5_SUBCOMMAND_INIT)
        
        # Step 3: Set display mode
        print("\nStep 3: Setting display mode...")
        status = send_f5_command(device, endpoint_out, endpoint_in, F5_SUBCOMMAND_MODE)
        
        # Step 4: Clear the screen
        print("\nStep 4: Clearing screen...")
        status = send_f5_command(device, endpoint_out, endpoint_in, F5_SUBCOMMAND_CLEAR)
        
        # Step 5: Convert image to RGB565 format
        print("\nStep 5: Converting image...")
        rgb565_data = rgb_to_rgb565(image)
        print(f"Converted image: {image.width}x{image.height}, {len(rgb565_data)} bytes")
        
        # Step 6: Send the image
        print("\nStep 6: Sending display image command...")
        status = send_display_image(device, endpoint_out, endpoint_in, rgb565_data)
        
        # Keep the connection open briefly to ensure display updates
        print("\nKeeping connection open for 5 seconds...")
        time.sleep(5)
        
        # Ask the user if they can see the image
        user_input = input("\nDo you see the test pattern on the LCD? (y/n): ")
        if user_input.lower() == 'y':
            print("Test successful! The LCD is displaying the test pattern.")
        else:
            print("Test failed. The LCD is not displaying the test pattern correctly.")
        
        # Release the interface
        print("\nReleasing interface...")
        usb.util.release_interface(device, interface)
        
        print("\n=== Test Complete ===")
        return True
        
    except usb.core.USBError as e:
        print(f"USB Error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

if __name__ == "__main__":
    # Check if running with sudo
    if os.geteuid() != 0:
        print("This script must be run with sudo privileges.")
        sys.exit(1)
    
    simple_display_test()
