#!/usr/bin/env python3
"""
Simple test script to check ALi LCD device connectivity
"""

import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Try different import paths
print("Current working directory:", os.getcwd())
print("Python path:", sys.path)

try:
    # First try importing directly
    print("\nTrying direct import...")
    from ali_lcd_device.device import ALiLCDDevice
    print("Direct import successful")
except ImportError as e:
    print(f"Direct import failed: {e}")
    
    try:
        # Then try importing from src
        print("\nTrying import from src...")
        from src.ali_lcd_device.device import ALiLCDDevice
        print("Import from src successful")
    except ImportError as e:
        print(f"Import from src failed: {e}")
        
        # Add the parent directory to sys.path and try again
        print("\nAdding parent directory to sys.path...")
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        
        try:
            from src.ali_lcd_device.device import ALiLCDDevice
            print("Import after path adjustment successful")
        except ImportError as e:
            print(f"Import after path adjustment failed: {e}")
            sys.exit(1)

# Try to connect to the device
print("\nTrying to connect to ALi LCD device...")
try:
    device = ALiLCDDevice()
    print(f"Created device instance: {device}")
    
    # Print USB device search parameters
    print(f"Looking for USB device with VID:PID = {device.vendor_id:04x}:{device.product_id:04x}")
    
    # Try listing all devices first
    import usb.core
    print("\nListing all USB devices:")
    devices = list(usb.core.find(find_all=True))
    target_device = None
    for dev in devices:
        print(f"  {dev.idVendor:04x}:{dev.idProduct:04x}")
        if dev.idVendor == device.vendor_id and dev.idProduct == device.product_id:
            target_device = dev
            print(f"  ↑ This is our target device")
    
    if target_device is None:
        print("Target device not found in USB device list!")
    
    # Try connecting
    print("\nAttempting connection...")
    connected = device.connect()
    print(f"Connection successful: {connected}")
    
    # Show device state
    print(f"Device initialized: {device.initialized}")
    print(f"Display initialized: {device.display_initialized}")
    
    # Clean up
    print("\nClosing connection...")
    device.close()
    print("Connection closed")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
