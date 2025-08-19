#!/usr/bin/env python3
"""
Enhanced SCSI Approach for the ALi LCD device.
This script attempts to communicate with the ALi LCD device using standard SCSI commands
followed by the specific protocol sequence documented for this device. It implements
lifecycle-aware communication based on device states.
"""

import usb.core
import usb.util
import time
import logging
import struct
import sys
import argparse
from datetime import datetime
import random

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

# ALi LCD Device Custom Commands
F5_INITIALIZE_DISPLAY = b'\xF5\x01\x00\x00\x00\x00'
F5_ANIMATION_CONTROL = b'\xF5\x10\x00\x00\x00\x00'
F5_SET_MODE = b'\xF5\x20\x00\x00\x00\x00'
F5_GET_STATUS = b'\xF5\x30\x00\x00\x00\x00'
F5_CLEAR_SCREEN = b'\xF5\xA0\x00\x00\x00\x00'
F5_DISPLAY_IMAGE = b'\xF5\xB0\x00\x00\x00\x00'

# Device States
STATE_ANIMATION = "ANIMATION"
STATE_CONNECTING = "CONNECTING"
STATE_CONNECTED = "CONNECTED"
STATE_DISCONNECTED = "DISCONNECTED"

class ALiLCDDevice:
    def __init__(self, vendor_id, product_id):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.device = None
        self.connected = False
        self.consecutive_failures = 0
        self.max_retries = 5
        self.retry_delays = [0.5, 1, 2, 4, 8]  # Exponential backoff
        self.command_tag = random.randint(1, 0xFFFFFFFF)  # Random initial tag
        self.current_state = STATE_ANIMATION
        self.state_start_time = time.time()
        self.command_count = 0
        self.last_command_time = time.time()
        
        # State-specific timing
        self.command_delays = {
            STATE_ANIMATION: 0.5,      # Longer delays in animation state
            STATE_CONNECTING: 0.3,     # Moderate delays in connecting
            STATE_CONNECTED: 0.1,      # Short delays when connected
            STATE_DISCONNECTED: 1.0    # Long delays when disconnected
        }
        
        # Tag validation strictness by state
        self.tag_validation = {
            STATE_ANIMATION: False,    # Ignore tag mismatches in animation
            STATE_CONNECTING: False,   # Ignore tag mismatches when connecting
            STATE_CONNECTED: True,     # Strict validation when connected
            STATE_DISCONNECTED: False  # Ignore when disconnected
        }

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
            self.current_state = STATE_ANIMATION
            self.state_start_time = time.time()
            self.command_count = 0
            logger.info("USB device connected and interface claimed")
            logger.info(f"Initial state: {self.current_state}")
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
                logger.debug(f"Writing {len(data)} bytes to EP_OUT")
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
                logger.debug(f"Reading {length} bytes from EP_IN")
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
                
                # Clear halt on endpoint for pipe errors
                if "pipe" in str(e).lower():
                    try:
                        logger.debug(f"Clearing halt on endpoint 0x{endpoint:02x}")
                        self.device.clear_halt(endpoint)
                    except Exception as clear_e:
                        logger.warning(f"Failed to clear halt: {str(clear_e)}")
                    
                if attempt < self.max_retries - 1:
                    delay = self.retry_delays[min(attempt, len(self.retry_delays)-1)]
                    logger.debug(f"Retrying read in {delay} seconds...")
                    time.sleep(delay)
                    
        logger.error("Failed to read from device after multiple attempts")
        return None

    def update_state(self):
        """Update the device state based on time and command count"""
        current_time = time.time()
        time_in_state = current_time - self.state_start_time
        time_since_last_command = current_time - self.last_command_time
        
        # Check for state transitions
        if self.current_state == STATE_ANIMATION:
            # Animation -> Connecting after ~56-58 seconds of commands
            if time_in_state > 56 and self.command_count > 100:
                self.current_state = STATE_CONNECTING
                self.state_start_time = current_time
                logger.info(f"State transition: {STATE_ANIMATION} -> {STATE_CONNECTING}")
                
        elif self.current_state == STATE_CONNECTING:
            # Connecting -> Connected after a few seconds
            if time_in_state > 3:
                self.current_state = STATE_CONNECTED
                self.state_start_time = current_time
                logger.info(f"State transition: {STATE_CONNECTING} -> {STATE_CONNECTED}")
                
        elif self.current_state == STATE_CONNECTED:
            # Connected -> Disconnected if no commands for ~5 seconds
            if time_since_last_command > 5:
                self.current_state = STATE_DISCONNECTED
                self.state_start_time = current_time
                logger.info(f"State transition: {STATE_CONNECTED} -> {STATE_DISCONNECTED}")
                
        elif self.current_state == STATE_DISCONNECTED:
            # Disconnected -> Animation after 10 seconds
            if time_in_state > 10:
                self.current_state = STATE_ANIMATION
                self.state_start_time = current_time
                self.command_count = 0
                logger.info(f"State transition: {STATE_DISCONNECTED} -> {STATE_ANIMATION}")
        
        return self.current_state

    def send_command(self, command, expected_data_length=0, cmd_length=None, lun=0, timeout=TIMEOUT):
        """Send a command with state-aware behavior"""
        # Update state before sending command
        self.update_state()
        
        # Apply state-specific command delay
        time.sleep(self.command_delays[self.current_state])
        
        # Send the command
        status, data = self.send_scsi_command(command, expected_data_length, cmd_length, lun, timeout)
        
        # Update command metrics
        self.command_count += 1
        self.last_command_time = time.time()
        
        return status, data

    def send_scsi_command(self, command, expected_data_length=0, cmd_length=None, lun=0, timeout=TIMEOUT):
        """Send a SCSI command and handle response with state-aware tag handling"""
        
        # If command length not specified, use actual length up to 16 bytes max
        if cmd_length is None:
            cmd_length = min(len(command), 16)
        
        # Construct the Command Block Wrapper (CBW)
        direction_flag = 0x80 if expected_data_length > 0 else 0x00
        
        # Generate a command tag - using incremental tag by default
        tag = self.command_tag
        self.command_tag = (self.command_tag + 1) & 0xFFFFFFFF
        
        cbw = struct.pack('<4sIIBBB', 
                          b'USBC',          # CBW signature
                          tag,              # Command tag
                          expected_data_length,  # Data transfer length
                          direction_flag,   # Direction flag
                          lun,              # LUN
                          cmd_length)       # Command length
        
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
        bytes_written = self.write(EP_OUT, cbw, timeout=timeout)
        if bytes_written == 0:
            logger.warning("Failed to send command")
            return None, None
        
        # Read data if expected
        data = None
        if expected_data_length > 0:
            data = self.read(EP_IN, expected_data_length, timeout=timeout)
            if data is None:
                logger.warning(f"Failed to read {expected_data_length} bytes of data")
        
        # Read Command Status Wrapper (CSW) - 13 bytes
        csw = self.read(EP_IN, 13, timeout=timeout)
        if csw is None:
            logger.warning("Failed to read CSW")
            return None, data
        
        # Parse CSW
        if len(csw) == 13:
            signature, returned_tag, residue, status = struct.unpack('<4sIIB', csw)
            
            if signature != b'USBS':
                logger.warning(f"Invalid CSW signature: {signature}")
                
            # Check tag based on state-specific validation rules
            if self.tag_validation[self.current_state] and returned_tag != tag:
                logger.warning(f"CSW tag mismatch: expected {tag}, got {returned_tag}")
                # In connected state, tag mismatches are serious
                if self.current_state == STATE_CONNECTED:
                    self.command_tag = returned_tag + 1  # Sync with device
            else:
                # Log but don't treat as error in animation/connecting states
                if returned_tag != tag:
                    logger.debug(f"Tag mismatch (allowed in {self.current_state}): expected {tag}, got {returned_tag}")
                    self.command_tag = returned_tag + 1  # Sync with device
            
            if status == 0:
                logger.debug(f"Command successful, status: {status}")
            else:
                logger.warning(f"Command failed with status {status}")
                
            return status, data
        else:
            logger.warning(f"Received CSW with incorrect length: {len(csw)}")
            return None, data

    def test_unit_ready(self):
        """Send TEST UNIT READY command with state-aware retry logic"""
        status, _ = self.send_command(TEST_UNIT_READY_CMD)
        return status == 0

    def inquiry(self):
        """Send INQUIRY command and parse response"""
        status, data = self.send_command(INQUIRY_CMD, expected_data_length=36)
        
        if status == 0 and data is not None:
            vendor = data[8:16].tobytes().decode('ascii', errors='replace').strip()
            product = data[16:32].tobytes().decode('ascii', errors='replace').strip()
            revision = data[32:36].tobytes().decode('ascii', errors='replace').strip()
            
            logger.info(f"Device info - Vendor: {vendor}, Product: {product}, Revision: {revision}")
            return True
        else:
            logger.warning("INQUIRY command failed")
            return False

    def request_sense(self):
        """Send REQUEST SENSE command to get error information"""
        status, data = self.send_command(REQUEST_SENSE_CMD, expected_data_length=18)
        
        if status == 0 and data is not None:
            sense_key = data[2] & 0x0F
            asc = data[12]
            ascq = data[13]
            
            logger.info(f"Sense data - Sense Key: {sense_key}, ASC: {asc}, ASCQ: {ascq}")
            return True, (sense_key, asc, ascq)
        else:
            logger.warning("REQUEST SENSE command failed")
            return False, None

    def initialize_display(self):
        """Send F5 01 command to initialize display"""
        logger.info("Sending Initialize Display command (F5 01)")
        status, _ = self.send_command(F5_INITIALIZE_DISPLAY, cmd_length=6, timeout=5000)
        return status == 0

    def stop_animation(self):
        """Send F5 10 command to stop built-in animation"""
        logger.info("Sending Stop Animation command (F5 10 00)")
        # Animation control needs 1 byte of data (0=stop)
        status, _ = self.send_command(F5_ANIMATION_CONTROL, expected_data_length=0, cmd_length=6)
        # The command is followed by 1 byte of data
        self.write(EP_OUT, b'\x00', timeout=1000)
        return status == 0

    def set_mode(self):
        """Send F5 20 command to set display mode"""
        logger.info("Sending Set Mode command (F5 20)")
        status, _ = self.send_command(F5_SET_MODE, expected_data_length=0, cmd_length=6)
        # Mode 5 is standard operation (4 bytes)
        self.write(EP_OUT, b'\x05\x00\x00\x00', timeout=1000)
        return status == 0

    def get_status(self):
        """Send F5 30 command to get device status"""
        logger.info("Sending Get Status command (F5 30)")
        status, data = self.send_command(F5_GET_STATUS, expected_data_length=8, cmd_length=6)
        
        if status == 0 and data is not None:
            logger.info(f"Status data: {data.tobytes().hex()}")
            return True, data
        else:
            logger.warning("Get Status command failed")
            return False, None

    def clear_screen(self):
        """Send F5 A0 command to clear the screen"""
        logger.info("Sending Clear Screen command (F5 A0)")
        status, _ = self.send_command(F5_CLEAR_SCREEN, cmd_length=6)
        return status == 0

def maintain_connection(device, duration=60):
    """Maintain connection to the device for a specified duration"""
    logger.info(f"Maintaining connection for {duration} seconds...")
    
    start_time = time.time()
    poll_interval = 2  # Poll every 2 seconds
    
    success_count = 0
    failure_count = 0
    
    while time.time() - start_time < duration:
        # Update state
        current_state = device.update_state()
        
        # Always send TEST UNIT READY to keep the connection alive
        status = device.test_unit_ready()
        
        if status:
            success_count += 1
            logger.info(f"TEST UNIT READY succeeded ({success_count} successes, {failure_count} failures)")
            
            # If we're in connected state, try some device-specific commands
            if current_state == STATE_CONNECTED and success_count % 5 == 0:
                logger.info("Trying some device-specific commands in connected state")
                
                # Try to get device status
                device.get_status()
                
            # Delay between commands - shorter in connected state
            if current_state == STATE_CONNECTED:
                time.sleep(1)
            else:
                time.sleep(poll_interval)
        else:
            failure_count += 1
            logger.warning(f"TEST UNIT READY failed ({success_count} successes, {failure_count} failures)")
            
            # Request sense to get error information
            device.request_sense()
            
            # Adjust delay based on failure count
            time.sleep(poll_interval)
        
        # If we've had too many consecutive failures, try to recover
        if failure_count > 10 and success_count == 0:
            logger.warning("Too many failures, attempting recovery...")
            
            # Try to clear any stalled endpoints
            try:
                device.device.clear_halt(EP_IN)
                device.device.clear_halt(EP_OUT)
                logger.info("Cleared halts on endpoints")
            except Exception as e:
                logger.warning(f"Failed to clear halts: {str(e)}")
            
            # Reset success/failure counts
            success_count = 0
            failure_count = 0
    
    logger.info(f"Connection maintenance completed after {duration} seconds")

def perform_device_initialization(device):
    """Perform the complete device initialization sequence"""
    logger.info("Starting device initialization sequence...")
    
    # Step 1: INQUIRY command
    if not device.inquiry():
        logger.warning("INQUIRY failed, continuing anyway...")
    
    # Step 2: TEST UNIT READY
    tur_success = device.test_unit_ready()
    if not tur_success:
        logger.warning("TEST UNIT READY failed, continuing anyway...")
        # If TEST UNIT READY fails, get sense data
        device.request_sense()
    
    # Step 3: Try to initialize the display
    init_success = device.initialize_display()
    if init_success:
        logger.info("Successfully initialized display!")
    else:
        logger.warning("Failed to initialize display, continuing...")
    
    # Step 4: Try to get status
    status_success, _ = device.get_status()
    if status_success:
        logger.info("Successfully retrieved device status")
    else:
        logger.warning("Failed to get device status, continuing...")
    
    # Step 5: Try to set mode
    mode_success = device.set_mode()
    if mode_success:
        logger.info("Successfully set device mode")
    else:
        logger.warning("Failed to set device mode, continuing...")
    
    # Step 6: Try to stop animation
    anim_success = device.stop_animation()
    if anim_success:
        logger.info("Successfully stopped animation")
    else:
        logger.warning("Failed to stop animation, continuing...")
    
    # Step 7: Try to clear screen
    clear_success = device.clear_screen()
    if clear_success:
        logger.info("Successfully cleared screen")
    else:
        logger.warning("Failed to clear screen")
    
    logger.info("Device initialization sequence completed")
    return init_success or status_success or mode_success

def main():
    parser = argparse.ArgumentParser(description='ALi LCD Display Enhanced SCSI Communication Tool')
    parser.add_argument('--duration', type=int, default=300,
                        help='Duration to maintain connection in seconds (default: 300)')
    parser.add_argument('--init-only', action='store_true',
                        help='Only perform initialization sequence, then exit')
    parser.add_argument('--log-file', type=str,
                        help='Log to file in addition to console')
    
    args = parser.parse_args()
    
    # Setup file logging if requested
    if args.log_file:
        file_handler = logging.FileHandler(args.log_file)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
    
    logger.info("ALi LCD Display Enhanced SCSI Communication Tool")
    logger.info(f"Starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Connect to device
    device = ALiLCDDevice(VENDOR_ID, PRODUCT_ID)
    if not device.connect():
        logger.error("Failed to connect to device")
        return 1
    
    try:
        # Perform device initialization
        initialization_success = perform_device_initialization(device)
        
        if args.init_only:
            logger.info("Initialization complete, exiting as requested")
            return 0 if initialization_success else 1
        
        # Maintain connection for the specified duration
        maintain_connection(device, args.duration)
        
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
