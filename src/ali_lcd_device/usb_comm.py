#!/usr/bin/env python3
"""
USB communication module for ALi LCD device.
"""

import usb.core
import usb.util
import time
import logging
import struct
import threading

logger = logging.getLogger(__name__)

# USB constants for BOT protocol
CBW_SIGNATURE = 0x43425355  # 'USBC' in little-endian
CSW_SIGNATURE = 0x53425355  # 'USBS' in little-endian

# USB Mass Storage directions
MS_DIRECTION_OUT = 0x00
MS_DIRECTION_IN = 0x80

# Default USB timeouts
DEFAULT_TIMEOUT = 5000  # 5 seconds

class USBError(Exception):
    """Base exception for USB communication errors."""
    pass

class TagMismatchError(USBError):
    """Exception for tag mismatch errors."""
    pass

class PipeError(USBError):
    """Exception for pipe errors."""
    pass

class DeviceNotFoundError(USBError):
    """Exception for device not found errors."""
    pass

class ResourceBusyError(USBError):
    """Exception for resource busy errors."""
    pass

class RobustUSBSession:
    """
    Provides robust USB communication with error handling and recovery.
    
    This class handles common USB errors and implements retry logic with
    exponential backoff.
    """
    
    def __init__(self, max_retries=3, retry_delay=0.2):
        """
        Initialize the robust USB session.
        
        Args:
            max_retries (int): Maximum number of retry attempts
            retry_delay (float): Initial delay between retries (seconds)
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.lock = threading.Lock()
    
    def with_retry(self, func, *args, **kwargs):
        """
        Execute a function with retry logic.
        
        Args:
            func: The function to execute
            *args: Arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            The return value of the function
            
        Raises:
            USBError: If the function fails after all retries
        """
        retry_count = 0
        delay = self.retry_delay
        
        while True:
            try:
                with self.lock:
                    return func(*args, **kwargs)
            except usb.core.USBError as e:
                retry_count += 1
                
                # If we've hit the maximum retries, re-raise the exception
                if retry_count > self.max_retries:
                    raise USBError(f"Failed after {self.max_retries} retries: {str(e)}") from e
                
                # Log the error and retry
                logger.warning("USB error (attempt %d/%d): %s", 
                             retry_count, self.max_retries, str(e))
                
                # Handle specific error types
                if "pipe" in str(e).lower():
                    self._handle_pipe_error(*args)
                elif "busy" in str(e).lower():
                    self._handle_busy_error(*args)
                
                # Wait before retrying
                time.sleep(delay)
                delay *= 2  # Exponential backoff
    
    def _handle_pipe_error(self, device, endpoint=None):
        """
        Handle pipe errors by clearing endpoint halts.
        
        Args:
            device: The USB device
            endpoint: The endpoint that caused the error
        """
        try:
            if endpoint is not None:
                logger.debug("Clearing halt on endpoint 0x%02x", endpoint.bEndpointAddress)
                device.clear_halt(endpoint.bEndpointAddress)
            else:
                # If no specific endpoint, try to clear both in and out endpoints
                for ep in device.get_active_configuration()[(0,0)]:
                    if usb.util.endpoint_direction(ep.bEndpointAddress) in \
                            [usb.util.ENDPOINT_IN, usb.util.ENDPOINT_OUT]:
                        logger.debug("Clearing halt on endpoint 0x%02x", ep.bEndpointAddress)
                        device.clear_halt(ep.bEndpointAddress)
        except usb.core.USBError as e:
            logger.error("Failed to clear halt: %s", str(e))
    
    def _handle_busy_error(self, device):
        """
        Handle resource busy errors.
        
        Args:
            device: The USB device
        """
        # Nothing specific to do here, the retry with delay should handle it
        logger.debug("Resource busy, waiting before retry")


def create_cbw(tag, data_length, direction, lun, command):
    """
    Create a Command Block Wrapper (CBW) for SCSI commands.
    
    Args:
        tag (int): Command tag
        data_length (int): Expected data transfer length
        direction (str): Data direction ('in', 'out', or 'none')
        lun (int): Logical Unit Number
        command (bytes): SCSI command bytes
        
    Returns:
        bytes: The CBW bytes
    """
    # Convert direction string to flag
    if direction.lower() == 'in':
        direction_flag = MS_DIRECTION_IN
    else:
        direction_flag = MS_DIRECTION_OUT
    
    # Get command length
    cmd_len = len(command)
    
    # Create CBW structure
    cbw = struct.pack('<IIIBBBB',
                      CBW_SIGNATURE,  # dCBWSignature
                      tag,            # dCBWTag
                      data_length,    # dCBWDataTransferLength
                      direction_flag, # bmCBWFlags
                      lun,            # bCBWLUN
                      cmd_len,        # bCBWCBLength
                      0)              # reserved
    
    # Add command bytes
    cbw += command
    
    # Pad to 31 bytes
    cbw += b'\x00' * (31 - len(cbw))
    
    return cbw


def parse_csw(data):
    """
    Parse a Command Status Wrapper (CSW).
    
    Args:
        data (bytes): The CSW data
        
    Returns:
        tuple: (signature, tag, data_residue, status)
        
    Raises:
        ValueError: If the CSW is invalid
    """
    if len(data) != 13:
        raise ValueError(f"Invalid CSW length: {len(data)}")
    
    signature, tag, data_residue, status = struct.unpack('<IIIB', data)
    
    if signature != CSW_SIGNATURE:
        raise ValueError(f"Invalid CSW signature: 0x{signature:08x}")
    
    return signature, tag, data_residue, status
