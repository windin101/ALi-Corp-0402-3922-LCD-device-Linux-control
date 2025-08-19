#!/usr/bin/env python3
"""
Basic reset and test for ALi LCD device
"""

import usb.core
import usb.util
import time
import sys
import os

# ALi LCD device identifiers
VENDOR_ID = 0x0402
PRODUCT_ID = 0x3922

def reset_device():
    """Attempt to reset the USB device"""
    print("Looking for ALi LCD device...")
    
    # Find the device
    device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if device is None:
        print("Device not found!")
        return False
    
    print(f"Found device: {device}")
    
    # Try to reset the device
    try:
        print("Resetting device...")
        device.reset()
        print("Device reset successful")
        return True
    except Exception as e:
        print(f"Error resetting device: {e}")
        return False

def basic_communication_test():
    """Perform basic communication test"""
    print("Starting basic communication test...")
    
    # Find the device
    device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if device is None:
        print("Device not found!")
        return False
    
    # Try to set configuration
    try:
        print("Setting device configuration...")
        device.set_configuration()
        print("Configuration set successfully")
    except Exception as e:
        print(f"Error setting configuration: {e}")
        print("Continuing anyway, this might be normal...")
    
    # Get configuration
    try:
        print("Getting active configuration...")
        cfg = device.get_active_configuration()
        print(f"Active configuration: {cfg}")
    except Exception as e:
        print(f"Error getting configuration: {e}")
        return False
    
    # Get interface
    try:
        print("Getting interface...")
        interface = cfg[(0, 0)]
        print(f"Interface: {interface}")
    except Exception as e:
        print(f"Error getting interface: {e}")
        return False
    
    # Check if kernel driver is active
    try:
        print("Checking if kernel driver is active...")
        if device.is_kernel_driver_active(interface.bInterfaceNumber):
            print("Kernel driver is active, detaching...")
            device.detach_kernel_driver(interface.bInterfaceNumber)
            print("Kernel driver detached")
        else:
            print("No kernel driver active")
    except Exception as e:
        print(f"Error checking kernel driver: {e}")
        print("Continuing anyway...")
    
    # Claim interface
    try:
        print("Claiming interface...")
        usb.util.claim_interface(device, interface.bInterfaceNumber)
        print("Interface claimed successfully")
    except Exception as e:
        print(f"Error claiming interface: {e}")
        return False
    
    # Find endpoints
    try:
        print("Finding endpoints...")
        ep_out = None
        ep_in = None
        
        for ep in interface:
            if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
                ep_out = ep
                print(f"Found OUT endpoint: 0x{ep.bEndpointAddress:02x}")
            elif usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
                ep_in = ep
                print(f"Found IN endpoint: 0x{ep.bEndpointAddress:02x}")
        
        if ep_out is None or ep_in is None:
            print("Could not find required endpoints")
            return False
    except Exception as e:
        print(f"Error finding endpoints: {e}")
        return False
    
    # Create a basic Test Unit Ready command
    print("Creating Test Unit Ready command...")
    
    # CBW signature (USBC in little-endian)
    cbw_signature = 0x43425355
    
    # Use tag 1
    tag = 1
    
    # No data transfer
    data_length = 0
    
    # Flags for direction (0 = out, 0x80 = in)
    flags = 0
    
    # LUN 0
    lun = 0
    
    # Command length (6 for Test Unit Ready)
    cmd_length = 6
    
    # Test Unit Ready command (first byte is 0x00, rest are 0)
    command = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    
    # Pad to 16 bytes
    command = command.ljust(16, b'\x00')
    
    # Create Command Block Wrapper (CBW)
    cbw = (
        cbw_signature.to_bytes(4, byteorder='little') +
        tag.to_bytes(4, byteorder='little') +
        data_length.to_bytes(4, byteorder='little') +
        bytes([flags, lun, cmd_length]) +
        command
    )
    
    print(f"CBW created: {cbw.hex()}")
    
    # Send command
    try:
        print("Sending Test Unit Ready command...")
        
        # Command phase
        bytes_written = ep_out.write(cbw)
        print(f"Wrote {bytes_written} bytes")
        
        # Status phase
        print("Reading Command Status Wrapper (CSW)...")
        csw = ep_in.read(13, timeout=5000)
        csw_hex = ''.join([f'{b:02x}' for b in csw])
        print(f"CSW received: {csw_hex}")
        
        # Parse CSW
        csw_signature = int.from_bytes(csw[0:4], byteorder='little')
        csw_tag = int.from_bytes(csw[4:8], byteorder='little')
        csw_data_residue = int.from_bytes(csw[8:12], byteorder='little')
        csw_status = csw[12]
        
        print(f"CSW Signature: 0x{csw_signature:08x}")
        print(f"CSW Tag: {csw_tag}")
        print(f"CSW Data Residue: {csw_data_residue}")
        print(f"CSW Status: {csw_status}")
        
        if csw_status == 0:
            print("Command completed successfully!")
        else:
            print(f"Command failed with status {csw_status}")
    except Exception as e:
        print(f"Error sending command: {e}")
        return False
    
    # Release interface
    try:
        print("Releasing interface...")
        usb.util.release_interface(device, interface.bInterfaceNumber)
        print("Interface released")
    except Exception as e:
        print(f"Error releasing interface: {e}")
    
    return True

if __name__ == "__main__":
    print("\n=== ALi LCD Device Reset and Test ===\n")
    
    if reset_device():
        print("\nDevice reset successful, waiting 2 seconds before communication test...\n")
        time.sleep(2)
        basic_communication_test()
    else:
        print("\nDevice reset failed, trying communication test anyway...\n")
        time.sleep(2)
        basic_communication_test()
    
    print("\n=== Test Complete ===\n")
