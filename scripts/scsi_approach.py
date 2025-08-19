#!/usr/bin/env python3
"""
SCSI Approach for the ALi LCD device.
This script attempts to communicate with the ALi LCD device using standard SCSI commands
before trying the custom F5 commands. This is based on the understanding that the device
may need proper SCSI initialization before accepting vendor-specific commands.
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
INQUIRY_CMD = b'\x12\x00\x00\x00\x24\x00'  # Standard INQUIRY, 36 bytes
MODE_SENSE_CMD = b'\x5A\x00\x00\x00\x10\x00'  # MODE SENSE(10), 16 bytes
REQUEST_SENSE_CMD = b'\x03\x00\x00\x00\x12\x00'  # REQUEST SENSE, 18 bytes
READ_CAPACITY_CMD = b'\x25\x00\x00\x00\x00\x00\x00\x00\x00\x00'  # READ CAPACITY

# Custom F5 Commands - We'll try different variations
CMD_F5_01_V1 = b'\xF5\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
CMD_F5_01_V2 = b'\xF5\x01\x00\x00\x00\x00'  # Shorter version without padding
CMD_F5_01_V3 = b'\xF5\x01'  # Minimal version

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
            
            # Reset the device - Skip this, it might be causing issues
            # try:
            #     self.device.reset()
            #     time.sleep(2)  # Give the device time to reset
            # except Exception as e:
            #     logger.warning(f"Could not reset device: {str(e)}")
            
            # Set configuration - Using the first configuration by default
            try:
                cfg = self.device[0]
                self.device.set_configuration(cfg.bConfigurationValue)
                logger.info(f"Set configuration to {cfg.bConfigurationValue}")
            except Exception as e:
                logger.warning(f"Could not set configuration: {str(e)}")
                try:
                    # Try default configuration
                    self.device.set_configuration()
                    logger.info("Set default configuration")
                except Exception as e2:
                    logger.warning(f"Could not set default configuration: {str(e2)}")
                
            # Claim interface
            try:
                usb.util.claim_interface(self.device, 0)
                logger.info("Claimed interface 0")
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

def send_scsi_command(device, command, expected_data_length=0, cmd_length=None, lun=0, longer_timeout=False):
    """Send a SCSI command and handle response with flexible command length"""
    
    timeout = 5000 if longer_timeout else 1000  # Use longer timeout for slow operations
    
    # If command length not specified, use actual length up to 16 bytes max
    if cmd_length is None:
        cmd_length = min(len(command), 16)
    
    # Construct the Command Block Wrapper (CBW)
    # CBW format:
    # - 'USBC' signature (4 bytes)
    # - Command tag (4 bytes, incremental)
    # - Data transfer length (4 bytes)
    # - Flags (1 byte, 0x80 for IN, 0x00 for OUT)
    # - LUN (1 byte)
    # - Command length (1 byte)
    # - Command (variable length)
    
    # For TEST_UNIT_READY command, no data is expected (direction is OUT)
    direction_flag = 0x80 if expected_data_length > 0 else 0x00
    
    # Generate a command tag - using timestamp for uniqueness
    tag = int(time.time() * 1000) & 0xFFFFFFFF
    
    cbw = struct.pack('<4sIIBBB', 
                      b'USBC', 
                      tag, 
                      expected_data_length, 
                      direction_flag, 
                      lun,  # LUN
                      cmd_length)
    
    # Add command, ensuring it's the right length
    if len(command) < cmd_length:
        command = command + b'\x00' * (cmd_length - len(command))
    elif len(command) > cmd_length:
        command = command[:cmd_length]
    
    cbw += command
    
    # Ensure the CBW is 31 bytes total
    padding_needed = 31 - len(cbw)
    if padding_needed > 0:
        cbw += b'\x00' * padding_needed
        
    logger.debug(f"Sending CBW: {cbw.hex()}")
    
    # Write Command Block Wrapper (CBW)
    bytes_written = device.write(EP_OUT, cbw, timeout=timeout)
    if bytes_written == 0:
        logger.warning("Failed to send command")
        return None, None
    
    # Read data if expected
    data = None
    if expected_data_length > 0:
        data = device.read(EP_IN, expected_data_length, timeout=timeout)
        if data is None:
            logger.warning(f"Failed to read {expected_data_length} bytes of data")
    
    # Read Command Status Wrapper (CSW) - 13 bytes
    csw = device.read(EP_IN, 13, timeout=timeout)
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
            
        if status == 0:
            logger.debug(f"Command successful, status: {status}")
        else:
            logger.warning(f"Command failed with status {status}")
            
        return status, data
    else:
        logger.warning(f"Received CSW with incorrect length: {len(csw)}")
        return None, data

def send_inquiry(device):
    """Send a standard SCSI INQUIRY command to the device"""
    logger.info("Sending INQUIRY command...")
    status, data = send_scsi_command(device, INQUIRY_CMD, expected_data_length=36)
    
    if status == 0 and data is not None:
        vendor = data[8:16].tobytes().decode('ascii', errors='replace').strip()
        product = data[16:32].tobytes().decode('ascii', errors='replace').strip()
        revision = data[32:36].tobytes().decode('ascii', errors='replace').strip()
        
        logger.info(f"Device info - Vendor: {vendor}, Product: {product}, Revision: {revision}")
        return True
    else:
        logger.warning("INQUIRY command failed")
        return False

def send_request_sense(device):
    """Send a REQUEST SENSE command to get error information"""
    logger.info("Sending REQUEST SENSE command...")
    status, data = send_scsi_command(device, REQUEST_SENSE_CMD, expected_data_length=18)
    
    if status == 0 and data is not None:
        sense_key = data[2] & 0x0F
        asc = data[12]
        ascq = data[13]
        
        logger.info(f"Sense data - Sense Key: {sense_key}, ASC: {asc}, ASCQ: {ascq}")
        return True
    else:
        logger.warning("REQUEST SENSE command failed")
        return False

def try_different_test_unit_ready(device):
    """Try different variations of TEST UNIT READY command"""
    variants = [
        (b'\x00\x00\x00\x00\x00\x00', 6, "Standard 6-byte"),
        (b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 12, "Extended 12-byte"),
        (b'\x00', 1, "Minimal 1-byte")
    ]
    
    for cmd, length, description in variants:
        logger.info(f"Trying TEST UNIT READY variant: {description}")
        status, _ = send_scsi_command(device, cmd, cmd_length=length)
        
        if status == 0:
            logger.info(f"TEST UNIT READY ({description}) succeeded!")
            return True
        else:
            logger.warning(f"TEST UNIT READY ({description}) failed with status {status}")
        
        # Wait between attempts
        time.sleep(1)
    
    return False

def try_different_f5_commands(device):
    """Try different variations of the F5 command"""
    variants = [
        (CMD_F5_01_V1, 16, "Standard 16-byte"),
        (CMD_F5_01_V2, 6, "Short 6-byte"),
        (CMD_F5_01_V3, 2, "Minimal 2-byte")
    ]
    
    for cmd, length, description in variants:
        logger.info(f"Trying F5 01 variant: {description}")
        
        # Wait for a while before sending
        time.sleep(2)
        
        status, _ = send_scsi_command(device, cmd, cmd_length=length, longer_timeout=True)
        
        if status == 0:
            logger.info(f"F5 01 command ({description}) succeeded!")
            return True
        elif status is not None:
            logger.warning(f"F5 01 command ({description}) failed with status {status}")
        else:
            logger.warning(f"F5 01 command ({description}) failed with no status")
        
        # Check if device is still responding
        time.sleep(2)
        test_status, _ = send_scsi_command(device, TEST_UNIT_READY_CMD)
        if test_status is None:
            logger.warning("Device not responding after F5 command attempt")
            return False
        
        # Wait between attempts
        time.sleep(3)
    
    return False

def main():
    parser = argparse.ArgumentParser(description='ALi LCD Display SCSI Communication Tool')
    parser.add_argument('--skip-init', action='store_true',
                        help='Skip standard SCSI initialization')
    parser.add_argument('--log-file', type=str,
                        help='Log to file in addition to console')
    
    args = parser.parse_args()
    
    # Setup file logging if requested
    if args.log_file:
        file_handler = logging.FileHandler(args.log_file)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
    
    logger.info("ALi LCD Display SCSI Communication Tool")
    logger.info(f"Starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Connect to device
    device = USBDevice(VENDOR_ID, PRODUCT_ID)
    if not device.connect():
        logger.error("Failed to connect to device")
        return 1
    
    try:
        # Try plain TEST UNIT READY first
        logger.info("Sending initial TEST UNIT READY to check device status...")
        status, _ = send_scsi_command(device, TEST_UNIT_READY_CMD)
        
        if status == 0:
            logger.info("Device is ready")
        else:
            logger.warning(f"Device returned status {status} for TEST UNIT READY")
            
            # If device reports not ready, try to get sense data
            if not args.skip_init:
                send_request_sense(device)
        
        # Let's try some standard SCSI commands if not skipping initialization
        if not args.skip_init:
            # Try INQUIRY command
            logger.info("Attempting standard SCSI initialization...")
            
            inquiry_success = send_inquiry(device)
            
            # Wait a bit after initialization
            logger.info("Waiting after SCSI initialization...")
            time.sleep(5)
            
            # Try TEST UNIT READY again
            logger.info("Sending TEST UNIT READY after initialization...")
            status, _ = send_scsi_command(device, TEST_UNIT_READY_CMD)
            
            if status == 0:
                logger.info("Device is ready after initialization")
            else:
                logger.warning(f"Device returned status {status} for TEST UNIT READY after initialization")
        
        # Try different TEST UNIT READY variations
        logger.info("Trying different TEST UNIT READY command variations...")
        tur_success = try_different_test_unit_ready(device)
        
        if tur_success:
            logger.info("Found a working TEST UNIT READY variant")
        else:
            logger.warning("No TEST UNIT READY variants succeeded")
        
        # Now try different F5 command variants
        logger.info("Attempting to send F5 command in different variations...")
        f5_success = try_different_f5_commands(device)
        
        if f5_success:
            logger.info("Successfully found a working F5 command variant!")
        else:
            logger.warning("All F5 command variants failed")
        
        # Final test to see if device is still responding
        logger.info("Final communication test...")
        status, _ = send_scsi_command(device, TEST_UNIT_READY_CMD)
        
        if status is not None:
            logger.info(f"Device is still responsive with status {status}")
        else:
            logger.warning("Device is no longer responsive")
        
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
