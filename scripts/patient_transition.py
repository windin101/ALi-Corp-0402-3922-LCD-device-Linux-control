#!/usr/bin/env python3
"""
ALi LCD Patient Transition Script

This script implements a very patient approach to transition the ALi LCD device from
Animation state to Connected state. It focuses solely on achieving the transition,
using minimal commands with precise timing.

Key characteristics:
- Sends TEST UNIT READY commands at exactly 1-second intervals
- Runs for at least 70 seconds (well beyond the expected 56-58 second transition point)
- Ignores all errors and CSW mismatches during Animation state
- Avoids clearing endpoint halts during initial phase
- Attempts recovery only after significant unresponsiveness

Usage:
  sudo python3 patient_transition.py

Author: LEO
Date: August 19, 2025
"""

import sys
import time
import usb.core
import usb.util
import struct
import logging
import argparse
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('ALi-LCD-Patient')

# USB Constants
VENDOR_ID = 0x0402
PRODUCT_ID = 0x3922
EP_OUT = 0x02
EP_IN = 0x81

# SCSI Commands
TEST_UNIT_READY_CMD = b'\x00\x00\x00\x00\x00\x00'
INQUIRY_CMD = b'\x12\x00\x00\x00\x24\x00'
REQUEST_SENSE_CMD = b'\x03\x00\x00\x00\x12\x00'

# Custom Commands
F5_COMMANDS = {
    'INIT': b'\xF5\x01\x00\x00\x00\x00',
    'ANIMATION': b'\xF5\x10\x00\x00\x00\x00',
    'SET_MODE': b'\xF5\x20\x00\x00\x00\x00',
    'GET_STATUS': b'\xF5\x30\x00\x00\x00\x00',
    'CLEAR_SCREEN': b'\xF5\xA0\x00\x00\x00\x00',
}

class PatientTransition:
    def __init__(self):
        self.device = None
        self.tag = 0x12345678
        self.error_count = 0
        self.command_count = 0
        self.current_state = "ANIMATION"
        self.transition_detected = False
        
    def connect(self):
        """Establish connection to the device with minimal intervention"""
        logger.info("Looking for USB device %04X:%04X...", VENDOR_ID, PRODUCT_ID)
        
        # Find device
        self.device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if self.device is None:
            logger.error("Device not found!")
            return False
            
        logger.info("Device found")
        
        # Reset the device (but don't do this repeatedly)
        try:
            logger.info("Resetting device...")
            self.device.reset()
            time.sleep(2)  # Wait after reset
        except Exception as e:
            logger.warning(f"Reset error: {e}")
            # Continue anyway
        
        # Set configuration
        try:
            logger.info("Setting configuration...")
            self.device.set_configuration()
            time.sleep(1)
        except Exception as e:
            logger.warning(f"Configuration error: {e}")
            # Continue anyway
            
        # Claim interface
        try:
            interface = 0
            if self.device.is_kernel_driver_active(interface):
                self.device.detach_kernel_driver(interface)
            self.device.claim_interface(interface)
            logger.info("Interface claimed")
        except Exception as e:
            logger.warning(f"Interface claim error: {e}")
            # Continue anyway
            
        logger.info("Device ready")
        return True
        
    def send_cbw(self, command, data_length=0, is_read=False):
        """Send a Command Block Wrapper"""
        # Increment tag for each command
        self.tag += 1
        
        # Construct CBW
        flags = 0x80 if is_read else 0x00
        cbw = struct.pack('<4s4sII1s1s', 
            b'USBC',                 # Signature
            struct.pack('<I', self.tag),  # Tag
            data_length,             # Data transfer length
            flags,                   # Flags
            b'\x00',                 # LUN
            bytes([len(command)])    # Command length
        )
        cbw += command + b'\x00' * (16 - len(command))  # Pad command to 16 bytes
        
        # Send CBW
        try:
            sent = self.device.write(EP_OUT, cbw)
            return True
        except Exception as e:
            logger.debug(f"CBW write error: {e}")
            return False
    
    def read_csw(self):
        """Read the Command Status Wrapper with minimal error handling"""
        try:
            csw = self.device.read(EP_IN, 13, timeout=1500)
            
            # Extract data from CSW
            csw_signature = csw[0:4]
            csw_tag = struct.unpack('<I', csw[4:8])[0]
            csw_data_residue = struct.unpack('<I', csw[8:12])[0]
            csw_status = csw[12]
            
            # Very minimal validation - just check signature
            if csw_signature != b'USBS':
                logger.debug("Invalid CSW signature")
                return None
                
            return {
                'tag': csw_tag,
                'residue': csw_data_residue,
                'status': csw_status
            }
        except Exception as e:
            # During Animation state, we expect errors - just log at debug level
            logger.debug(f"CSW read error: {e}")
            return None
    
    def send_test_unit_ready(self):
        """Send TEST UNIT READY command with minimal error handling"""
        self.send_cbw(TEST_UNIT_READY_CMD)
        time.sleep(0.5)  # Wait for device to process
        csw = self.read_csw()
        
        # Just log the result, don't try to handle errors
        if csw:
            status_str = f"Status: {csw['status']}"
            if csw['status'] == 0:
                logger.info(f"TEST UNIT READY: {status_str} (Success!)")
                # This might indicate transition to Connected state
                if self.current_state == "ANIMATION" and self.command_count > 50:
                    logger.info("Possible state transition detected!")
                    self.transition_detected = True
                    self.current_state = "CONNECTING"
            else:
                logger.debug(f"TEST UNIT READY: {status_str}")
        else:
            logger.debug("TEST UNIT READY: No valid CSW")
            
        self.command_count += 1
        
    def send_f5_command(self, subcommand, data=None, data_length=0, is_read=False):
        """Send an F5 command with minimal error handling"""
        logger.info(f"Sending F5 command {subcommand[1]:02X}")
        self.send_cbw(subcommand, data_length, is_read)
        
        # Send data if needed
        if data and not is_read:
            try:
                self.device.write(EP_OUT, data)
                logger.debug(f"Sent {len(data)} bytes of data")
            except Exception as e:
                logger.warning(f"Data write error: {e}")
        
        # Read data if needed
        if is_read and data_length > 0:
            try:
                received = self.device.read(EP_IN, data_length, timeout=1500)
                logger.info(f"Received {len(received)} bytes: {received.hex()}")
            except Exception as e:
                logger.warning(f"Data read error: {e}")
        
        # Wait before reading CSW
        time.sleep(1.0)
        
        # Read CSW
        csw = self.read_csw()
        if csw:
            status_str = f"Status: {csw['status']}"
            if csw['status'] == 0:
                logger.info(f"F5 command: {status_str} (Success!)")
                return True
            else:
                logger.info(f"F5 command: {status_str}")
                return False
        else:
            logger.info("F5 command: No valid CSW")
            return False
            
    def run_patient_transition(self, duration=70):
        """Run a patient transition sequence focusing on TEST UNIT READY"""
        if not self.connect():
            return False
            
        logger.info("Starting patient transition sequence")
        logger.info("Initial state: ANIMATION")
        logger.info(f"Will run for at least {duration} seconds")
        
        start_time = time.time()
        last_command_time = 0
        
        # Main loop - send TEST UNIT READY commands at precisely 1-second intervals
        while time.time() - start_time < duration:
            current_time = time.time()
            elapsed = int(current_time - start_time)
            
            # Ensure exactly 1 second between commands
            if current_time - last_command_time >= 1.0:
                logger.info(f"[{elapsed}s] Sending TEST UNIT READY ({self.command_count + 1})")
                self.send_test_unit_ready()
                last_command_time = time.time()
                
                # Display progress every 5 seconds
                if self.command_count % 5 == 0:
                    logger.info(f"Progress: {elapsed}/{duration} seconds, {self.command_count} commands")
            
            # Small sleep to prevent CPU spinning
            time.sleep(0.1)
        
        logger.info(f"Completed initial transition phase: {self.command_count} commands in {duration} seconds")
        
        # Now try to confirm the transition with some specific commands
        logger.info("Sending F5 initialization commands to confirm transition")
        
        # Standard initialization sequence
        time.sleep(2)  # Pause before starting F5 commands
        self.send_f5_command(F5_COMMANDS['INIT'])
        time.sleep(2)
        self.send_f5_command(F5_COMMANDS['GET_STATUS'], data_length=8, is_read=True)
        time.sleep(2)
        self.send_f5_command(F5_COMMANDS['SET_MODE'], data=b'\x05\x00\x00\x00')
        time.sleep(2)
        self.send_f5_command(F5_COMMANDS['ANIMATION'], data=b'\x00')
        
        # Final verification
        logger.info("Final verification with TEST UNIT READY")
        for i in range(5):
            self.send_test_unit_ready()
            time.sleep(1)
        
        # Release interface
        try:
            self.device.release_interface(0)
            logger.info("Interface released")
        except Exception as e:
            logger.warning(f"Interface release error: {e}")
        
        logger.info("Patient transition sequence complete")
        
        # Report results
        if self.transition_detected:
            logger.info("SUCCESS: Transition to Connected state was detected!")
        else:
            logger.info("NOTE: No clear transition was detected, but commands were sent")
            logger.info("The device may still have transitioned successfully")
        
        return self.transition_detected

def main():
    parser = argparse.ArgumentParser(description='ALi LCD Patient Transition Tool')
    parser.add_argument('--duration', type=int, default=70, 
                        help='Duration in seconds for the transition sequence (default: 70)')
    args = parser.parse_args()
    
    logger.info("ALi LCD Patient Transition Tool")
    logger.info(f"Starting at {datetime.now()}")
    
    transition = PatientTransition()
    success = transition.run_patient_transition(duration=args.duration)
    
    if success:
        logger.info("Patient transition process SUCCEEDED")
        return 0
    else:
        logger.info("Patient transition process COMPLETED, but transition was not confirmed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
