#!/usr/bin/env python3
"""
Image processing utilities for ALi LCD device.
"""

import logging
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

def rgb888_to_rgb565(r, g, b):
    """
    Convert RGB888 (24-bit) to RGB565 (16-bit).
    
    Args:
        r (int): Red component (0-255)
        g (int): Green component (0-255)
        b (int): Blue component (0-255)
        
    Returns:
        bytes: Two bytes in RGB565 format (high byte first)
    """
    r = (r >> 3) & 0x1F  # 5 bits for red
    g = (g >> 2) & 0x3F  # 6 bits for green
    b = (b >> 3) & 0x1F  # 5 bits for blue
    
    # Combine components into RGB565 (high byte first)
    high_byte = ((r << 3) | (g >> 3)) & 0xFF
    low_byte = ((g << 5) | b) & 0xFF
    
    return bytes([high_byte, low_byte])


def convert_image_to_rgb565(image_path, resize=None):
    """
    Convert an image file to RGB565 format.
    
    Args:
        image_path (str): Path to the image file
        resize (tuple, optional): (width, height) to resize the image
        
    Returns:
        tuple: (rgb565_data, width, height)
    """
    # Open and convert image to RGB
    image = Image.open(image_path).convert('RGB')
    
    # Resize if requested
    if resize:
        image = image.resize(resize, Image.LANCZOS)
        
    width, height = image.size
    
    # Get image data as numpy array
    img_array = np.array(image)
    
    # Extract RGB components
    r = img_array[:, :, 0]
    g = img_array[:, :, 1]
    b = img_array[:, :, 2]
    
    # Convert to RGB565
    r = (r >> 3) & 0x1F
    g = (g >> 2) & 0x3F
    b = (b >> 3) & 0x1F
    
    # Create RGB565 data array
    rgb565_data = np.zeros((height, width, 2), dtype=np.uint8)
    rgb565_data[:, :, 0] = ((r << 3) | (g >> 3)) & 0xFF
    rgb565_data[:, :, 1] = ((g << 5) | b) & 0xFF
    
    # Convert to bytes (row-major order)
    return rgb565_data.tobytes(), width, height


def create_gradient_pattern(width, height):
    """
    Create a gradient test pattern in RGB565 format.
    
    Args:
        width (int): Image width
        height (int): Image height
        
    Returns:
        bytes: RGB565 image data
    """
    # Create arrays for RGB components
    r = np.zeros((height, width), dtype=np.uint8)
    g = np.zeros((height, width), dtype=np.uint8)
    b = np.zeros((height, width), dtype=np.uint8)
    
    # Fill with gradient pattern
    for y in range(height):
        for x in range(width):
            r[y, x] = int(255 * x / width)
            g[y, x] = int(255 * y / height)
            b[y, x] = 128  # Constant blue component
    
    # Convert to RGB565
    r = (r >> 3) & 0x1F
    g = (g >> 2) & 0x3F
    b = (b >> 3) & 0x1F
    
    # Create RGB565 data
    rgb565_data = np.zeros((height, width, 2), dtype=np.uint8)
    rgb565_data[:, :, 0] = ((r << 3) | (g >> 3)) & 0xFF
    rgb565_data[:, :, 1] = ((g << 5) | b) & 0xFF
    
    return rgb565_data.tobytes()


def create_checkerboard_pattern(width, height, square_size=20):
    """
    Create a checkerboard test pattern in RGB565 format.
    
    Args:
        width (int): Image width
        height (int): Image height
        square_size (int): Size of checkerboard squares
        
    Returns:
        bytes: RGB565 image data
    """
    # Create a blank image array
    rgb565_data = np.zeros((height, width, 2), dtype=np.uint8)
    
    # Define colors (white and black in RGB565)
    white = np.array([0xFF, 0xFF], dtype=np.uint8)  # Full intensity
    black = np.array([0x00, 0x00], dtype=np.uint8)  # Zero intensity
    
    # Fill the checkerboard pattern
    for y in range(0, height, square_size):
        for x in range(0, width, square_size):
            color = white if ((x // square_size) + (y // square_size)) % 2 == 0 else black
            
            # Calculate effective square size (handle edge cases)
            x_size = min(square_size, width - x)
            y_size = min(square_size, height - y)
            
            # Fill the square
            rgb565_data[y:y+y_size, x:x+x_size] = color
    
    return rgb565_data.tobytes()


def create_color_bars(width, height):
    """
    Create color bars test pattern in RGB565 format.
    
    Args:
        width (int): Image width
        height (int): Image height
        
    Returns:
        bytes: RGB565 image data
    """
    # Create a blank image array
    rgb565_data = np.zeros((height, width, 2), dtype=np.uint8)
    
    # Define colors in RGB888
    colors = [
        (255, 0, 0),     # Red
        (0, 255, 0),     # Green
        (0, 0, 255),     # Blue
        (255, 255, 0),   # Yellow
        (255, 0, 255),   # Magenta
        (0, 255, 255),   # Cyan
        (255, 255, 255), # White
        (0, 0, 0)        # Black
    ]
    
    # Convert colors to RGB565
    rgb565_colors = []
    for r, g, b in colors:
        r = (r >> 3) & 0x1F
        g = (g >> 2) & 0x3F
        b = (b >> 3) & 0x1F
        
        high_byte = ((r << 3) | (g >> 3)) & 0xFF
        low_byte = ((g << 5) | b) & 0xFF
        
        rgb565_colors.append(np.array([high_byte, low_byte], dtype=np.uint8))
    
    # Fill the color bars
    bar_width = width // len(colors)
    
    for i, color in enumerate(rgb565_colors):
        x_start = i * bar_width
        x_end = (i + 1) * bar_width if i < len(colors) - 1 else width
        
        rgb565_data[:, x_start:x_end] = color
    
    return rgb565_data.tobytes()
