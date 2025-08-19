#!/usr/bin/env python3
"""
ALi LCD Device API Library
This library provides a simple API for interacting with the ALi LCD device
based on the knowledge gained from our experiments.
"""

import os
import sys
import time
import usb.core
import usb.util
from PIL import Image

# ALi LCD Device constants
VENDOR_ID = 0x0402
PRODUCT_ID = 0x3922
DISPLAY_WIDTH = 480
DISPLAY_HEIGHT = 272

# SCSI/USB Commands
TEST_UNIT_READY = 0x00
F5_COMMAND = 0xF5
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

class AliLcdDevice:
    """Class representing an ALi LCD device"""
    
    def __init__(self, debug=False):
        """Initialize the ALi LCD device connection"""
        self.device = None
        self.interface = None
        self.endpoint_out = None
        self.endpoint_in = None
        self.tag_counter = 0
        self.debug = debug
    
    def log(self, message):
        """Log a message if debug mode is enabled"""
        if self.debug:
            print(message)
        
    def find_device(self):
        """Find the ALi LCD device"""
        self.log("Looking for ALi LCD device...")
        self.device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        
        if self.device is None:
            self.log("Error: ALi LCD device not found")
            return False
        
        self.log(f"Found ALi LCD device at address {self.device.address}")
        return True
    
    def initialize(self):
        """Initialize the device"""
        try:
            # Reset the device
            self.log("Resetting device...")
            self.device.reset()
            time.sleep(1)  # Give device time to reset
            
            # Detach kernel driver if active
            if self.device.is_kernel_driver_active(0):
                self.log("Detaching kernel driver...")
                self.device.detach_kernel_driver(0)
            
            # Set configuration
            self.log("Setting device configuration...")
            self.device.set_configuration()
            time.sleep(0.5)  # Wait for configuration to take effect
            
            # Get the active configuration
            cfg = self.device.get_active_configuration()
            
            # Get the first interface
            self.interface = cfg[(0,0)]
            
            # Find the endpoints
            for ep in self.interface:
                if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
                    self.endpoint_out = ep.bEndpointAddress
                elif usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
                    self.endpoint_in = ep.bEndpointAddress
            
            if self.endpoint_out is None or self.endpoint_in is None:
                self.log("Error: Could not find required endpoints")
                return False
            
            self.log(f"Found endpoints: OUT=0x{self.endpoint_out:02X}, IN=0x{self.endpoint_in:02X}")
            
            # Claim the interface
            self.log("Claiming interface...")
            usb.util.claim_interface(self.device, self.interface)
            time.sleep(0.5)  # Wait for interface claim to take effect
            
            return True
            
        except usb.core.USBError as e:
            self.log(f"USB Error during initialization: {e}")
            return False
    
    def get_next_tag(self):
        """Get the next command tag"""
        self.tag_counter += 1
        return self.tag_counter
    
    def build_cbw(self, transfer_length, flags, cb_data):
        """Build a Command Block Wrapper (CBW)"""
        cbw = bytearray(31)  # CBW is always 31 bytes
        
        tag = self.get_next_tag()
        
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
        
        return cbw, tag
    
    def clear_stall(self, endpoint):
        """Clear a stall condition on the specified endpoint"""
        try:
            self.device.clear_halt(endpoint)
            self.log(f"Stall condition cleared on endpoint 0x{endpoint:02X}")
            return True
        except usb.core.USBError as e:
            self.log(f"Error clearing stall: {e}")
            return False
    
    def send_command(self, command, data=None, max_retries=5):
        """Send a command with robust error handling"""
        retries = 0
        backoff = 1.0  # Start with 1 second backoff
        
        while retries < max_retries:
            try:
                # Send the CBW
                bytes_written = self.device.write(self.endpoint_out, command)
                
                # Send data if provided
                if data:
                    chunk_size = 1024  # Use smaller chunks to avoid timeouts
                    for i in range(0, len(data), chunk_size):
                        chunk = data[i:i+chunk_size]
                        self.device.write(self.endpoint_out, chunk)
                        # Small delay between chunks to prevent overwhelming the device
                        time.sleep(0.01)
                    self.log(f"Sent {len(data)} bytes of data")
                
                # Read the CSW
                try:
                    csw_data = self.device.read(self.endpoint_in, 13, timeout=5000)
                    
                    # Check CSW signature
                    signature = int.from_bytes(csw_data[0:4], byteorder='little')
                    if signature != CSW_SIGNATURE:
                        self.log(f"Warning: Invalid CSW signature: {signature:08X}, expected: {CSW_SIGNATURE:08X}")
                    
                    # Return status
                    status = csw_data[12]
                    self.log(f"Command completed with status: {status}")
                    return status
                    
                except usb.core.USBError as e:
                    self.log(f"Error reading CSW: {e}")
                    
                    if "Pipe error" in str(e):
                        self.log("Pipe error detected, clearing endpoints...")
                        self.clear_stall(self.endpoint_in)
                        self.clear_stall(self.endpoint_out)
                        
                        # Try reading CSW again after clearing stall
                        try:
                            csw_data = self.device.read(self.endpoint_in, 13, timeout=2000)
                            status = csw_data[12]
                            self.log(f"Command completed with status after stall: {status}")
                            return status
                        except usb.core.USBError as e2:
                            self.log(f"Error reading CSW after stall clear: {e2}")
                            
                            # Just assume phase error and continue
                            self.log("Assuming command completed with errors, continuing...")
                            return CSW_STATUS_PHASE_ERROR
                    
                    # If it's a timeout, retry with exponential backoff
                    if "timed out" in str(e):
                        retries += 1
                        if retries < max_retries:
                            self.log(f"Retrying in {backoff} seconds...")
                            time.sleep(backoff)
                            backoff *= 1.5  # Exponential backoff
                        else:
                            self.log("Maximum retries exceeded")
                            return None
                    else:
                        # For other errors, just continue
                        self.log("Continuing despite error...")
                        return CSW_STATUS_PHASE_ERROR
                
            except usb.core.USBError as e:
                self.log(f"Error sending command: {e}")
                
                # If device disconnected, return immediately
                if "no such device" in str(e).lower():
                    self.log("Device disconnected")
                    return None
                
                retries += 1
                if retries < max_retries:
                    self.log(f"Retrying in {backoff} seconds...")
                    time.sleep(backoff)
                    backoff *= 1.5  # Exponential backoff
                else:
                    self.log("Maximum retries exceeded")
                    return None
        
        return None
    
    def test_unit_ready(self):
        """Send Test Unit Ready command"""
        self.log("Sending Test Unit Ready command...")
        
        # Prepare the CBWCB (Command Block)
        cb_data = bytearray(16)
        cb_data[0] = TEST_UNIT_READY  # Test Unit Ready opcode
        
        # Build the CBW
        cbw, _ = self.build_cbw(0, CBW_FLAGS_DATA_IN, cb_data)
        
        # Send the command
        return self.send_command(cbw)
    
    def send_f5_command(self, subcommand):
        """Send an F5 command with the specified subcommand"""
        self.log(f"Sending F5 command with subcommand 0x{subcommand:02X}...")
        
        # Prepare the CBWCB (Command Block)
        cb_data = bytearray(16)
        cb_data[0] = F5_COMMAND  # F5 command
        cb_data[1] = subcommand  # Subcommand
        
        # Build the CBW
        cbw, _ = self.build_cbw(0, CBW_FLAGS_DATA_IN, cb_data)
        
        # Send the command
        return self.send_command(cbw)
    
    def display_image(self, image_data):
        """Send an image to the display"""
        self.log("Sending display image command...")
        data_length = len(image_data)
        
        # Prepare the CBWCB (Command Block)
        cb_data = bytearray(16)
        cb_data[0] = F5_COMMAND            # F5 command
        cb_data[1] = F5_SUBCOMMAND_DISPLAY # Display subcommand
        
        # Build the CBW with data out flag and transfer length
        cbw, _ = self.build_cbw(data_length, CBW_FLAGS_DATA_OUT, cb_data)
        
        # Send the command and data
        return self.send_command(cbw, image_data)
    
    def clear_screen(self):
        """Clear the screen"""
        return self.send_f5_command(F5_SUBCOMMAND_CLEAR)
    
    def set_display_mode(self):
        """Set the display mode"""
        return self.send_f5_command(F5_SUBCOMMAND_MODE)
    
    def initialize_display(self):
        """Initialize the display with F5 init command"""
        return self.send_f5_command(F5_SUBCOMMAND_INIT)
    
    def close(self):
        """Close the connection to the device"""
        if self.device and self.interface is not None:
            try:
                self.log("Releasing interface...")
                usb.util.release_interface(self.device, self.interface)
                self.log("Interface released")
            except usb.core.USBError as e:
                self.log(f"Error releasing interface: {e}")

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

def display_image(image_path, debug=False):
    """Display an image on the ALi LCD device"""
    
    # Check if running with sudo
    if os.geteuid() != 0:
        print("This function must be run with sudo privileges.")
        return False
    
    try:
        # Load the image
        image = Image.open(image_path)
        
        # Resize image if necessary
        if image.size != (DISPLAY_WIDTH, DISPLAY_HEIGHT):
            image = image.resize((DISPLAY_WIDTH, DISPLAY_HEIGHT), Image.LANCZOS)
        
        # Convert image to RGB565 format
        rgb565_data = rgb_to_rgb565(image)
        
        # Initialize the device
        lcd = AliLcdDevice(debug=debug)
        
        if not lcd.find_device():
            return False
        
        if not lcd.initialize():
            return False
        
        # Check device status
        lcd.test_unit_ready()
        
        # Initialize display
        lcd.initialize_display()
        
        # Set display mode
        lcd.set_display_mode()
        
        # Clear the screen
        lcd.clear_screen()
        
        # Send the image
        result = lcd.display_image(rgb565_data)
        
        # Close the connection
        lcd.close()
        
        return result is not None
        
    except Exception as e:
        if debug:
            print(f"Error displaying image: {e}")
        return False

if __name__ == "__main__":
    # Simple command-line interface
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <image_path> [--debug]")
        sys.exit(1)
    
    image_path = sys.argv[1]
    debug = "--debug" in sys.argv
    
    if not os.path.exists(image_path):
        print(f"Error: Image file '{image_path}' not found")
        sys.exit(1)
    
    print(f"Displaying image '{image_path}' on ALi LCD device...")
    
    if display_image(image_path, debug):
        print("Image displayed successfully")
    else:
        print("Failed to display image")
