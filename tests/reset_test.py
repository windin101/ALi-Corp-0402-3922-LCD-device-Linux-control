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
    create_f5_reset_command,
    create_f5_init_command,
    create_f5_get_status_command,
    create_f5_set_mode_command,
    create_f5_clear_screen_command,
    create_request_sense
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_with_retries():
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
        
        # Try a device reset first to ensure a clean state
        logger.info("Resetting device with F5 0x00 command...")
        cmd, data_length, direction = create_f5_reset_command()
        success, _, _ = device._send_command(cmd, data_length, direction)
        logger.info(f"Device reset result: {'Success' if success else 'Failed'}")
        
        # Wait after reset
        time.sleep(1)
        
        # Try TEST UNIT READY
        for i in range(3):
            logger.info(f"Attempt {i+1}/3: Testing if device is ready using TEST UNIT READY command")
            success, _ = device._test_unit_ready()
            logger.info(f"TEST UNIT READY result: {'Success' if success else 'Failed'}")
            if success:
                break
            time.sleep(0.5)
        
        # Try INQUIRY
        logger.info("Sending INQUIRY command...")
        try:
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
        except Exception as e:
            logger.error(f"Error executing INQUIRY command: {e}")
        
        # Try F5 0x01 (Initialize Display) with retries
        for i in range(3):
            logger.info(f"Attempt {i+1}/3: Sending F5 0x01 (Initialize Display)...")
            try:
                cmd, data_length, direction = create_f5_init_command()
                success, _, _ = device._send_command(cmd, data_length, direction)
                logger.info(f"Initialize display command result: {'Success' if success else 'Failed'}")
                
                if success:
                    break
                    
                # Try REQUEST SENSE to check for errors
                logger.info("Getting error details with REQUEST SENSE...")
                cmd, data_length, direction = create_request_sense()
                try:
                    _, _, sense_data = device._send_command(cmd, data_length, direction)
                    if sense_data:
                        logger.info(f"REQUEST SENSE after F5 01 command: {sense_data.hex()}")
                        # Parse sense data
                        sense_key = sense_data[2] & 0x0F
                        asc = sense_data[12]
                        ascq = sense_data[13]
                        logger.info(f"Sense Key: {sense_key}, ASC: {asc}, ASCQ: {ascq}")
                except Exception as e:
                    logger.error(f"Error getting REQUEST SENSE data: {e}")
                    
                time.sleep(1)  # Wait before retry
            except Exception as e:
                logger.error(f"Error sending F5 0x01 command: {e}")
                time.sleep(1)  # Wait before retry
        
        # Try F5 0xA0 (Clear Screen)
        logger.info("Sending F5 0xA0 (Clear Screen)...")
        try:
            cmd, data_length, direction = create_f5_clear_screen_command()
            success, _, _ = device._send_command(cmd, data_length, direction)
            logger.info(f"Clear screen command result: {'Success' if success else 'Failed'}")
        except Exception as e:
            logger.error(f"Error sending Clear Screen command: {e}")
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        logger.info("Closing device connection")
        device.close()
        logger.info("Test complete")

if __name__ == "__main__":
    test_with_retries()
