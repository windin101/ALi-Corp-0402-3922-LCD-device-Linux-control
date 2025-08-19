# ALi LCD Device Control - Implementation Plan

This document outlines the implementation plan for the ALi Corp 0402:3922 LCD device communication library based on the knowledge base documentation.

## Installation

### Prerequisites

The following packages are required:

- Python 3.6 or higher
- libusb development package

#### Ubuntu/Debian

```bash
sudo apt update
sudo apt install python3-dev python3-pip libusb-1.0-0-dev
```

#### Fedora/RHEL/CentOS

```bash
sudo dnf install python3-devel python3-pip libusbx-devel
```

#### Arch Linux

```bash
sudo pacman -S python python-pip libusb
```

### Installing the Package

```bash
# Clone the repository
git clone https://github.com/windin101/ALi-Corp-0402-3922-LCD-device-Linux-control.git
cd ALi-Corp-0402-3922-LCD-device-Linux-control

# Install the package
pip install -e .
```

### USB Permissions

To access the USB device without root privileges, create a udev rule:

```bash
sudo nano /etc/udev/rules.d/99-ali-lcd.rules
```

Add the following content:

```
SUBSYSTEM=="usb", ATTRS{idVendor}=="0402", ATTRS{idProduct}=="3922", MODE="0666", GROUP="plugdev"
```

Then reload the rules:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## Usage Examples

### Basic Usage

```python
from ali_lcd_device.device import ALiLCDDevice

# Create device instance
device = ALiLCDDevice()

# Connect to the device
device.connect(wait_for_stable=True)

# Initialize the display
device.initialize_display()

# Display an image
device.display_image('path/to/image.png')

# Close the connection
device.close()
```

### Using a Context Manager

```python
from ali_lcd_device.device import ALiLCDDevice

with ALiLCDDevice() as device:
    device.connect(wait_for_stable=True)
    device.initialize_display()
    device.display_image('path/to/image.png')
```

### Displaying Test Patterns

```python
from ali_lcd_device.device import ALiLCDDevice
from ali_lcd_device.image_utils import create_gradient_pattern
from ali_lcd_device.commands import create_image_header, create_f5_display_image_command

with ALiLCDDevice() as device:
    device.connect(wait_for_stable=True)
    device.initialize_display()
    
    # Create a gradient test pattern
    width, height = 320, 320
    pattern_data = create_gradient_pattern(width, height)
    
    # Create header
    header = create_image_header(width, height, 0, 0)
    
    # Combine header and pattern data
    data = header + pattern_data
    
    # Send display command
    cmd, data_length, direction = create_f5_display_image_command(width, height, 0, 0)
    device._send_command(cmd, len(data), direction, data)
```

## Troubleshooting

### Common Issues

1. **Command Failures During Animation State**
   - This is normal and expected behavior
   - The device is less responsive during the Animation state
   - Commands will be retried automatically
   - Wait approximately 60 seconds for the device to reach the Connected state

2. **Permission Denied**
   - Ensure udev rules are set correctly
   - Try running with sudo to verify it's a permissions issue
   - Check the rules are loaded: `sudo udevadm control --reload-rules`

3. **Device Not Found**
   - Check the device is connected and recognized: `lsusb | grep 0402:3922`
   - Verify the kernel driver isn't claiming the device
   - Try unplugging and reconnecting the device

4. **Communication Errors**
   - Run the diagnostic tool: `python tools/diagnostic.py`
   - In Animation state, wait ~60 seconds for stable communication
   - Use wait_for_stable=True when connecting
   - Add `--debug` flag to enable verbose logging: `python examples/basic_demo.py --debug`

5. **Tag Synchronization Issues**
   - These are normal in certain states and handled automatically
   - If persistent, try reconnecting the device physically
   - The diagnostic tool can help identify tag mismatch patterns

### Debug Mode

To enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Next Steps

1. **Run the Basic Demo**
   ```bash
   cd examples
   python basic_demo.py
   ```

2. **Run Unit Tests**
   ```bash
   python -m unittest discover tests
   ```

3. **Customize and Extend**
   - Add support for additional display modes
   - Implement more efficient image update methods
   - Create a GUI application for easy control
