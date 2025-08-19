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
    create_f5_animation_command,
    create_f5_set_mode_command,
    create_f5_get_status_command,
    create_request_sense
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_f5_commands():
    device = ALiLCDDevice()
    
    try:
        logger.info("Connecting to ALi LCD device")
        device.connect()
        logger.info("Connected successfully")
        
        # Wait a moment
        time.sleep(1)
        
        # Try to get into CONNECTED state
        logger.info("Waiting for device to potentially reach Connected state (60 seconds)")
        try:
            device._wait_for_connected_state(timeout=60)
            current_state = device.lifecycle_state  # Using public property
            logger.info(f"Current device state: {current_state}")
        except Exception as e:
            logger.error(f"Error waiting for connected state: {e}")
        
        # Test if device is in Connected state 
        logger.info("Testing if device is ready using TEST UNIT READY command")
        success, _ = device._test_unit_ready()
        logger.info(f"TEST UNIT READY result: {'Success' if success else 'Failed'}")
        
        # Now try the F5 commands in sequence
        logger.info("Testing F5 commands in sequence")
        
        # Try F5 subcommand 0x01 (Initialize Display)
        logger.info("Testing F5 0x01 (Initialize Display)...")
        try:
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
            logger.error(f"F5 0x01 command failed: {e}")
        
        # Try F5 subcommand 0x30 (Get Status)
        logger.info("Testing F5 0x30 (Get Status)...")
        try:
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
        except Exception as e:
            logger.error(f"F5 0x30 command failed: {e}")
            
        # Try F5 subcommand 0x20 (Set Mode) with data 05 00 00 00
        logger.info("Testing F5 0x20 (Set Mode)...")
        try:
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
            logger.error(f"F5 0x20 command failed: {e}")
        
        # Try F5 subcommand 0x10 (Animation Control) to stop animation
        logger.info("Testing F5 0x10 (Animation Control)...")
        try:
            cmd, data_length, direction, anim_data = create_f5_animation_command(start_animation=False)
            success, tag_mismatch, _ = device._send_command(cmd, data_length, direction, anim_data)
            logger.info(f"Animation control command result: {'Success' if success else 'Failed'}")
            
            if not success:
                # Try REQUEST SENSE to check for errors
                logger.info("Getting error details with REQUEST SENSE...")
                cmd, data_length, direction = create_request_sense()
                _, _, sense_data = device._send_command(cmd, data_length, direction)
                if sense_data:
                    logger.info(f"REQUEST SENSE after F5 10 command: {sense_data.hex()}")
                    # Parse sense data
                    sense_key = sense_data[2] & 0x0F
                    asc = sense_data[12]
                    ascq = sense_data[13]
                    logger.info(f"Sense Key: {sense_key}, ASC: {asc}, ASCQ: {ascq}")
        except Exception as e:
            logger.error(f"F5 0x10 command failed: {e}")
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        logger.info("Closing device connection")
        device.close()
        logger.info("Test complete")

if __name__ == "__main__":
    test_f5_commands()
