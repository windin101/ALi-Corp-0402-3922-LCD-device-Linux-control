#!/usr/bin/env python3
"""
ALi LCD Device Diagnostic Tool

This script performs diagnostic tests on the ALi LCD device to help
identify and troubleshoot common issues.
"""

import sys
import os
import logging
import time
import argparse
import usb.core
import usb.util

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from ali_lcd_device.device import ALiLCDDevice
from ali_lcd_device.commands import (
    create_test_unit_ready, create_inquiry, create_request_sense,
    create_f5_init_command, create_f5_set_mode_command
)
from ali_lcd_device.usb_comm import create_cbw, parse_csw

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def find_ali_devices():
    """Find all ALi LCD devices connected to the system."""
    print("\n=== USB Device Detection ===")
    devices = usb.core.find(find_all=True, idVendor=0x0402, idProduct=0x3922)
    
    count = 0
    for device in devices:
        count += 1
        print(f"ALi LCD device found: Bus {device.bus} Port {'.'.join(str(p) for p in device.port_numbers)}")
        
        # Get device information
        try:
            manufacturer = usb.util.get_string(device, device.iManufacturer)
            product = usb.util.get_string(device, device.iProduct)
            print(f"  Manufacturer: {manufacturer}")
            print(f"  Product: {product}")
        except:
            print("  Could not retrieve device strings")
        
        # Check if kernel driver is attached
        for config in device:
            for interface in config:
                try:
                    if device.is_kernel_driver_active(interface.bInterfaceNumber):
                        print(f"  Kernel driver is attached to interface {interface.bInterfaceNumber}")
                    else:
                        print(f"  No kernel driver attached to interface {interface.bInterfaceNumber}")
                except:
                    print(f"  Could not determine kernel driver status for interface {interface.bInterfaceNumber}")
    
    if count == 0:
        print("No ALi LCD devices found")
        
    return count

def test_usb_permissions():
    """Test if we have permission to access the USB device."""
    print("\n=== USB Permission Test ===")
    try:
        device = usb.core.find(idVendor=0x0402, idProduct=0x3922)
        if device is None:
            print("Device not found, skipping permission test")
            return False
        
        # Try to get the device descriptor
        device.get_active_configuration()
        print("USB permissions test passed")
        return True
    except usb.core.USBError as e:
        if "permission" in str(e).lower() or "access" in str(e).lower():
            print("USB permission denied. You may need to:")
            print("1. Run with sudo")
            print("2. Install udev rules:")
            print("   sudo cp system/99-ali-lcd.rules /etc/udev/rules.d/")
            print("   sudo udevadm control --reload-rules && sudo udevadm trigger")
        else:
            print(f"USB error: {str(e)}")
        return False

def test_low_level_commands():
    """Test low-level SCSI commands directly."""
    print("\n=== Low-Level Command Test ===")
    
    try:
        # Find the device
        device = usb.core.find(idVendor=0x0402, idProduct=0x3922)
        if device is None:
            print("Device not found, skipping low-level command test")
            return False
        
        # Set configuration and claim interface
        try:
            device.set_configuration()
        except:
            pass  # Device may already be configured
        
        # Get the interface
        cfg = device.get_active_configuration()
        interface = cfg[(0, 0)]
        
        # Detach kernel driver if active
        if device.is_kernel_driver_active(interface.bInterfaceNumber):
            print("Detaching kernel driver")
            device.detach_kernel_driver(interface.bInterfaceNumber)
        
        # Claim the interface
        usb.util.claim_interface(device, interface.bInterfaceNumber)
        
        # Find the endpoints
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
        
        print("Endpoints found, testing TEST UNIT READY command")
        
        # Create a TEST UNIT READY command
        cmd, _, _ = create_test_unit_ready()
        
        # Create CBW
        tag = 1
        cbw = create_cbw(tag, 0, 'none', 0, cmd)
        
        # Send CBW
        print(f"Sending CBW (tag={tag})")
        try:
            device.write(ep_out, cbw)
            print("CBW sent successfully")
        except Exception as e:
            print(f"Error sending CBW: {str(e)}")
            return False
        
        # Read CSW
        print("Reading CSW")
        try:
            csw_data = device.read(ep_in, 13)
            print(f"CSW received: {csw_data.tobytes().hex()}")
            
            # Parse CSW
            csw_signature, csw_tag, csw_data_residue, csw_status = parse_csw(csw_data)
            print(f"CSW Signature: 0x{csw_signature:08x}")
            print(f"CSW Tag: {csw_tag}")
            print(f"CSW Data Residue: {csw_data_residue}")
            print(f"CSW Status: {csw_status}")
            
            if csw_signature != 0x53425355:
                print("WARNING: Invalid CSW signature")
            
            if csw_tag != tag:
                print(f"WARNING: Tag mismatch (expected {tag}, got {csw_tag})")
            
            print("Low-level command test completed successfully")
            return csw_status == 0
            
        except Exception as e:
            print(f"Error reading CSW: {str(e)}")
            return False
        
    except Exception as e:
        print(f"Error in low-level command test: {str(e)}")
        return False

def test_lifecycle_state_transitions():
    """Test lifecycle state transitions."""
    print("\n=== Lifecycle State Transition Test ===")
    print("This test will attempt to connect to the device and observe state transitions.")
    print("It will run for about 60 seconds to capture the full transition sequence.")
    print("Press Ctrl+C to abort the test at any time.")
    
    try:
        # Check if device is already claimed by another process
        test_device = usb.core.find(idVendor=0x0402, idProduct=0x3922)
        if test_device is None:
            print("Device not found, skipping lifecycle test")
            return False
        
        # Try to claim the interface
        cfg = test_device.get_active_configuration()
        interface = cfg[(0, 0)]
        
        try:
            # First try to detach any kernel driver
            if test_device.is_kernel_driver_active(interface.bInterfaceNumber):
                print("Detaching kernel driver before lifecycle test")
                test_device.detach_kernel_driver(interface.bInterfaceNumber)
                
            # Try to claim the interface
            usb.util.claim_interface(test_device, interface.bInterfaceNumber)
            # Release it for our test
            usb.util.release_interface(test_device, interface.bInterfaceNumber)
        except usb.core.USBError as e:
            if "busy" in str(e).lower():
                print("ERROR: Device is currently being used by another process.")
                print("Please close any other applications that might be using the device,")
                print("or try unplugging and reconnecting the device.")
                return False
        
        # Create device instance
        device = ALiLCDDevice()
        
        # Connect to the device
        print("Connecting to device...")
        device.connect(wait_for_stable=False)
        
        print("Starting state transition test")
        print("Current state:", device.lifecycle_state.name)
        
        start_time = time.time()
        last_state = device.lifecycle_state
        command_count = 0
        tag_mismatches = 0
        
        # Run for about 65 seconds to ensure we catch the transitions
        while time.time() - start_time < 65:
            # Send TEST UNIT READY command
            success, tag_mismatch = device._test_unit_ready()
            command_count += 1
            
            if tag_mismatch:
                tag_mismatches += 1
            
            # Check if state has changed
            if device.lifecycle_state != last_state:
                elapsed = time.time() - start_time
                print(f"[{elapsed:.1f}s] State transition: {last_state.name} → {device.lifecycle_state.name}")
                print(f"  Commands sent: {command_count}")
                print(f"  Tag mismatch rate: {tag_mismatches/command_count:.1%}")
                last_state = device.lifecycle_state
                
            # Print status every 5 seconds
            if command_count % 25 == 0:
                elapsed = time.time() - start_time
                mismatch_rate = tag_mismatches / command_count if command_count > 0 else 0
                print(f"[{elapsed:.1f}s] State: {device.lifecycle_state.name}, "
                      f"Commands: {command_count}, Mismatch rate: {mismatch_rate:.1%}")
            
            # Adaptive sleep based on state
            if device.lifecycle_state.name == 'ANIMATION':
                time.sleep(0.2)
            else:
                time.sleep(0.1)
                
        print("\nTest completed.")
        print(f"Final state: {device.lifecycle_state.name}")
        print(f"Commands sent: {command_count}")
        print(f"Tag mismatch rate: {tag_mismatches/command_count:.1%}")
        
        return device.lifecycle_state.name == 'CONNECTED'
        
    except KeyboardInterrupt:
        print("\nTest aborted by user.")
        return False
    except Exception as e:
        print(f"Error in lifecycle state test: {str(e)}")
        return False
    finally:
        if 'device' in locals() and device is not None:
            device.close()

def main():
    parser = argparse.ArgumentParser(description='ALi LCD Device Diagnostic Tool')
    parser.add_argument('--usb-only', action='store_true', 
                        help='Only test USB detection and permissions')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger('ali_lcd_device').setLevel(logging.DEBUG)
    
    print("ALi LCD Device Diagnostic Tool")
    print("==============================")
    
    # Run the tests
    device_count = find_ali_devices()
    
    if device_count == 0:
        print("\nNo ALi LCD devices found. Please check the connection.")
        return
    
    permission_ok = test_usb_permissions()
    
    if not permission_ok:
        print("\nUSB permission issues detected. Please fix permissions before continuing.")
        return
    
    if args.usb_only:
        print("\nUSB-only tests completed. All tests passed.")
        return
    
    low_level_ok = test_low_level_commands()
    
    if not low_level_ok:
        print("\nLow-level command test failed. This may indicate issues with the device.")
        print("You might want to try disconnecting and reconnecting the device.")
    
    print("\nDo you want to run the lifecycle state transition test?")
    print("This will take about 60 seconds to complete.")
    print("Press y to continue, any other key to skip: ", end="")
    
    choice = input().lower()
    if choice == 'y':
        lifecycle_ok = test_lifecycle_state_transitions()
        
        if lifecycle_ok:
            print("\nAll tests completed successfully.")
        else:
            print("\nLifecycle state test issues detected.")
            print("This is normal if the test was aborted before completion.")
    else:
        print("\nLifecycle state test skipped.")
    
    print("\nDiagnostic tests completed.")

if __name__ == "__main__":
    main()
