#!/usr/bin/env python3
"""
USB Diagnostic Tool for ALi LCD Device

This tool helps diagnose common USB issues with the ALi LCD device,
including permission problems, resource busy errors, and kernel driver conflicts.
"""

import usb.core
import usb.util
import sys
import os
import time
import subprocess
import logging
from pathlib import Path

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import our package
from src.ali_lcd_device.usb_comm import (
    USBError, DeviceNotFoundError
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('usb_diagnostic')

# ALi LCD device identifiers
VENDOR_ID = 0x0402
PRODUCT_ID = 0x3922

def check_usb_permissions():
    """Check if user has permissions to access USB devices."""
    logger.info("Checking USB permissions...")
    
    # Check if running as root (not recommended but informative)
    if os.geteuid() == 0:
        logger.warning("Running as root. This is not recommended for security reasons.")
        logger.warning("Consider setting up udev rules instead.")
        return True
        
    # Check for existing udev rules
    udev_paths = [
        "/etc/udev/rules.d/99-ali-lcd.rules",
        "/lib/udev/rules.d/99-ali-lcd.rules",
        "/usr/lib/udev/rules.d/99-ali-lcd.rules"
    ]
    
    rule_exists = False
    for path in udev_paths:
        if os.path.exists(path):
            logger.info(f"Found udev rule: {path}")
            rule_exists = True
            break
    
    if not rule_exists:
        logger.warning("No ALi LCD udev rules found.")
        logger.warning("You may need to create a udev rule to access the device without root privileges.")
        logger.info("Example udev rule:")
        logger.info(f"SUBSYSTEM==\"usb\", ATTRS{{idVendor}}==\"{VENDOR_ID:04x}\", ATTRS{{idProduct}}==\"{PRODUCT_ID:04x}\", MODE=\"0666\"")
        logger.info("Save this to /etc/udev/rules.d/99-ali-lcd.rules and run 'sudo udevadm control --reload-rules'")
    
    # Check if user is in plugdev group
    try:
        groups = subprocess.check_output(["groups"]).decode().strip().split()
        if "plugdev" in groups:
            logger.info("User is in the plugdev group, which may help with USB access.")
        else:
            logger.info("User is not in the plugdev group, which might be required on some systems.")
    except Exception as e:
        logger.debug(f"Error checking groups: {e}")
    
    return rule_exists

def check_kernel_drivers():
    """Check for kernel drivers that might claim the device."""
    logger.info("Checking for kernel drivers that might claim the device...")
    
    try:
        # Check loaded modules
        lsmod = subprocess.check_output(["lsmod"]).decode()
        
        # Known modules that might interfere
        problematic_modules = ["usb_storage", "uas"]
        
        for module in problematic_modules:
            if module in lsmod:
                logger.info(f"Found kernel module {module} which might claim the device.")
    except Exception as e:
        logger.debug(f"Error checking kernel modules: {e}")
    
    return True

def check_busy_device():
    """Check if the device is already claimed by another process."""
    logger.info("Checking if device is already claimed by another process...")
    
    try:
        # Try to find processes using the USB device
        cmd = f"lsof -t /dev/bus/usb/*/*"
        output = subprocess.check_output(cmd, shell=True).decode().strip()
        
        if output:
            pids = output.split('\n')
            logger.warning(f"Found {len(pids)} processes that might be using USB devices.")
            
            for pid in pids:
                try:
                    cmd = f"ps -p {pid} -o comm="
                    process_name = subprocess.check_output(cmd, shell=True).decode().strip()
                    logger.warning(f"Process {pid} ({process_name}) is using a USB device.")
                except:
                    pass
    except Exception as e:
        logger.debug(f"Error checking for busy devices: {e}")
    
    return True

def check_device_present():
    """Check if the ALi LCD device is present in the system."""
    logger.info(f"Looking for ALi LCD device (VID=0x{VENDOR_ID:04x}, PID=0x{PRODUCT_ID:04x})...")
    
    try:
        device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if device is None:
            logger.error("ALi LCD device not found!")
            logger.info("Make sure the device is connected and powered on.")
            return False
        
        logger.info("Device found!")
        logger.info(f"Device: {device}")
        
        # Get device information
        try:
            manufacturer = usb.util.get_string(device, device.iManufacturer)
            product = usb.util.get_string(device, device.iProduct)
            serial = usb.util.get_string(device, device.iSerialNumber)
            
            logger.info(f"Manufacturer: {manufacturer}")
            logger.info(f"Product: {product}")
            logger.info(f"Serial Number: {serial}")
        except Exception as e:
            logger.debug(f"Could not read device strings: {e}")
        
        # Check if kernel driver is active
        try:
            interface = 0  # Assume interface 0
            if device.is_kernel_driver_active(interface):
                logger.warning(f"Kernel driver is active on interface {interface}")
                logger.info("This might cause 'Resource busy' errors if not properly detached.")
            else:
                logger.info(f"No kernel driver active on interface {interface}")
        except Exception as e:
            logger.debug(f"Could not check kernel driver: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking for device: {e}")
        return False

def try_claim_device():
    """Try to claim the device interface."""
    logger.info("Attempting to claim the device interface...")
    
    try:
        device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if device is None:
            logger.error("Device not found!")
            return False
        
        # Set configuration
        try:
            device.set_configuration()
        except usb.core.USBError as e:
            logger.warning(f"Error setting configuration: {e}")
            logger.info("This might be normal if the device is already configured.")
        
        # Get configuration
        cfg = device.get_active_configuration()
        
        # Get interface
        interface = cfg[(0, 0)]
        interface_number = interface.bInterfaceNumber
        
        # Try to detach kernel driver
        if device.is_kernel_driver_active(interface_number):
            logger.info(f"Detaching kernel driver from interface {interface_number}")
            try:
                device.detach_kernel_driver(interface_number)
                logger.info("Successfully detached kernel driver")
            except usb.core.USBError as e:
                logger.error(f"Failed to detach kernel driver: {e}")
                logger.error("This might cause 'Resource busy' errors.")
                return False
        
        # Try to claim interface
        try:
            usb.util.claim_interface(device, interface_number)
            logger.info(f"Successfully claimed interface {interface_number}")
            
            # Release it immediately for other applications
            usb.util.release_interface(device, interface_number)
            logger.info(f"Released interface {interface_number}")
            
            return True
        except usb.core.USBError as e:
            logger.error(f"Failed to claim interface: {e}")
            if "busy" in str(e).lower():
                logger.error("Device is busy - another application may be using it")
                logger.error("Try closing other applications or unplugging and reconnecting the device")
            return False
            
    except Exception as e:
        logger.error(f"Error while trying to claim device: {e}")
        return False

def perform_diagnostics():
    """Run a complete diagnostic on the ALi LCD device."""
    logger.info("Starting ALi LCD device diagnostics...")
    
    results = {}
    
    # Check USB permissions
    results['permissions'] = check_usb_permissions()
    
    # Check kernel drivers
    results['kernel_drivers'] = check_kernel_drivers()
    
    # Check if device is already claimed
    results['not_busy'] = check_busy_device()
    
    # Check if device is present
    results['device_present'] = check_device_present()
    
    # Try to claim the device
    if results['device_present']:
        results['can_claim'] = try_claim_device()
    else:
        results['can_claim'] = False
    
    # Print summary
    logger.info("\n======== DIAGNOSTIC SUMMARY ========")
    logger.info(f"Device found: {results['device_present']}")
    if results['device_present']:
        logger.info(f"Can claim device: {results['can_claim']}")
    
    # Provide recommendations
    logger.info("\n======== RECOMMENDATIONS ========")
    
    if not results['device_present']:
        logger.info("1. Make sure the device is properly connected")
        logger.info("2. Check if the device appears in 'lsusb' output")
        logger.info("3. Try a different USB port or cable")
    elif not results['can_claim']:
        logger.info("1. Unplug and reconnect the device")
        logger.info("2. Make sure no other applications are using the device")
        logger.info("3. Set up udev rules to allow non-root access to the device")
        logger.info("4. Try running the application with 'sudo' (not recommended for regular use)")
        logger.info("5. Check if the usb_storage module is claiming the device")
    else:
        logger.info("The device appears to be working correctly!")
        logger.info("If you're still experiencing issues:")
        logger.info("1. Check that you're using the correct device protocol")
        logger.info("2. Verify timeout settings in your application")
        logger.info("3. Add more error handling and retries for USB operations")
    
    return results

if __name__ == "__main__":
    perform_diagnostics()
