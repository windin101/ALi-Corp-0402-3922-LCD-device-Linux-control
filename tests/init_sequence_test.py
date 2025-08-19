#!/usr/bin/env python3
import logging
import sys
import time
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

# Now import should work
from ali_lcd_device.device import ALiLCDDevice
from ali_lcd_device.commands import (
    create_f5_init_command,
    create_f5_get_status_command,
    create_f5_set_mode_command,
    create_request_sense
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_init_sequence():
    device = ALiLCDDevice()
    
    try:
        logger.info("Connecting to ALi LCD device")
        device.connect()
        logger.info("Connected successfully")
        
        # Wait for device to reach Connected state
        logger.info("Waiting for device to reach Connected state (60 seconds)...")
        device._wait_for_connected_state(timeout=60)
        logger.info(f"Current device state: {device.lifecycle_state}")
        
        # Wait an additional 2 seconds after reaching Connected state
        logger.info("Waiting 2 additional seconds after reaching Connected state...")
        time.sleep(2)
        
        # Follow the Initialization Sequence from the documentation:
        # 1. TEST UNIT READY
        logger.info("1. Testing if device is ready using TEST UNIT READY command")
        success, _ = device._test_unit_ready()
        logger.info(f"TEST UNIT READY result: {'Success' if success else 'Failed'}")
        
        # 2. INQUIRY
        logger.info("2. Sending INQUIRY command")
        success, _, inquiry_data = device._inquiry()
        if success and inquiry_data:
            logger.info(f"INQUIRY result: {inquiry_data.hex()}")
            try:
                # Try to decode the inquiry data (typically contains ASCII information)
                inquiry_text = inquiry_data[8:36].decode('ascii', errors='replace').strip()
                logger.info(f"INQUIRY text: {inquiry_text}")
            except Exception as e:
                logger.error(f"Error decoding inquiry data: {e}")
        else:
            logger.error(f"INQUIRY command failed: success={success}")
        
        # 3. F5 0x01 (Initialize Display)
        logger.info("3. Sending F5 0x01 (Initialize Display)...")
        cmd, data_length, direction = create_f5_init_command()
        success, tag_mismatch, data = device._send_command(cmd, data_length, direction)
        logger.info(f"Initialize display command result: {'Success' if success else 'Failed'}")
        
        if not success:
            # Try REQUEST SENSE to check for errors
            logger.info("Getting error details with REQUEST SENSE...")
            cmd, data_length, direction = create_request_sense()
            _, _, sense_data = device._send_command(cmd, data_length, direction)
            if sense_data:
                logger.info(f"REQUEST SENSE after F5 01 command: {sense_data.hex()}")
                # Parse sense data
                sense_key = sense_data[2] & 0x0F
                asc = sense_data[12]
                ascq = sense_data[13]
                logger.info(f"Sense Key: {sense_key}, ASC: {asc}, ASCQ: {ascq}")
        
        # 4. F5 0x30 (Get Status)
        logger.info("4. Sending F5 0x30 (Get Status)...")
        cmd, data_length, direction = create_f5_get_status_command()
        success, tag_mismatch, status_data = device._send_command(cmd, data_length, direction)
        
        if success and status_data:
            logger.info(f"Status result: {status_data.hex()}")
        else:
            logger.error(f"Get Status command failed: success={success}")
            
            # Try REQUEST SENSE to check for errors
            logger.info("Getting error details with REQUEST SENSE...")
            cmd, data_length, direction = create_request_sense()
            _, _, sense_data = device._send_command(cmd, data_length, direction)
            if sense_data:
                logger.info(f"REQUEST SENSE after F5 30 command: {sense_data.hex()}")
                # Parse sense data
                sense_key = sense_data[2] & 0x0F
                asc = sense_data[12]
                ascq = sense_data[13]
                logger.info(f"Sense Key: {sense_key}, ASC: {asc}, ASCQ: {ascq}")
        
        # 5. F5 0x20 (Set Mode) with data 05 00 00 00
        logger.info("5. Sending F5 0x20 (Set Mode)...")
        cmd, data_length, direction, mode_data = create_f5_set_mode_command(mode=5)
        success, tag_mismatch, _ = device._send_command(cmd, data_length, direction, mode_data)
        logger.info(f"Set mode command result: {'Success' if success else 'Failed'}")
        
        if not success:
            # Try REQUEST SENSE to check for errors
            logger.info("Getting error details with REQUEST SENSE...")
            cmd, data_length, direction = create_request_sense()
            _, _, sense_data = device._send_command(cmd, data_length, direction)
            if sense_data:
                logger.info(f"REQUEST SENSE after F5 20 command: {sense_data.hex()}")
                # Parse sense data
                sense_key = sense_data[2] & 0x0F
                asc = sense_data[12]
                ascq = sense_data[13]
                logger.info(f"Sense Key: {sense_key}, ASC: {asc}, ASCQ: {ascq}")
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        logger.info("Closing device connection")
        device.close()
        logger.info("Test complete")

if __name__ == "__main__":
    test_init_sequence()
