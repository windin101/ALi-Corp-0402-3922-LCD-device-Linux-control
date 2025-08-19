#!/usr/bin/env python3
"""
Advanced ALi LCD Device Diagnostic Tool

This tool implements a highly specialized approach for diagnosing and controlling
the ALi LCD device (VID:0x0402, PID:0x3922) with precise control of timing, command
structures, and error handling based on observed behavior patterns.

Features:
- Extremely slow and careful command sequencing
- USB descriptor inspection and analysis
- Verbose SCSI command debugging
- Detailed error interpretation
- State-aware command handling
- Multiple recovery strategies

Author: LEO
Date: August 19, 2025
"""

import os
import sys
import time
import usb.core
import usb.util
import struct
import binascii
import argparse
import logging
from datetime import datetime
import threading

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('ALi-LCD-Diagnostics')

# USB Constants
VENDOR_ID = 0x0402
PRODUCT_ID = 0x3922
EP_OUT = 0x02
EP_IN = 0x81

# SCSI Commands
TEST_UNIT_READY_CMD = b'\x00\x00\x00\x00\x00\x00'
INQUIRY_CMD = b'\x12\x00\x00\x00\x24\x00'
REQUEST_SENSE_CMD = b'\x03\x00\x00\x00\x12\x00'

# ALi LCD Device Custom Commands
F5_COMMANDS = {
    'INIT': b'\xF5\x01\x00\x00\x00\x00',
    'INIT_ALT': b'\xF5\x03\x00\x00\x00\x00',  # Alternative init from diagnostic
    'ANIMATION': b'\xF5\x10\x00\x00\x00\x00',
    'SET_MODE': b'\xF5\x20\x00\x00\x00\x00',
    'GET_STATUS': b'\xF5\x30\x00\x00\x00\x00',
    'CLEAR_SCREEN': b'\xF5\xA0\x00\x00\x00\x00',
    'DISPLAY_IMAGE': b'\xF5\xB0\x00\x00\x00\x00'
}

# Command timing configurations (in seconds)
COMMAND_TIMING = {
    'DEFAULT_DELAY': 3.0,        # Default delay between commands
    'POST_ERROR_DELAY': 5.0,     # Delay after errors
    'RECONNECT_DELAY': 10.0,     # Delay before reconnection attempt
    'INIT_DELAY': 10.0,          # Delay after initialization commands
    'STATUS_DELAY': 2.0,         # Delay after status commands
    'ANIMATION_DELAY': 4.0,      # Delay after animation commands
    'CLEAR_DELAY': 3.0,          # Delay after clear screen
    'READ_WRITE_DELAY': 0.5,     # Delay between write and read operations
    'CSW_DELAY': 1.0             # Delay before reading CSW
}

# SCSI Status Codes
SCSI_STATUS = {
    0x00: "Good",
    0x01: "Check Condition",
    0x02: "Condition Met",
    0x04: "Busy",
    0x08: "Reservation Conflict",
    0x10: "Task Set Full",
    0x14: "ACA Active",
    0x18: "Task Aborted"
}

# SCSI Sense Keys
SENSE_KEYS = {
    0x00: "No Sense",
    0x01: "Recovered Error",
    0x02: "Not Ready",
    0x03: "Medium Error",
    0x04: "Hardware Error",
    0x05: "Illegal Request",
    0x06: "Unit Attention",
    0x07: "Data Protect",
    0x08: "Blank Check",
    0x09: "Vendor Specific",
    0x0A: "Copy Aborted",
    0x0B: "Aborted Command",
    0x0C: "Obsolete",
    0x0D: "Volume Overflow",
    0x0E: "Miscompare",
    0x0F: "Completed"
}

class ALiLCDDiagnostics:
    def __init__(self, vendor_id=VENDOR_ID, product_id=PRODUCT_ID):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.device = None
        self.tag = 0x12345678  # Initial command tag
        self.is_connected = False
        self.error_count = 0
        self.success_count = 0
        self.current_state = "DISCONNECTED"
        self.command_count = 0
        self.last_status = None
        self.last_sense = None
        self.reconnect_lock = threading.Lock()
        self.reconnecting = False
        self.verbose = True
        self.halt_on_error = False
        self.max_errors = 10  # Maximum consecutive errors before recovery
        
    def print_device_descriptors(self):
        """Print detailed information about the USB device descriptors"""
        if not self.device:
            logger.error("No device connected")
            return
        
        logger.info("=== USB Device Descriptors ===")
        logger.info(f"Device ID: {self.device.idVendor:04X}:{self.device.idProduct:04X}")
        logger.info(f"USB Version: {self.device.bcdUSB >> 8}.{self.device.bcdUSB & 0xFF}")
        logger.info(f"Device Class: 0x{self.device.bDeviceClass:02X}")
        logger.info(f"Device Subclass: 0x{self.device.bDeviceSubClass:02X}")
        logger.info(f"Device Protocol: 0x{self.device.bDeviceProtocol:02X}")
        logger.info(f"Max Packet Size: {self.device.bMaxPacketSize0}")
        logger.info(f"Vendor ID: 0x{self.device.idVendor:04X}")
        logger.info(f"Product ID: 0x{self.device.idProduct:04X}")
        logger.info(f"Device Version: {self.device.bcdDevice >> 8}.{self.device.bcdDevice & 0xFF}")
        
        # Try to get string descriptors
        try:
            if self.device.iManufacturer:
                manufacturer = usb.util.get_string(self.device, self.device.iManufacturer)
                logger.info(f"Manufacturer: {manufacturer}")
        except:
            logger.info("Manufacturer: [Unable to retrieve]")
            
        try:
            if self.device.iProduct:
                product = usb.util.get_string(self.device, self.device.iProduct)
                logger.info(f"Product: {product}")
        except:
            logger.info("Product: [Unable to retrieve]")
            
        try:
            if self.device.iSerialNumber:
                serial = usb.util.get_string(self.device, self.device.iSerialNumber)
                logger.info(f"Serial Number: {serial}")
        except:
            logger.info("Serial Number: [Unable to retrieve]")
        
        # Print configuration details
        logger.info("\n=== Configuration Details ===")
        cfg_count = 0
        for cfg in self.device:
            cfg_count += 1
            logger.info(f"Configuration {cfg.bConfigurationValue}:")
            logger.info(f"  Number of Interfaces: {cfg.bNumInterfaces}")
            logger.info(f"  Max Power: {cfg.bMaxPower * 2}mA")
            
            intf_count = 0
            for intf in cfg:
                intf_count += 1
                logger.info(f"  Interface {intf.bInterfaceNumber}, Alt Setting {intf.bAlternateSetting}")
                logger.info(f"    Class: 0x{intf.bInterfaceClass:02X}")
                logger.info(f"    Subclass: 0x{intf.bInterfaceSubClass:02X}")
                logger.info(f"    Protocol: 0x{intf.bInterfaceProtocol:02X}")
                
                ep_count = 0
                for ep in intf:
                    ep_count += 1
                    direction = "IN" if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN else "OUT"
                    ep_type = usb.util.endpoint_type(ep.bmAttributes)
                    type_str = {
                        usb.util.ENDPOINT_TYPE_CTRL: "Control",
                        usb.util.ENDPOINT_TYPE_ISO: "Isochronous",
                        usb.util.ENDPOINT_TYPE_BULK: "Bulk",
                        usb.util.ENDPOINT_TYPE_INTR: "Interrupt"
                    }.get(ep_type, "Unknown")
                    
                    logger.info(f"    Endpoint 0x{ep.bEndpointAddress:02X} ({direction}): {type_str}")
                    logger.info(f"      Max Packet Size: {ep.wMaxPacketSize}")
                    logger.info(f"      Polling Interval: {ep.bInterval}")
        
        logger.info(f"\nFound {cfg_count} configurations with {intf_count} interfaces and {ep_count} endpoints")
    
    def connect(self):
        """Connect to the device with detailed error handling"""
        try:
            logger.info(f"Looking for USB device {self.vendor_id:04x}:{self.product_id:04x}...")
            
            # Find all USB devices and list them
            all_devices = list(usb.core.find(find_all=True))
            logger.info(f"Found {len(all_devices)} USB devices in the system")
            
            for dev in all_devices:
                logger.debug(f"Device: {dev.idVendor:04x}:{dev.idProduct:04x}")
            
            # Find our specific device
            self.device = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)
            
            if self.device is None:
                logger.error("ALi LCD device not found")
                return False
                
            logger.info(f"Found ALi LCD device at address {self.device.address}")
            
            # Handle kernel driver (if active)
            try:
                if self.device.is_kernel_driver_active(0):
                    logger.info("Detaching kernel driver...")
                    self.device.detach_kernel_driver(0)
                    logger.info("Kernel driver detached")
            except Exception as e:
                logger.warning(f"Kernel driver handling error: {str(e)}")
            
            # Reset the device for a clean state
            try:
                logger.info("Resetting device...")
                self.device.reset()
                time.sleep(2)  # Longer delay after reset
                logger.info("Device reset complete")
            except Exception as e:
                logger.warning(f"Device reset error: {str(e)}")
            
            # Set configuration
            try:
                logger.info("Setting device configuration...")
                self.device.set_configuration()
                time.sleep(1.5)  # Wait for configuration
                logger.info("Configuration set")
            except Exception as e:
                logger.warning(f"Failed to set configuration: {str(e)}")
                # Try fallback to first configuration
                try:
                    cfg = self.device[0]
                    self.device.set_configuration(cfg.bConfigurationValue)
                    logger.info(f"Set configuration to {cfg.bConfigurationValue}")
                except Exception as e2:
                    logger.warning(f"Fallback configuration failed: {str(e2)}")
            
            # Get and print device descriptors
            self.print_device_descriptors()
            
            # Get active configuration and interface
            cfg = self.device.get_active_configuration()
            intf = cfg[(0,0)]  # First interface
            
            # Claim interface
            try:
                logger.info("Claiming interface...")
                usb.util.claim_interface(self.device, intf)
                logger.info("Interface claimed")
            except Exception as e:
                logger.warning(f"Interface claim error: {str(e)}")
                # Try alternative claim method
                try:
                    self.device.set_configuration()
                    self.device.set_interface_altsetting(0, 0)
                    logger.info("Interface claimed via alternative method")
                except Exception as e2:
                    logger.error(f"All interface claim methods failed: {str(e2)}")
                    return False
            
            self.is_connected = True
            self.current_state = "ANIMATION"  # Initial state is always animation
            self.command_count = 0
            self.error_count = 0
            
            logger.info("Successfully connected to ALi LCD device")
            return True
            
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            self.is_connected = False
            return False

    def disconnect(self):
        """Disconnect from the device and clean up resources"""
        if self.device:
            try:
                cfg = self.device.get_active_configuration()
                intf = cfg[(0,0)]
                usb.util.release_interface(self.device, intf)
                logger.info("Interface released")
            except Exception as e:
                logger.warning(f"Interface release error: {str(e)}")
        
        self.device = None
        self.is_connected = False
        self.current_state = "DISCONNECTED"
        logger.info("Disconnected from device")
        return True

    def reconnect(self):
        """Safely reconnect to the device with retry logic"""
        with self.reconnect_lock:
            if self.reconnecting:
                logger.debug("Reconnection already in progress, skipping")
                return False
            
            self.reconnecting = True
        
        try:
            logger.info("Starting reconnection sequence...")
            
            # Make sure we're fully disconnected
            self.disconnect()
            
            # Wait before reconnection attempt
            wait_time = COMMAND_TIMING['RECONNECT_DELAY']
            logger.info(f"Waiting {wait_time}s before reconnection attempt...")
            time.sleep(wait_time)
            
            # Try to reconnect up to 3 times
            for attempt in range(3):
                logger.info(f"Reconnection attempt {attempt+1}/3")
                
                if self.connect():
                    logger.info("Reconnection successful!")
                    self.tag = 0x12345678  # Reset tag
                    self.error_count = 0
                    self.command_count = 0
                    self.current_state = "ANIMATION"
                    return True
                
                logger.warning(f"Reconnection attempt {attempt+1} failed")
                time.sleep(2 * (attempt + 1))  # Increasing delays
            
            logger.error("All reconnection attempts failed")
            return False
            
        finally:
            with self.reconnect_lock:
                self.reconnecting = False

    def build_cbw(self, command, data_length=0, direction_in=True, lun=0):
        """
        Build a Command Block Wrapper (CBW)
        
        Args:
            command: SCSI command bytes
            data_length: Expected data transfer length
            direction_in: True for device-to-host, False for host-to-device
            lun: Logical Unit Number
            
        Returns:
            CBW as bytes
        """
        # Increment tag for each command
        self.tag = (self.tag + 1) & 0xFFFFFFFF
        
        # Determine direction flag
        direction_flag = 0x80 if direction_in else 0x00
        
        # Command length (up to 16 bytes)
        cmd_length = min(len(command), 16)
        
        # Create CBW structure
        cbw = struct.pack('<4sIIBBB',
                          b'USBC',           # CBW signature
                          self.tag,          # Command tag
                          data_length,       # Data transfer length
                          direction_flag,    # Direction flag
                          lun,               # LUN
                          cmd_length)        # Command length
        
        # Add command, padding if necessary
        command_padded = command + b'\x00' * (cmd_length - len(command)) if len(command) < cmd_length else command[:cmd_length]
        cbw += command_padded
        
        # Pad to 31 bytes total
        padding_needed = 31 - len(cbw)
        if padding_needed > 0:
            cbw += b'\x00' * padding_needed
            
        return cbw

    def send_command(self, command, expected_length=0, direction_in=True, lun=0, timeout=5000, data_out=None, name=None):
        """
        Send a SCSI command with robust error handling
        
        Args:
            command: SCSI command bytes
            expected_length: Expected data response length
            direction_in: True for device-to-host, False for host-to-device
            lun: Logical Unit Number
            timeout: USB timeout in milliseconds
            data_out: Optional data to send after command
            name: Command name for logging
            
        Returns:
            Tuple of (status, data)
        """
        if not self.is_connected or not self.device:
            logger.error("Device not connected")
            return None, None
        
        cmd_name = name if name else f"Command 0x{command[0]:02X}"
        logger.info(f"Sending {cmd_name}")
        
        # Record command start time
        start_time = time.time()
        
        # Build the CBW
        cbw = self.build_cbw(command, expected_length, direction_in, lun)
        
        # Debug info
        logger.debug(f"CBW ({len(cbw)} bytes): {binascii.hexlify(cbw).decode()}")
        logger.debug(f"Command Tag: 0x{self.tag:08X}")
        
        # Send CBW with retry logic
        try:
            # Send the CBW
            bytes_written = self.device.write(EP_OUT, cbw, timeout=timeout)
            logger.debug(f"Sent {bytes_written} bytes")
            
            # Wait before reading data - helps with timing-sensitive devices
            time.sleep(COMMAND_TIMING['READ_WRITE_DELAY'])
            
            # Read data if expected
            data = None
            if expected_length > 0 and direction_in:
                try:
                    logger.debug(f"Reading {expected_length} bytes of data")
                    data = self.device.read(EP_IN, expected_length, timeout=timeout)
                    logger.debug(f"Read {len(data)} bytes of data: {binascii.hexlify(data).decode() if len(data) <= 32 else binascii.hexlify(data[:32]).decode() + '...'}")
                except usb.core.USBTimeoutError:
                    logger.warning("Data read timed out")
                except usb.core.USBError as e:
                    logger.warning(f"Data read error: {str(e)}")
                    
                    # Handle pipe errors by clearing halt
                    if "pipe" in str(e).lower():
                        try:
                            logger.debug("Clearing halt on IN endpoint")
                            self.device.clear_halt(EP_IN)
                        except Exception as ce:
                            logger.warning(f"Clear halt error: {str(ce)}")
                    
                    # Check for device disconnection
                    if "no such device" in str(e).lower():
                        logger.error("Device disconnected during data read")
                        self.is_connected = False
                        return None, None
            
            # Send data if provided
            if data_out is not None and not direction_in:
                try:
                    logger.debug(f"Sending {len(data_out)} bytes of data: {binascii.hexlify(data_out).decode()}")
                    bytes_written = self.device.write(EP_OUT, data_out, timeout=timeout)
                    logger.debug(f"Sent {bytes_written} bytes of data")
                except Exception as e:
                    logger.warning(f"Data write error: {str(e)}")
            
            # Wait before reading CSW - critical for timing-sensitive devices
            time.sleep(COMMAND_TIMING['CSW_DELAY'])
            
            # Read CSW (13 bytes)
            try:
                logger.debug("Reading CSW")
                csw = self.device.read(EP_IN, 13, timeout=timeout)
                
                if len(csw) == 13:
                    csw_signature, csw_tag, residue, status = struct.unpack('<4sIIB', csw)
                    
                    logger.debug(f"CSW: {binascii.hexlify(csw).decode()}")
                    logger.debug(f"CSW Signature: {csw_signature}")
                    logger.debug(f"CSW Tag: 0x{csw_tag:08X} (Expected: 0x{self.tag:08X})")
                    logger.debug(f"Data Residue: {residue}")
                    
                    status_desc = SCSI_STATUS.get(status, "Unknown")
                    logger.info(f"Status: {status} ({status_desc})")
                    
                    # Update status tracking
                    self.last_status = status
                    if status == 0:
                        self.success_count += 1
                        self.error_count = 0  # Reset error count on success
                    else:
                        self.error_count += 1
                    
                    # Increment command counter
                    self.command_count += 1
                    
                    # Log execution time
                    exec_time = time.time() - start_time
                    logger.debug(f"Command execution time: {exec_time:.2f} seconds")
                    
                    return status, data
                else:
                    logger.warning(f"Invalid CSW length: {len(csw)}")
                    return None, data
            
            except usb.core.USBTimeoutError:
                logger.warning("CSW read timed out")
                self.error_count += 1
                return None, data
                
            except usb.core.USBError as e:
                logger.warning(f"CSW read error: {str(e)}")
                self.error_count += 1
                
                # Handle pipe errors by clearing halt
                if "pipe" in str(e).lower():
                    try:
                        logger.debug("Clearing halt on IN endpoint")
                        self.device.clear_halt(EP_IN)
                    except Exception as ce:
                        logger.warning(f"Clear halt error: {str(ce)}")
                
                # Check for device disconnection
                if "no such device" in str(e).lower():
                    logger.error("Device disconnected during CSW read")
                    self.is_connected = False
                    return None, data
                
                return None, data
                
        except usb.core.USBError as e:
            logger.error(f"Command send error: {str(e)}")
            self.error_count += 1
            
            # Check for device disconnection
            if "no such device" in str(e).lower():
                logger.error("Device disconnected during command send")
                self.is_connected = False
            
            return None, None

    def test_unit_ready(self):
        """Send TEST UNIT READY command"""
        status, _ = self.send_command(TEST_UNIT_READY_CMD, name="TEST UNIT READY")
        
        if status == 0:
            logger.info("Device is ready")
        else:
            logger.warning("Device not ready")
            
        # Delay after command
        time.sleep(COMMAND_TIMING['DEFAULT_DELAY'])
        return status == 0

    def inquiry(self):
        """Send INQUIRY command and parse response"""
        status, data = self.send_command(INQUIRY_CMD, expected_length=36, name="INQUIRY")
        
        if status == 0 and data is not None:
            # Parse INQUIRY data
            peripheral_qualifier = (data[0] >> 5) & 0x07
            peripheral_device_type = data[0] & 0x1F
            rmb = (data[1] >> 7) & 0x01
            version = data[2]
            
            vendor = data[8:16].tobytes().decode('ascii', errors='replace').strip()
            product = data[16:32].tobytes().decode('ascii', errors='replace').strip()
            revision = data[32:36].tobytes().decode('ascii', errors='replace').strip()
            
            logger.info("INQUIRY Response:")
            logger.info(f"  Peripheral Qualifier: {peripheral_qualifier}")
            logger.info(f"  Peripheral Device Type: {peripheral_device_type}")
            logger.info(f"  Removable Media: {'Yes' if rmb else 'No'}")
            logger.info(f"  Version: {version}")
            logger.info(f"  Vendor: {vendor}")
            logger.info(f"  Product: {product}")
            logger.info(f"  Revision: {revision}")
            
            # Delay after command
            time.sleep(COMMAND_TIMING['DEFAULT_DELAY'])
            return True
        else:
            logger.warning("INQUIRY command failed")
            # Longer delay after failure
            time.sleep(COMMAND_TIMING['POST_ERROR_DELAY'])
            return False

    def request_sense(self):
        """Send REQUEST SENSE command and parse response"""
        status, data = self.send_command(REQUEST_SENSE_CMD, expected_length=18, name="REQUEST SENSE")
        
        if status == 0 and data is not None:
            # Parse REQUEST SENSE data
            response_code = data[0] & 0x7F
            sense_key = data[2] & 0x0F
            asc = data[12]
            ascq = data[13]
            
            sense_key_desc = SENSE_KEYS.get(sense_key, "Unknown")
            
            logger.info("REQUEST SENSE Response:")
            logger.info(f"  Response Code: 0x{response_code:02X}")
            logger.info(f"  Sense Key: {sense_key} ({sense_key_desc})")
            logger.info(f"  ASC: 0x{asc:02X}")
            logger.info(f"  ASCQ: 0x{ascq:02X}")
            
            # Store last sense data
            self.last_sense = (sense_key, asc, ascq)
            
            # Delay after command
            time.sleep(COMMAND_TIMING['DEFAULT_DELAY'])
            return True
        else:
            logger.warning("REQUEST SENSE command failed")
            # Longer delay after failure
            time.sleep(COMMAND_TIMING['POST_ERROR_DELAY'])
            return False

    def send_f5_command(self, subcommand, data_out=None, expected_length=0):
        """Send F5 vendor-specific command"""
        cmd_name = {
            'INIT': "Initialize Display",
            'INIT_ALT': "Initialize Display (Alt)",
            'ANIMATION': "Animation Control",
            'SET_MODE': "Set Mode",
            'GET_STATUS': "Get Status",
            'CLEAR_SCREEN': "Clear Screen",
            'DISPLAY_IMAGE': "Display Image"
        }.get(subcommand, f"F5 {subcommand}")
        
        command = F5_COMMANDS.get(subcommand)
        if not command:
            logger.error(f"Unknown F5 subcommand: {subcommand}")
            return False
        
        # Direction is IN if we expect data, OUT if we're sending data
        direction_in = expected_length > 0
        
        # Longer timeout for F5 commands
        status, data = self.send_command(
            command, 
            expected_length=expected_length,
            direction_in=direction_in,
            timeout=10000,  # 10 seconds
            data_out=data_out,
            name=f"F5 {cmd_name}"
        )
        
        success = status == 0
        
        if success:
            logger.info(f"F5 {cmd_name} command succeeded")
        else:
            logger.warning(f"F5 {cmd_name} command failed with status {status}")
        
        # Delay after F5 command - longer than standard commands
        delay = COMMAND_TIMING['POST_ERROR_DELAY'] if not success else {
            'INIT': COMMAND_TIMING['INIT_DELAY'],
            'INIT_ALT': COMMAND_TIMING['INIT_DELAY'],
            'ANIMATION': COMMAND_TIMING['ANIMATION_DELAY'],
            'GET_STATUS': COMMAND_TIMING['STATUS_DELAY'],
            'CLEAR_SCREEN': COMMAND_TIMING['CLEAR_DELAY'],
            'SET_MODE': COMMAND_TIMING['DEFAULT_DELAY'],
            'DISPLAY_IMAGE': COMMAND_TIMING['DEFAULT_DELAY']
        }.get(subcommand, COMMAND_TIMING['DEFAULT_DELAY'])
        
        logger.debug(f"Waiting {delay}s after F5 command...")
        time.sleep(delay)
        
        return success, data

    def run_diagnostic_sequence(self):
        """Run a comprehensive diagnostic sequence"""
        logger.info("Starting comprehensive diagnostic sequence...")
        
        # Start with basic commands
        logger.info("\n=== Basic Command Tests ===")
        self.test_unit_ready()
        self.inquiry()
        self.request_sense()
        
        # Test reset capability
        logger.info("\n=== Device Reset Test ===")
        try:
            logger.info("Resetting device...")
            self.device.reset()
            time.sleep(3)  # Longer delay after reset
            logger.info("Device reset complete")
            
            # Re-test basic commands after reset
            self.test_unit_ready()
            self.inquiry()
            self.request_sense()
        except Exception as e:
            logger.warning(f"Device reset error: {str(e)}")
        
        # Test ALi-specific F5 commands
        logger.info("\n=== ALi LCD Device Commands ===")
        
        # Initialize display
        logger.info("\n--- F5 Init Commands ---")
        init_success, _ = self.send_f5_command('INIT')
        
        # Try alternative init if first fails
        if not init_success:
            logger.info("Trying alternative init command...")
            time.sleep(3)  # Wait before retry
            init_success, _ = self.send_f5_command('INIT_ALT')
        
        # Read status
        logger.info("\n--- F5 Status Command ---")
        self.send_f5_command('GET_STATUS', expected_length=8)
        
        # Set mode command with mode data
        logger.info("\n--- F5 Mode Command ---")
        self.send_f5_command('SET_MODE', data_out=b'\x05\x00\x00\x00')
        
        # Animation control
        logger.info("\n--- F5 Animation Command ---")
        self.send_f5_command('ANIMATION', data_out=b'\x00')  # 0x00 = stop animation
        
        # Clear screen
        logger.info("\n--- F5 Clear Screen Command ---")
        self.send_f5_command('CLEAR_SCREEN')
        
        # Try TUR again to see if status changed
        logger.info("\n=== Post-Command Verification ===")
        self.test_unit_ready()
        self.request_sense()
        
        logger.info("Diagnostic sequence complete")
        return True

    def run_monitoring_sequence(self, duration=60):
        """Run a monitoring sequence for a specified duration"""
        logger.info(f"Starting monitoring sequence for {duration} seconds...")
        
        start_time = time.time()
        check_interval = 5  # Check every 5 seconds
        
        while time.time() - start_time < duration:
            elapsed = time.time() - start_time
            remaining = duration - elapsed
            logger.info(f"Monitoring - Elapsed: {int(elapsed)}s, Remaining: {int(remaining)}s")
            
            # Check if device is still connected
            if not self.is_connected:
                logger.warning("Device disconnected during monitoring")
                if self.reconnect():
                    logger.info("Device successfully reconnected")
                else:
                    logger.error("Failed to reconnect, aborting monitoring")
                    break
            
            # Send TEST UNIT READY to keep connection alive
            ready = self.test_unit_ready()
            
            # If too many consecutive errors, attempt recovery
            if self.error_count >= self.max_errors:
                logger.warning(f"Detected {self.error_count} consecutive errors, attempting recovery")
                self.request_sense()  # Get error information
                
                # Try to reconnect
                if self.reconnect():
                    logger.info("Recovery successful")
                else:
                    logger.error("Recovery failed")
                    time.sleep(check_interval)  # Wait before continuing
            
            # Periodically get status
            if int(elapsed) % 30 == 0:  # Every 30 seconds
                logger.info("Periodic status check")
                status_success, _ = self.send_f5_command('GET_STATUS', expected_length=8)
                
                # If status fails, try a more comprehensive recovery
                if not status_success:
                    logger.warning("Status check failed, trying more commands")
                    self.request_sense()
                    self.test_unit_ready()
            
            # Sleep until next check
            time.sleep(check_interval)
        
        logger.info(f"Monitoring complete - Total Duration: {int(time.time() - start_time)}s")
        return True

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Advanced ALi LCD Device Diagnostic Tool')
    parser.add_argument('--diagnostic', action='store_true', help='Run diagnostic sequence')
    parser.add_argument('--monitor', action='store_true', help='Run monitoring sequence')
    parser.add_argument('--duration', type=int, default=60, help='Duration for monitoring in seconds')
    parser.add_argument('--logfile', type=str, help='Log to file in addition to console')
    
    args = parser.parse_args()
    
    # Setup file logging if requested
    if args.logfile:
        file_handler = logging.FileHandler(args.logfile)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
    
    # Check if running as root/sudo
    if os.geteuid() != 0:
        logger.error("This script must be run as root or with sudo")
        return 1
    
    logger.info("Advanced ALi LCD Device Diagnostic Tool")
    logger.info(f"Starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Create diagnostic instance
        diagnostics = ALiLCDDiagnostics()
        
        # Connect to device
        if not diagnostics.connect():
            logger.error("Failed to connect to device")
            return 1
        
        if args.diagnostic:
            # Run diagnostic sequence
            diagnostics.run_diagnostic_sequence()
        elif args.monitor:
            # Run monitoring sequence
            diagnostics.run_monitoring_sequence(args.duration)
        else:
            # Default: run both
            diagnostics.run_diagnostic_sequence()
            diagnostics.run_monitoring_sequence(args.duration)
        
        # Disconnect
        diagnostics.disconnect()
        logger.info("Diagnostics completed successfully")
        return 0
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
