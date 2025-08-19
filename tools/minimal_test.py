#!/usr/bin/env python3
"""
Minimal test for ALi LCD device
Focus on just initializing the device and sending minimal commands
"""

import os
import sys
import time
import usb.core
import usb.util

# ALi LCD Device constants
VENDOR_ID = 0x0402
PRODUCT_ID = 0x3922

# SCSI/USB Commands
TEST_UNIT_READY = 0x00
F5_COMMAND = 0xF5
F5_SUBCOMMAND_INIT = 0x03
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

def send_command(device, endpoint_out, endpoint_in, command):
    """Send a command with basic error handling"""
    try:
        # Send the CBW
        bytes_written = device.write(endpoint_out, command)
        print(f"Sent command: {' '.join(f'{b:02X}' for b in command[:16])}...")
        
        try:
            # Read the CSW
            csw_data = device.read(endpoint_in, 13, timeout=2000)
            csw_tag, csw_residue, csw_status = parse_csw(csw_data)
            print(f"Command completed with status: {csw_status}")
            return csw_status
        except usb.core.USBError as e:
            if "Pipe error" in str(e):
                print(f"Pipe error reading CSW: {e}")
                clear_stall(device, endpoint_in)
                try:
                    # Try reading CSW again
                    csw_data = device.read(endpoint_in, 13, timeout=2000)
                    csw_tag, csw_residue, csw_status = parse_csw(csw_data)
                    print(f"Command completed with status after stall: {csw_status}")
                    return csw_status
                except usb.core.USBError as e2:
                    print(f"Error reading CSW after clear stall: {e2}")
                    return None
            else:
                print(f"USB error reading CSW: {e}")
                return None
            
    except usb.core.USBError as e:
        print(f"USB error sending command: {e}")
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
    return send_command(device, endpoint_out, endpoint_in, cbw)

def send_f5_command(device, endpoint_out, endpoint_in, subcommand):
    """Send an F5 command with the specified subcommand"""
    print(f"Sending F5 command with subcommand 0x{subcommand:02X}...")
    
    # Prepare the CBWCB (Command Block)
    cb_data = bytearray(16)
    cb_data[0] = F5_COMMAND  # F5 command
    cb_data[1] = subcommand  # Subcommand
    
    # Build the CBW
    cbw = build_cbw(0x12345679, 0, CBW_FLAGS_DATA_IN, cb_data)
    
    # Send the command
    return send_command(device, endpoint_out, endpoint_in, cbw)

def minimal_test():
    """Run a minimal test with the ALi LCD device"""
    print("\n=== ALi LCD Minimal Test ===\n")
    
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
        time.sleep(1)  # Give device time to reset
        
        # Detach kernel driver if active
        if device.is_kernel_driver_active(0):
            print("Detaching kernel driver...")
            device.detach_kernel_driver(0)
        
        # Set configuration
        print("Setting device configuration...")
        device.set_configuration()
        time.sleep(0.5)  # Wait for configuration to take effect
        
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
        time.sleep(0.5)  # Wait for interface claim to take effect
        
        # Step 1: Test Unit Ready command (to check device status)
        print("\nStep 1: Sending Test Unit Ready command...")
        status = test_unit_ready(device, endpoint_out, endpoint_in)
        time.sleep(0.5)
        
        # Step 2: Initialize with F5 init command
        print("\nStep 2: Sending F5 init command...")
        status = send_f5_command(device, endpoint_out, endpoint_in, F5_SUBCOMMAND_INIT)
        time.sleep(0.5)
        
        # Step 3: Set display mode
        print("\nStep 3: Setting display mode...")
        status = send_f5_command(device, endpoint_out, endpoint_in, F5_SUBCOMMAND_MODE)
        time.sleep(0.5)
        
        # Step 4: Clear the screen
        print("\nStep 4: Clearing screen...")
        status = send_f5_command(device, endpoint_out, endpoint_in, F5_SUBCOMMAND_CLEAR)
        
        # Keep the connection open briefly to ensure commands complete
        print("\nCommands sent. Waiting 5 seconds...")
        time.sleep(5)
        
        # Release the interface
        print("\nReleasing interface...")
        usb.util.release_interface(device, interface)
        
        print("\n=== Test Complete ===")
        
        # Ask if screen cleared
        user_input = input("\nDid the LCD screen clear/change? (y/n): ")
        if user_input.lower() == 'y':
            print("Basic test successful! The LCD responded to commands.")
        else:
            print("Test inconclusive. The LCD did not show visible changes.")
            
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
    
    minimal_test()
