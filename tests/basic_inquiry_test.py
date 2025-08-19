#!/usr/bin/env python3
import logging
import time
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
        
        # Test INQUIRY command
        logger.info("Testing INQUIRY command...")
        try:
            inquiry_result = device._send_command(0x12, data_length=36)
            logger.info(f"INQUIRY result: {inquiry_result.hex()}")
            # Try to decode ASCII parts
            ascii_part = inquiry_result[8:36].decode('ascii', errors='replace')
            logger.info(f"INQUIRY ASCII data: {ascii_part}")
        except Exception as e:
            logger.error(f"INQUIRY command failed: {e}")
        
        # Try REQUEST SENSE command
        logger.info("Testing REQUEST SENSE command...")
        try:
            sense_result = device._send_command(0x03, data_length=18)
            logger.info(f"REQUEST SENSE result: {sense_result.hex()}")
        except Exception as e:
            logger.error(f"REQUEST SENSE command failed: {e}")
        
        # Test if we get to Connected state
        logger.info("Waiting for device to potentially reach Connected state (60 seconds)")
        device._wait_for_connected_state(timeout=60)
        logger.info(f"Current device state: {device._lifecycle.state}")
        
        # If we reached Connected state, try F5 commands
        if device._lifecycle.is_connected():
            logger.info("Device is in Connected state, testing F5 commands")
            
            # Try F5 subcommand 0x30 (Get Status)
            logger.info("Testing F5 0x30 (Get Status)...")
            try:
                status_cmd = bytearray([0xF5, 0x30, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
                status_result = device._send_command(status_cmd, data_length=8)
                logger.info(f"Status result: {status_result.hex()}")
            except Exception as e:
                logger.error(f"F5 0x30 command failed: {e}")
            
            # Try F5 subcommand 0x01 (Initialize Display)
            logger.info("Testing F5 0x01 (Initialize Display)...")
            try:
                init_cmd = bytearray([0xF5, 0x01, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
                device._send_command(init_cmd)
                logger.info("Initialize display command sent successfully")
                time.sleep(1)  # Give some time for processing
            except Exception as e:
                logger.error(f"F5 0x01 command failed: {e}")
                
            # Try another REQUEST SENSE to get error details
            logger.info("Getting error details with REQUEST SENSE...")
            try:
                sense_result = device._send_command(0x03, data_length=18)
                logger.info(f"REQUEST SENSE after F5 command: {sense_result.hex()}")
            except Exception as e:
                logger.error(f"REQUEST SENSE command failed: {e}")
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        logger.info("Closing device connection")
        device.close()
        logger.info("Test complete")

if __name__ == "__main__":
    test_basic_commands()
