#!/usr/bin/env python3
"""
SCSI command definitions for ALi LCD device.
"""

def create_test_unit_ready(tag=0):
    """
    Create a TEST UNIT READY command.
    
    Args:
        tag (int): The command tag
        
    Returns:
        tuple: (command, data_length, direction)
    """
    cmd = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    return cmd, 0, 'none'


def create_inquiry(allocation_length=36, tag=0):
    """
    Create an INQUIRY command.
    
    Args:
        allocation_length (int): Amount of data to request
        tag (int): The command tag
        
    Returns:
        tuple: (command, data_length, direction)
    """
    cmd = bytes([0x12, 0x00, 0x00, 0x00, allocation_length, 0x00])
    return cmd, allocation_length, 'in'


def create_request_sense(allocation_length=18, tag=0):
    """
    Create a REQUEST SENSE command.
    
    Args:
        allocation_length (int): Amount of data to request
        tag (int): The command tag
        
    Returns:
        tuple: (command, data_length, direction)
    """
    cmd = bytes([0x03, 0x00, 0x00, 0x00, allocation_length, 0x00])
    return cmd, allocation_length, 'in'


def create_f5_command(subcommand, data_length=0, tag=0):
    """
    Create a custom F5 command with the specified subcommand.
    
    Args:
        subcommand (int): The subcommand (0x00, 0x01, 0x10, etc.)
        data_length (int): Length of data to transfer (if any)
        tag (int): The command tag
        
    Returns:
        tuple: (command, data_length, direction)
    """
    # Determine data direction
    direction = 'none'
    if data_length > 0:
        if subcommand in [0x30]:  # Commands that return data
            direction = 'in'
        else:  # Commands that accept data
            direction = 'out'
    
    # Create the command bytes
    cmd = bytearray([0xF5, subcommand])
    cmd.extend([0x00] * 10)  # Pad to 12 bytes
    
    return bytes(cmd), data_length, direction


def create_f5_reset_command(tag=0):
    """
    Create a F5 reset command (subcommand 0x00).
    
    Args:
        tag (int): The command tag
        
    Returns:
        tuple: (command, data_length, direction)
    """
    return create_f5_command(0x00, 0, tag)


def create_f5_init_command(tag=0):
    """
    Create a F5 initialize display command (subcommand 0x01).
    
    Args:
        tag (int): The command tag
        
    Returns:
        tuple: (command, data_length, direction)
    """
    return create_f5_command(0x01, 0, tag)


def create_f5_animation_command(start_animation, tag=0):
    """
    Create a F5 animation control command (subcommand 0x10).
    
    Args:
        start_animation (bool): True to start animation, False to stop
        tag (int): The command tag
        
    Returns:
        tuple: (command, data_length, direction, data)
    """
    cmd, data_length, direction = create_f5_command(0x10, 1, tag)
    data = bytes([0x01 if start_animation else 0x00])
    return cmd, data_length, direction, data


def create_f5_set_mode_command(mode=5, tag=0):
    """
    Create a F5 set mode command (subcommand 0x20).
    
    Args:
        mode (int): The mode value (typically 5)
        tag (int): The command tag
        
    Returns:
        tuple: (command, data_length, direction, data)
    """
    cmd, data_length, direction = create_f5_command(0x20, 4, tag)
    data = bytes([mode, 0x00, 0x00, 0x00])
    return cmd, data_length, direction, data


def create_f5_get_status_command(tag=0):
    """
    Create a F5 get status command (subcommand 0x30).
    
    Args:
        tag (int): The command tag
        
    Returns:
        tuple: (command, data_length, direction)
    """
    return create_f5_command(0x30, 8, tag)


def create_f5_clear_screen_command(tag=0):
    """
    Create a F5 clear screen command (subcommand 0xA0).
    
    Args:
        tag (int): The command tag
        
    Returns:
        tuple: (command, data_length, direction)
    """
    return create_f5_command(0xA0, 0, tag)


def create_f5_display_image_command(width, height, x=0, y=0, tag=0):
    """
    Create a F5 display image command (subcommand 0xB0).
    
    Args:
        width (int): Image width in pixels
        height (int): Image height in pixels
        x (int): X start position
        y (int): Y start position
        tag (int): The command tag
        
    Returns:
        tuple: (command, data_length, direction)
    """
    # Each pixel is 2 bytes in RGB565 format
    image_size = width * height * 2
    # Add 10 bytes for the header
    total_size = image_size + 10
    
    return create_f5_command(0xB0, total_size, tag)


def create_image_header(width, height, x=0, y=0):
    """
    Create the header for image data.
    
    Args:
        width (int): Image width in pixels
        height (int): Image height in pixels
        x (int): X start position
        y (int): Y start position
        
    Returns:
        bytes: The image header
    """
    return bytes([
        0x01,                    # Format (RGB565)
        0x00,                    # Reserved
        (x >> 8) & 0xFF,         # X start high byte
        x & 0xFF,                # X start low byte
        (y >> 8) & 0xFF,         # Y start high byte
        y & 0xFF,                # Y start low byte
        (width >> 8) & 0xFF,     # Width high byte
        width & 0xFF,            # Width low byte
        (height >> 8) & 0xFF,    # Height high byte
        height & 0xFF            # Height low byte
    ])
