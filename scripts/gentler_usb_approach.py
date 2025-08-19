#!/usr/bin/env python3
"""
Gentler USB approach for the ALi LCD device.
This script takes a more cautious approach to communicate with the ALi LCD device.

Key changes:
1. Much longer delay before sending F5 commands
2. Proper detection of device state transitions 
3. More gradual and careful state transitions
4. Proper error handling and recovery
"""

import usb.core
import usb.util
import time
import logging
import struct
import sys
import argparse
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# USB Constants
VENDOR_ID = 0x0402
PRODUCT_ID = 0x3922
EP_OUT = 0x02
EP_IN = 0x81
TIMEOUT = 1000  # 1 second

# SCSI Commands
TEST_UNIT_READY_CMD = b'\x00\x00\x00\x00\x00\x00'
CMD_F5_01 = b'\xF5\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
CMD_F5_20 = b'\xF5\x20\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
CMD_F5_25 = b'\xF5\x25\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
CMD_F5_37 = b'\xF5\x37\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

# USB device state tracking
successful_commands = 0
total_commands = 0
max_consecutive_failures = 0
current_consecutive_failures = 0
last_csw_status = None

class USBDevice:
    def __init__(self, vendor_id, product_id):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.device = None
        self.connected = False
        self.consecutive_failures = 0
        self.max_retries = 5
        self.retry_delays = [0.5, 1, 2, 4, 8]  # Exponential backoff

    def connect(self):
        """Connect to the USB device and claim interface"""
        try:
            logger.info(f"Looking for USB device {self.vendor_id:04x}:{self.product_id:04x}...")
            
            # Find the device
            self.device = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)
            
            if self.device is None:
                logger.error("Device not found")
                return False
                
            logger.info("Device found")
            
            # Handle Linux kernel driver attachment
            try:
                if self.device.is_kernel_driver_active(0):
                    logger.info("Detaching kernel driver")
                    self.device.detach_kernel_driver(0)
            except Exception as e:
                logger.warning(f"Kernel driver handling error: {str(e)}")
            
            # Reset the device
            try:
                self.device.reset()
                time.sleep(2)  # Give the device time to reset
            except Exception as e:
                logger.warning(f"Could not reset device: {str(e)}")
            
            # Set configuration
            try:
                self.device.set_configuration()
            except Exception as e:
                logger.warning(f"Could not set configuration: {str(e)}")
                
            # Claim interface
            try:
                usb.util.claim_interface(self.device, 0)
            except Exception as e:
                logger.warning(f"Could not claim interface: {str(e)}")
                
            self.connected = True
            logger.info("USB device connected and interface claimed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to USB device: {str(e)}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from the USB device"""
        if self.device:
            try:
                usb.util.release_interface(self.device, 0)
                logger.info("Released USB interface")
            except Exception as e:
                logger.warning(f"Error releasing interface: {str(e)}")
                
        self.connected = False
        logger.info("Disconnected from USB device")

    def write(self, endpoint, data, timeout=TIMEOUT):
        """Write data to an endpoint with retry logic"""
        if not self.connected or self.device is None:
            logger.error("Cannot write: Device not connected")
            return 0
            
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Writing {len(data)} bytes directly to EP_OUT")
                bytes_written = self.device.write(endpoint, data, timeout=timeout)
                logger.debug(f"Successfully wrote {bytes_written} bytes")
                self.consecutive_failures = 0
                return bytes_written
            except Exception as e:
                self.consecutive_failures += 1
                logger.warning(f"USB Error on write attempt {attempt+1}/{self.max_retries}: {str(e)}")
                
                if "no such device" in str(e).lower() or "device disconnected" in str(e).lower():
                    logger.warning("Device disconnected")
                    self.connected = False
                    return 0
                    
                if attempt < self.max_retries - 1:
                    delay = self.retry_delays[min(attempt, len(self.retry_delays)-1)]
                    logger.debug(f"Retrying write in {delay} seconds...")
                    time.sleep(delay)
                    
        logger.error("Failed to write to device after multiple attempts")
        return 0

    def read(self, endpoint, length, timeout=TIMEOUT):
        """Read data from an endpoint with retry logic"""
        if not self.connected or self.device is None:
            logger.error("Cannot read: Device not connected")
            return None
            
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Reading {length} bytes directly from EP_IN")
                data = self.device.read(endpoint, length, timeout=timeout)
                logger.debug(f"Successfully read {len(data)} bytes")
                self.consecutive_failures = 0
                return data
            except usb.core.USBTimeoutError:
                logger.debug("Read timed out, may be normal for some commands")
                return None
            except Exception as e:
                self.consecutive_failures += 1
                logger.warning(f"USB Error on read attempt {attempt+1}/{self.max_retries}: {str(e)}")
                
                if "no such device" in str(e).lower() or "device disconnected" in str(e).lower():
                    logger.warning("Device disconnected")
                    self.connected = False
                    return None
                    
                if attempt < self.max_retries - 1:
                    delay = self.retry_delays[min(attempt, len(self.retry_delays)-1)]
                    logger.debug(f"Retrying read in {delay} seconds...")
                    time.sleep(delay)
                    
        logger.error("Failed to read from device after multiple attempts")
        return None

def send_scsi_command(device, command, expected_data_length=0):
    """Send a SCSI command and handle response"""
    global total_commands, successful_commands, last_csw_status
    
    total_commands += 1
    
    # Construct the Command Block Wrapper (CBW)
    # CBW format:
    # - 'USBC' signature (4 bytes)
    # - Command tag (4 bytes, incremental)
    # - Data transfer length (4 bytes)
    # - Flags (1 byte, 0x80 for IN, 0x00 for OUT)
    # - LUN (1 byte)
    # - Command length (1 byte)
    # - Command (16 bytes)
    
    # For TEST_UNIT_READY command, no data is expected (direction is OUT)
    direction_flag = 0x80 if expected_data_length > 0 else 0x00
    
    # Generate a command tag
    tag = total_commands & 0xFFFFFFFF
    
    cbw = struct.pack('<4sIIBBB', 
                      b'USBC', 
                      tag, 
                      expected_data_length, 
                      direction_flag, 
                      0,  # LUN always 0
                      len(command))
    
    # Pad command to 16 bytes if needed
    if len(command) < 16:
        command = command + b'\x00' * (16 - len(command))
    
    cbw += command
    
    # Write Command Block Wrapper (CBW)
    bytes_written = device.write(EP_OUT, cbw)
    if bytes_written == 0:
        logger.warning("Failed to send command")
        return None, None
    
    # Read data if expected
    data = None
    if expected_data_length > 0:
        data = device.read(EP_IN, expected_data_length)
        if data is None:
            logger.warning(f"Failed to read {expected_data_length} bytes of data")
    
    # Read Command Status Wrapper (CSW)
    csw = device.read(EP_IN, 13)
    if csw is None:
        logger.warning("Failed to read CSW")
        return None, data
    
    # Parse CSW
    if len(csw) == 13:
        signature, returned_tag, residue, status = struct.unpack('<4sIIB', csw)
        
        if signature != b'USBS':
            logger.warning(f"Invalid CSW signature: {signature}")
            
        if returned_tag != tag:
            logger.warning(f"CSW tag mismatch: expected {tag}, got {returned_tag}")
            
        last_csw_status = status
        
        if status == 0:
            successful_commands += 1
            logger.debug(f"Command successful, status: {status}")
        else:
            logger.warning(f"Command failed with status {status}")
            
        return status, data
    else:
        logger.warning(f"Received CSW with incorrect length: {len(csw)}")
        return None, data

def device_stabilization(device, duration=90, interval=0.5):
    """
    Send TEST_UNIT_READY commands for a specified duration to stabilize the connection.
    
    Args:
        device: USB device object
        duration: Duration in seconds to run stabilization
        interval: Time between commands in seconds
    """
    global successful_commands, total_commands
    
    start_time = time.time()
    end_time = start_time + duration
    successful_count = 0
    needed_success_count = 10  # Need to see at least 10 successful commands in a row
    
    logger.info(f"Starting device stabilization phase ({duration} seconds)...")
    
    # Reset counters
    successful_commands = 0
    total_commands = 0
    
    consecutive_successes = 0
    last_log_time = start_time
    
    while time.time() < end_time:
        elapsed = time.time() - start_time
        remaining = end_time - time.time()
        
        # Log progress every ~5 seconds
        if time.time() - last_log_time >= 5:
            success_rate = (successful_commands / max(total_commands, 1)) * 100
            logger.info(f"Stabilization progress: {elapsed:.1f}s elapsed, {remaining:.1f}s remaining, "
                       f"{consecutive_successes}/{needed_success_count} successful")
            last_log_time = time.time()
        
        # Send TEST_UNIT_READY command
        status, _ = send_scsi_command(device, TEST_UNIT_READY_CMD)
        
        if status == 0:
            consecutive_successes += 1
            if consecutive_successes >= needed_success_count:
                logger.info(f"Device appears stable after {elapsed:.1f} seconds")
                return True
        else:
            consecutive_successes = 0
        
        time.sleep(interval)
    
    # Check if we achieved stability
    success_rate = (successful_commands / max(total_commands, 1)) * 100
    logger.info(f"Stabilization complete: {total_commands} commands sent, {success_rate:.1f}% success rate")
    
    if consecutive_successes >= needed_success_count:
        logger.info("Device appears stable")
        return True
    else:
        logger.warning("Device may not be in a fully stable state yet")
        return False

def send_f5_command(device, cmd, cmd_name, wait_time=3):
    """Send an F5 command and handle the response with extended wait time"""
    logger.info(f"Sending direct {cmd_name} command...")
    
    # Wait for a while before sending to ensure the device is ready
    time.sleep(1.0)
    
    status, _ = send_scsi_command(device, cmd)
    
    if status == 0:
        logger.info(f"{cmd_name} command succeeded")
    else:
        logger.warning(f"Warning: {cmd_name} command failed with status {status}")
    
    # Wait for device to process the command
    logger.info(f"Waiting {wait_time} seconds for device to process {cmd_name} command...")
    time.sleep(wait_time)
    
    # Verify device is still responsive
    verify_status, _ = send_scsi_command(device, TEST_UNIT_READY_CMD)
    if verify_status is None:
        logger.warning(f"Device not responsive after {cmd_name} command")
        return False
    
    return status == 0

def wait_for_mode_change(device, wait_time=5, check_interval=0.5):
    """Wait for the device to change modes and stabilize"""
    logger.info(f"Waiting {wait_time} seconds for mode change to take effect...")
    
    # Wait a bit first
    time.sleep(2)
    
    # Then periodically check if device is still responsive
    end_time = time.time() + wait_time
    while time.time() < end_time:
        status, _ = send_scsi_command(device, TEST_UNIT_READY_CMD)
        if status is None:
            logger.warning("Device not responding during mode change")
        elif status != 0:
            logger.warning(f"Device returned non-zero status during mode change: {status}")
        
        time.sleep(check_interval)
    
    # Final check
    status, _ = send_scsi_command(device, TEST_UNIT_READY_CMD)
    if status == 0:
        logger.info("Device is responsive after mode change")
        return True
    else:
        logger.warning("Device may not be stable after mode change")
        return False

def main():
    parser = argparse.ArgumentParser(description='ALi LCD Display Communication Tool')
    parser.add_argument('--stabilize-time', type=int, default=90, 
                        help='Time in seconds to stabilize connection before sending commands')
    parser.add_argument('--test-only', action='store_true',
                        help='Only test connection, do not send any F5 commands')
    parser.add_argument('--log-file', type=str,
                        help='Log to file in addition to console')
    
    args = parser.parse_args()
    
    # Setup file logging if requested
    if args.log_file:
        file_handler = logging.FileHandler(args.log_file)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
    
    logger.info("ALi LCD Display Communication Tool")
    logger.info(f"Starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Connect to device
    device = USBDevice(VENDOR_ID, PRODUCT_ID)
    if not device.connect():
        logger.error("Failed to connect to device")
        return 1
    
    try:
        # Stabilization phase
        stable = device_stabilization(device, duration=args.stabilize_time)
        if not stable and not args.test_only:
            logger.warning("Device stabilization incomplete, continuing anyway")
        
        # If test-only mode, exit here
        if args.test_only:
            logger.info("Test-only mode, not sending any F5 commands")
            return 0
        
        # First phase: Send F5 01 (Initialize Display)
        logger.info("Sending enhanced initialization sequence...")
        
        # Allow extra time after stabilization
        logger.info("Waiting 3 more seconds to ensure device is ready...")
        time.sleep(3)
        
        # Send F5 01 command with extended wait time
        if not send_f5_command(device, CMD_F5_01, "F5 01 command (Initialize Display)", wait_time=5):
            logger.error("Failed to initialize display (F5 01)")
            return 1
        
        # Wait longer between major commands
        logger.info("Waiting for device to process initialization...")
        time.sleep(10)
        
        # Second phase: Send F5 20 (Set Mode)
        if not send_f5_command(device, CMD_F5_20, "F5 20 command (Set Mode)", wait_time=8):
            logger.error("Failed to set mode (F5 20)")
            return 1
        
        # Wait for mode change
        if not wait_for_mode_change(device, wait_time=10):
            logger.warning("Device may not have changed modes properly")
        
        # Third phase: Send F5 25 (Set Frame Rate)
        if not send_f5_command(device, CMD_F5_25, "F5 25 command (Set Frame Rate)", wait_time=5):
            logger.error("Failed to set frame rate (F5 25)")
            return 1
        
        # Wait between commands
        time.sleep(5)
        
        # Fourth phase: Send F5 37 (Get/Set Parameters)
        if not send_f5_command(device, CMD_F5_37, "F5 37 command (Get/Set Parameters)", wait_time=5):
            logger.error("Failed to get/set parameters (F5 37)")
            return 1
        
        logger.info("All commands completed successfully")
        
        # Keep connection open to allow manual inspection
        logger.info("Keeping connection open for 30 seconds to observe device behavior...")
        
        # Send periodic TEST_UNIT_READY to verify device is still responsive
        for i in range(6):
            time.sleep(5)
            status, _ = send_scsi_command(device, TEST_UNIT_READY_CMD)
            if status is None:
                logger.warning(f"Device not responsive at T+{i*5} seconds")
            else:
                logger.info(f"Device still responsive at T+{i*5} seconds with status {status}")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        return 1
    finally:
        # Always disconnect
        device.disconnect()
        logger.info("Program complete")

if __name__ == "__main__":
    sys.exit(main())
