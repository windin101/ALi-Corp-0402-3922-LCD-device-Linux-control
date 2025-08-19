#!/usr/bin/env python3
import logging
import sys
import time
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

# Now import should work
from ali_lcd_device.device import ALiLCDDevice

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_basic_commands():
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
            current_state = device._lifecycle_state
            logger.info(f"Current device state: {current_state}")
        except Exception as e:
            logger.error(f"Error waiting for connected state: {e}")
            
        # Now try the F5 commands in direct mode
        logger.info("Testing direct F5 commands")
        
        # Try F5 subcommand 0x01 (Initialize Display)
        logger.info("Testing F5 0x01 (Initialize Display)...")
        try:
            cmd = bytearray(12)  # Create 12-byte command
            cmd[0] = 0xF5
            cmd[1] = 0x01
            device._send_command(cmd)
            logger.info("Initialize display command sent successfully")
            time.sleep(1)  # Give some time for processing
            
            # Try REQUEST SENSE to check for errors
            logger.info("Getting error details with REQUEST SENSE...")
            sense_result = device._send_command(0x03, data_length=18)
            logger.info(f"REQUEST SENSE after F5 01 command: {sense_result.hex()}")
        except Exception as e:
            logger.error(f"F5 0x01 command failed: {e}")
        
        # Try F5 subcommand 0x30 (Get Status)
        logger.info("Testing F5 0x30 (Get Status)...")
        try:
            cmd = bytearray(12)  # Create 12-byte command
            cmd[0] = 0xF5
            cmd[1] = 0x30
            status_result = device._send_command(cmd, data_length=8)
            logger.info(f"Status result: {status_result.hex()}")
        except Exception as e:
            logger.error(f"F5 0x30 command failed: {e}")
            
        # Try F5 subcommand 0x20 (Set Mode) with data 05 00 00 00
        logger.info("Testing F5 0x20 (Set Mode)...")
        try:
            cmd = bytearray(12)  # Create 12-byte command
            cmd[0] = 0xF5
            cmd[1] = 0x20
            mode_data = bytearray([0x05, 0x00, 0x00, 0x00])
            device._send_command(cmd, data_out=mode_data)
            logger.info("Set mode command sent successfully")
            
            # Try REQUEST SENSE to check for errors
            logger.info("Getting error details with REQUEST SENSE...")
            sense_result = device._send_command(0x03, data_length=18)
            logger.info(f"REQUEST SENSE after F5 20 command: {sense_result.hex()}")
        except Exception as e:
            logger.error(f"F5 0x20 command failed: {e}")
        
        # Try F5 subcommand 0x10 (Animation Control) to stop animation
        logger.info("Testing F5 0x10 (Animation Control)...")
        try:
            cmd = bytearray(12)  # Create 12-byte command
            cmd[0] = 0xF5
            cmd[1] = 0x10
            anim_data = bytearray([0x00])  # 0 = stop animation
            device._send_command(cmd, data_out=anim_data)
            logger.info("Animation control command sent successfully")
            
            # Try REQUEST SENSE to check for errors
            logger.info("Getting error details with REQUEST SENSE...")
            sense_result = device._send_command(0x03, data_length=18)
            logger.info(f"REQUEST SENSE after F5 10 command: {sense_result.hex()}")
        except Exception as e:
            logger.error(f"F5 0x10 command failed: {e}")
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        logger.info("Closing device connection")
        device.close()
        logger.info("Test complete")

if __name__ == "__main__":
    test_basic_commands()
