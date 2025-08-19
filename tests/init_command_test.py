#!/usr/bin/env python3
import logging
import sys
import time
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

# Now import should work
from ali_lcd_device.device import ALiLCDDevice
from ali_lcd_device.commands import create_f5_init_command, create_request_sense

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_init_command():
    device = ALiLCDDevice()
    
    try:
        logger.info("Connecting to ALi LCD device")
        device.connect()
        logger.info("Connected successfully")
        
        # Wait for device to reach Connected state
        logger.info("Waiting for device to reach Connected state (60 seconds)...")
        device._wait_for_connected_state(timeout=60)
        logger.info(f"Current device state: {device.lifecycle_state}")
        
        # Test if device is ready using TEST UNIT READY
        logger.info("Testing if device is ready using TEST UNIT READY command")
        success, _ = device._test_unit_ready()
        logger.info(f"TEST UNIT READY result: {'Success' if success else 'Failed'}")
        
        # Try F5 subcommand 0x01 (Initialize Display)
        logger.info("Testing F5 0x01 (Initialize Display)...")
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
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        logger.info("Closing device connection")
        device.close()
        logger.info("Test complete")

if __name__ == "__main__":
    test_init_command()
