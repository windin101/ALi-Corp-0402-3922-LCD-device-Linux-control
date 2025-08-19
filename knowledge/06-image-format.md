# Image Format and Display

## RGB565 Color Format

The ALi LCD device uses the RGB565 color format for all image data:

- **Color Depth**: 16 bits per pixel
- **Component Allocation**:
  - Red: 5 bits (values 0-31)
  - Green: 6 bits (values 0-63)
  - Blue: 5 bits (values 0-31)
- **Byte Order**: High byte first
- **Bit Layout**: `RRRRRGGG GGGBBBBB`

### Converting RGB888 to RGB565

```python
def rgb888_to_rgb565(r, g, b):
    """Convert RGB888 (24-bit) to RGB565 (16-bit)."""
    r = (r >> 3) & 0x1F  # 5 bits for red
    g = (g >> 2) & 0x3F  # 6 bits for green
    b = (b >> 3) & 0x1F  # 5 bits for blue
    
    # Combine components into RGB565 (high byte first)
    high_byte = ((r << 3) | (g >> 3)) & 0xFF
    low_byte = ((g << 5) | b) & 0xFF
    
    return bytes([high_byte, low_byte])
```

### Converting an Image to RGB565

```python
def convert_image_to_rgb565(image_path):
    """Convert an image file to RGB565 format."""
    from PIL import Image
    import numpy as np
    
    # Open and convert image to RGB
    image = Image.open(image_path).convert('RGB')
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
```

## Display Command Format

To display an image, use the 0xF5 command with subcommand 0xB0:

### Command Structure

```
[0xF5] [0xB0] [Image format] [X start (2 bytes)] [Y start (2 bytes)] [Width (2 bytes)] [Height (2 bytes)] [Image data]
```

### Image Header Format

| Offset | Field | Size | Description |
|--------|-------|------|-------------|
| 0 | Image format | 1 byte | 0x01 for RGB565 |
| 1 | Reserved | 1 byte | 0x00 |
| 2-3 | X start | 2 bytes | X coordinate (big-endian) |
| 4-5 | Y start | 2 bytes | Y coordinate (big-endian) |
| 6-7 | Width | 2 bytes | Image width (big-endian) |
| 8-9 | Height | 2 bytes | Image height (big-endian) |

### Complete Display Command Example

```python
def display_image(device, image_path, x=0, y=0):
    """Display an image on the ALi LCD device."""
    # Convert image to RGB565
    image_data, width, height = convert_image_to_rgb565(image_path)
    
    # Create image header
    header = bytes([
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
    
    # Combine header and image data
    data = header + image_data
    
    # Create and send display command
    command = create_f5_command(0xB0, len(data))
    success, _ = device._send_command(command, data_out=data)
    
    return success
```

## Display Sequence

For optimal display results, follow this sequence:

1. **Initialize Display** (if not already done):
   ```python
   device.initialize_display()
   ```

2. **Set Display Mode**:
   ```python
   device.set_display_mode(5)  # Standard mode
   ```

3. **Stop Animation** (if active):
   ```python
   device.control_animation(False)
   ```

4. **Clear Screen**:
   ```python
   device.clear_screen()
   ```

5. **Display Image**:
   ```python
   device.display_image(image_path, x, y)
   ```

## Display Resolutions

The device supports multiple display resolutions:

- **320×320 pixels**: Standard square format
  - 204,800 bytes (320×320×2)
  
- **480×320 pixels**: Wide format
  - 307,200 bytes (480×320×2)
  
- **480×480 pixels**: Large square format
  - 460,800 bytes (480×480×2)

## Performance Considerations

1. **Memory Usage**:
   - Large images require significant memory
   - Pre-process images to match display resolution

2. **Transfer Speed**:
   - Full-screen updates are relatively slow (~200-500ms)
   - Consider partial updates for animations

3. **Image Conversion**:
   - Convert images to RGB565 in advance for better performance
   - Cache converted images when displaying the same image multiple times

## Advanced Techniques

### Partial Screen Updates

For faster updates, only update the changed portion of the screen:

```python
def update_region(device, image_data, x, y, width, height):
    """Update only a specific region of the screen."""
    # Create header for region
    header = bytes([
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
    
    # Send update command
    command = create_f5_command(0xB0, len(header) + len(image_data))
    device._send_command(command, data_out=header + image_data)
```

### Creating Test Patterns

Test patterns are useful for verifying display functionality:

```python
def create_gradient_pattern(width, height):
    """Create a gradient test pattern."""
    import numpy as np
    
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
```
