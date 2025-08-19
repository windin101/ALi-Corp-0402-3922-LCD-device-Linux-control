#!/usr/bin/env python3
"""
Comprehensive test for ALi LCD device lifecycle
"""

import sys
import os
import logging
import time
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

def test_device_lifecycle():
    """Test the complete device lifecycle"""
    
    print("\n=== ALi LCD Device Lifecycle Test ===\n")
    
    device = ALiLCDDevice()
    print(f"Created device instance with VID:PID = {device.vendor_id:04x}:{device.product_id:04x}")
    
    try:
        # Step 1: Connect to the device
        print("\n--- Step 1: Connecting to device ---")
        device.connect()
        print(f"Connected: {device.initialized}")
        print(f"Current state: {device.lifecycle_manager.get_state().name}")
        
        # Step 2: Wait for Animation state
        print("\n--- Step 2: Waiting in Animation state ---")
        print("Waiting 5 seconds to observe Animation state...")
        for i in range(5):
            time.sleep(1)
            state = device.lifecycle_manager.get_state()
            mismatch_rate = device.tag_monitor.get_mismatch_rate()
            print(f"Current state: {state.name}, Tag mismatch rate: {mismatch_rate:.2f}%")
        
        # Step 3: Initialize display
        print("\n--- Step 3: Initializing display ---")
        try:
            device.initialize_display()
            print("Display initialized successfully")
        except Exception as e:
            print(f"Display initialization failed: {e}")
            print("This might be normal during Animation state, continuing...")
        
        # Step 4: Wait for transition to Connected state
        print("\n--- Step 4: Waiting for Connected state ---")
        print("Waiting up to 30 seconds for Connected state...")
        
        start_time = time.time()
        timeout = 30
        connected = False
        
        while time.time() - start_time < timeout:
            state = device.lifecycle_manager.get_state()
            mismatch_rate = device.tag_monitor.get_mismatch_rate()
            print(f"Current state: {state.name}, Tag mismatch rate: {mismatch_rate:.2f}%")
            
            if state == DeviceLifecycleState.CONNECTED:
                connected = True
                print(f"Device reached Connected state after {time.time() - start_time:.1f} seconds")
                break
                
            time.sleep(1)
        
        if not connected:
            print("Device did not reach Connected state within timeout")
        
        # Step 5: Try sending a test command in current state
        print("\n--- Step 5: Sending test command ---")
        try:
            device._test_unit_ready()
            print("Test unit ready command successful")
        except Exception as e:
            print(f"Test unit ready command failed: {e}")
        
        # Step 6: Try initializing display again (should work if in Connected state)
        if connected:
            print("\n--- Step 6: Initializing display in Connected state ---")
            try:
                device.initialize_display()
                print("Display initialized successfully")
            except Exception as e:
                print(f"Display initialization failed: {e}")
        
        # Step 7: Close the connection
        print("\n--- Step 7: Closing connection ---")
        device.close()
        print("Connection closed")
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n=== Lifecycle Test Completed ===")
    return True

if __name__ == "__main__":
    test_device_lifecycle()
