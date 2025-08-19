#!/usr/bin/env python3
"""
ALi LCD Device Diagnostic Tool
This tool provides detailed information about the ALi LCD device and runs a series of
basic commands to diagnose communication issues.
"""

import os
import sys
import time
import usb.core
import usb.util
import binascii

# ALi LCD Device constants
VENDOR_ID = 0x0402
PRODUCT_ID = 0x3922

# SCSI/USB Commands
TEST_UNIT_READY = 0x00
F5_COMMAND = 0xF5
F5_SUBCOMMAND_INIT = 0x03

# CBW (Command Block Wrapper) Constants
CBW_SIGNATURE = 0x43425355  # USBC in ASCII
CBW_FLAGS_DATA_IN = 0x80
CBW_FLAGS_DATA_OUT = 0x00
CBW_LUN = 0x00
CBWCB_LEN = 0x10  # SCSI command length for our device

def print_device_details(device):
    """Print detailed information about the USB device"""
    print("\n=== Device Details ===")
    print(f"Device ID: {device.idVendor:04X}:{device.idProduct:04X}")
    print(f"USB Version: {device.bcdUSB >> 8}.{device.bcdUSB & 0xFF}")
    print(f"Device Version: {device.bcdDevice >> 8}.{device.bcdDevice & 0xFF}")
    print(f"Maximum Packet Size: {device.bMaxPacketSize0}")
    
    if device.iManufacturer:
        try:
            print(f"Manufacturer: {usb.util.get_string(device, device.iManufacturer)}")
        except:
            print("Manufacturer: [Unable to retrieve]")
    
    if device.iProduct:
        try:
            print(f"Product: {usb.util.get_string(device, device.iProduct)}")
        except:
            print("Product: [Unable to retrieve]")
    
    if device.iSerialNumber:
        try:
            print(f"Serial Number: {usb.util.get_string(device, device.iSerialNumber)}")
        except:
            print("Serial Number: [Unable to retrieve]")
    
    print(f"Device Class: {device.bDeviceClass}")
    print(f"Device Subclass: {device.bDeviceSubClass}")
    print(f"Device Protocol: {device.bDeviceProtocol}")
    print(f"Number of Configurations: {device.bNumConfigurations}")
    
    # Print configuration details
    for cfg in device:
        print(f"\n=== Configuration {cfg.bConfigurationValue} ===")
        print(f"Number of Interfaces: {cfg.bNumInterfaces}")
        print(f"Max Power: {cfg.bMaxPower * 2}mA")
        
        for intf in cfg:
            print(f"\n  Interface {intf.bInterfaceNumber}, Alt Setting {intf.bAlternateSetting}")
            print(f"  Class: {intf.bInterfaceClass}")
            print(f"  Subclass: {intf.bInterfaceSubClass}")
            print(f"  Protocol: {intf.bInterfaceProtocol}")
            
            for ep in intf:
                direction = "IN" if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN else "OUT"
                type_str = {
                    usb.util.ENDPOINT_TYPE_CTRL: "Control",
                    usb.util.ENDPOINT_TYPE_ISO: "Isochronous",
                    usb.util.ENDPOINT_TYPE_BULK: "Bulk",
                    usb.util.ENDPOINT_TYPE_INTR: "Interrupt"
                }.get(usb.util.endpoint_type(ep.bmAttributes), "Unknown")
                
                print(f"    Endpoint 0x{ep.bEndpointAddress:02X} ({direction}): {type_str}")
                print(f"    Max Packet Size: {ep.wMaxPacketSize}")
                print(f"    Polling Interval: {ep.bInterval}")

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

def test_unit_ready(device, endpoint_out, endpoint_in):
    """Send Test Unit Ready command with verbose logging"""
    print("\n=== Test Unit Ready Command ===")
    
    # Prepare the CBWCB (Command Block)
    cb_data = bytearray(16)
    cb_data[0] = TEST_UNIT_READY  # Test Unit Ready opcode
    
    # Build the CBW
    tag = 0x12345678
    cbw = build_cbw(tag, 0, CBW_FLAGS_DATA_IN, cb_data)
    
    print(f"Sending CBW (31 bytes): {binascii.hexlify(cbw).decode()}")
    
    try:
        # Send the CBW
        bytes_written = device.write(endpoint_out, cbw)
        print(f"Sent {bytes_written} bytes")
        
        # Read the CSW
        print("Reading CSW...")
        try:
            csw_data = device.read(endpoint_in, 13, timeout=2000)
            print(f"Received CSW (13 bytes): {binascii.hexlify(csw_data).decode()}")
            
            # Parse CSW
            signature = int.from_bytes(csw_data[0:4], byteorder='little')
            csw_tag = int.from_bytes(csw_data[4:8], byteorder='little')
            residue = int.from_bytes(csw_data[8:12], byteorder='little')
            status = csw_data[12]
            
            print(f"CSW Signature: 0x{signature:08X}")
            print(f"CSW Tag: 0x{csw_tag:08X} (Expected: 0x{tag:08X})")
            print(f"Data Residue: {residue}")
            print(f"Status: {status} ({['Success', 'Failed', 'Phase Error'][status] if status < 3 else 'Unknown'})")
            
            return status
            
        except usb.core.USBError as e:
            print(f"Error reading CSW: {e}")
            
            if "Pipe error" in str(e):
                print("Attempting to clear stall condition...")
                try:
                    device.clear_halt(endpoint_in)
                    print("Stall condition cleared")
                    
                    # Try reading CSW again
                    print("Retrying CSW read...")
                    csw_data = device.read(endpoint_in, 13, timeout=2000)
                    print(f"Received CSW after stall clear: {binascii.hexlify(csw_data).decode()}")
                    return csw_data[12]  # Return status
                except usb.core.USBError as e2:
                    print(f"Error after stall clear: {e2}")
                    return None
            return None
            
    except usb.core.USBError as e:
        print(f"Error sending CBW: {e}")
        return None

def f5_command(device, endpoint_out, endpoint_in, subcommand):
    """Send F5 command with detailed logging"""
    print(f"\n=== F5 Command (Subcommand 0x{subcommand:02X}) ===")
    
    # Prepare the CBWCB (Command Block)
    cb_data = bytearray(16)
    cb_data[0] = F5_COMMAND     # F5 command
    cb_data[1] = subcommand     # Subcommand
    
    # Build the CBW
    tag = 0x87654321
    cbw = build_cbw(tag, 0, CBW_FLAGS_DATA_IN, cb_data)
    
    print(f"Sending CBW (31 bytes): {binascii.hexlify(cbw).decode()}")
    
    try:
        # Send the CBW
        bytes_written = device.write(endpoint_out, cbw)
        print(f"Sent {bytes_written} bytes")
        
        # Read the CSW
        print("Reading CSW...")
        try:
            csw_data = device.read(endpoint_in, 13, timeout=2000)
            print(f"Received CSW (13 bytes): {binascii.hexlify(csw_data).decode()}")
            
            # Parse CSW
            signature = int.from_bytes(csw_data[0:4], byteorder='little')
            csw_tag = int.from_bytes(csw_data[4:8], byteorder='little')
            residue = int.from_bytes(csw_data[8:12], byteorder='little')
            status = csw_data[12]
            
            print(f"CSW Signature: 0x{signature:08X}")
            print(f"CSW Tag: 0x{csw_tag:08X} (Expected: 0x{tag:08X})")
            print(f"Data Residue: {residue}")
            print(f"Status: {status} ({['Success', 'Failed', 'Phase Error'][status] if status < 3 else 'Unknown'})")
            
            return status
            
        except usb.core.USBError as e:
            print(f"Error reading CSW: {e}")
            
            if "Pipe error" in str(e):
                print("Attempting to clear stall condition...")
                try:
                    device.clear_halt(endpoint_in)
                    print("Stall condition cleared")
                    
                    # Try reading CSW again
                    print("Retrying CSW read...")
                    csw_data = device.read(endpoint_in, 13, timeout=2000)
                    print(f"Received CSW after stall clear: {binascii.hexlify(csw_data).decode()}")
                    return csw_data[12]  # Return status
                except usb.core.USBError as e2:
                    print(f"Error after stall clear: {e2}")
                    return None
            return None
            
    except usb.core.USBError as e:
        print(f"Error sending CBW: {e}")
        return None

def run_diagnostic():
    """Run diagnostic tests on the ALi LCD device"""
    print("\n=== ALi LCD Device Diagnostic Tool ===\n")
    
    # Find the device
    print("Looking for ALi LCD device...")
    device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    
    if device is None:
        print("Error: ALi LCD device not found")
        return False
    
    print(f"Found ALi LCD device at address {device.address}")
    
    # Print detailed information about the device
    print_device_details(device)
    
    try:
        # Reset the device
        print("\n=== Device Reset ===")
        print("Resetting device...")
        device.reset()
        time.sleep(1)  # Give device time to reset
        print("Reset complete")
        
        # Detach kernel driver if active
        if device.is_kernel_driver_active(0):
            print("\n=== Kernel Driver ===")
            print("Detaching kernel driver...")
            device.detach_kernel_driver(0)
            print("Kernel driver detached")
        
        # Set configuration
        print("\n=== Configuration ===")
        print("Setting device configuration...")
        device.set_configuration()
        time.sleep(0.5)  # Wait for configuration to take effect
        print("Configuration set")
        
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
        print("\n=== Interface ===")
        print("Claiming interface...")
        usb.util.claim_interface(device, interface)
        print("Interface claimed")
        
        # Run test commands with detailed logging
        for i in range(3):
            print(f"\n--- Test Iteration {i+1} ---")
            test_unit_ready(device, endpoint_out, endpoint_in)
            time.sleep(0.5)
        
        # Send F5 init command
        f5_command(device, endpoint_out, endpoint_in, F5_SUBCOMMAND_INIT)
        
        # Release the interface
        print("\n=== Cleanup ===")
        print("Releasing interface...")
        usb.util.release_interface(device, interface)
        print("Interface released")
        
        print("\n=== Diagnostics Complete ===")
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
    
    run_diagnostic()
