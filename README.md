# ALi LCD Device Control

Linux communication library for the ALi Corp 0402:3922 LCD device.

## Overview

This project provides a robust implementation for communicating with the ALi Corp 0402:3922 LCD display device. The implementation is based on comprehensive reverse engineering of the device's protocol and behavior, documented in the [knowledge](knowledge/) directory.

## 🆕 NEW: Communication Sequence Analysis

We've identified the successful communication pattern with the device based on Wireshark USB captures and binary file examination. Two new scripts have been added to replicate this pattern:

- **scripts/replicate_sequence.py**: Implements the full lifecycle communication sequence
- **scripts/replay_frames.py**: Specifically replays binary frames in the exact observed sequence

See the [scripts README](scripts/README.md) for detailed usage instructions.

## Key Features

- **Lifecycle-Aware Communication**: Adapts to the device's four-state lifecycle for reliable operation
- **Robust Tag Synchronization**: Handles tag synchronization issues with state-specific strategies
- **Error Recovery**: Implements comprehensive error detection and recovery mechanisms
- **Image Display**: Provides tools for converting and displaying images on the device
- **Test Pattern Generation**: Includes utilities for generating test patterns
- **USB Diagnostics**: Tools to diagnose and fix common USB issues

## Simplified API and Tools

We've added a new simplified API (`ali_lcd_api.py`) and a collection of diagnostic and test tools that make it easier to work with the ALi LCD device:

- **api_lcd_api.py**: A simplified API for controlling the LCD device
- **display_image.py**: A simple script to display images on the LCD
- **tools/lcd_diagnostic.py**: Detailed diagnostic information about the device
- **tools/minimal_test.py**: Basic device operation tests
- **tools/simple_display_test.py**: Simple test pattern display
- **tools/robust_display_test.py**: Robust test with improved error handling
- **tools/final_display_test.py**: Comprehensive test incorporating all lessons learned

### Using the New API

```python
import ali_lcd_api

# Display an image on the LCD
ali_lcd_api.display_image('/path/to/your/image.png', debug=True)
```

### Quick Display Example

```bash
# Display a test pattern
sudo python3 display_image.py

# Display your own image
sudo python3 display_image.py --image /path/to/your/image.png
```

## Installation

### Prerequisites

- Python 3.6 or higher
- libusb development package
- PyUSB library

```bash
# Ubuntu/Debian
sudo apt install python3-dev python3-pip libusb-1.0-0-dev

# Install required Python packages
pip install pyusb Pillow

# Install the package
pip install -e .

# Set up udev rules (recommended)
sudo ./tools/install_udev_rules.sh
```

For detailed installation instructions, see [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Quick Start

```python
from ali_lcd_device.device import ALiLCDDevice

# Connect to the device
with ALiLCDDevice() as device:
    device.connect(wait_for_stable=True)
    device.initialize_display()
    device.display_image('path/to/image.png')
```

## Project Structure

- **src/ali_lcd_device/**: Core implementation
  - **device.py**: Main device interface
  - **lifecycle.py**: Lifecycle state management
  - **usb_comm.py**: USB communication layer
  - **commands.py**: SCSI command definitions
  - **image_utils.py**: Image conversion utilities

- **scripts/**: Communication sequence replication
  - **replicate_sequence.py**: Full lifecycle sequence implementation
  - **replay_frames.py**: Binary frame replay utility
  - **README.md**: Usage documentation

- **tools/**: Diagnostic and utility tools
  - **usb_diagnostic.py**: USB diagnostic utility
  - **reset_usb_device.sh**: Script to reset USB devices
  - **install_udev_rules.sh**: Script to install udev rules
  - **install_uas_quirks.sh**: Script to disable UAS for the device
  - **install_usbreset.sh**: Script to install the usbreset utility
  - **99-ali-lcd.rules**: udev rules for device access
  - **ali-lcd-uas-quirks.conf**: Modprobe config to disable UAS

- **examples/**: Usage examples
  - **basic_demo.py**: Simple demonstration
  - **advanced_demo.py**: More complex functionality
  - **lifecycle_demo.py**: Demonstrates lifecycle state handling

- **knowledge/**: Comprehensive documentation
  - **00-project-overview.md**: Project overview and summary
  - **01-device-specifications.md**: Hardware specifications
  - **02-usb-protocol.md**: USB protocol details
  - **03-lifecycle-states.md**: Device lifecycle states
  - **04-command-set.md**: Supported SCSI commands
  - **05-error-handling.md**: Error handling strategies
  - **06-image-format.md**: Image format documentation
  - **07-implementation-guidelines.md**: Implementation guidelines
  - **08-development-history.md**: Development history and challenges
  - **09-communication-sequence.md**: 🆕 Analysis of successful communication sequence

## Documentation

Detailed documentation is available in the [knowledge](knowledge/) directory:

- [Project Overview](knowledge/00-project-overview.md)
- [Device Specifications](knowledge/01-device-specifications.md)
- [USB Protocol](knowledge/02-usb-protocol.md)
- [Lifecycle States](knowledge/03-lifecycle-states.md)
- [Command Set](knowledge/04-command-set.md)
- [Error Handling](knowledge/05-error-handling.md)
- [Image Format](knowledge/06-image-format.md)
- [Implementation Guidelines](knowledge/07-implementation-guidelines.md)
- [Development History](knowledge/08-development-history.md)
- [Communication Sequence Analysis](knowledge/09-communication-sequence.md) 🆕

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

- **tests/**: Test suite
  - **test_lifecycle_states.py**: Lifecycle state tests
  - **test_tag_synchronization.py**: Tag synchronization tests

- **knowledge/**: Comprehensive documentation
  - **00-project-overview.md**: High-level project overview
  - **01-device-specifications.md**: Device hardware details
  - **02-usb-protocol.md**: USB protocol implementation
  - **03-lifecycle-states.md**: Device lifecycle states
  - **04-command-set.md**: SCSI command set details
  - **05-error-handling.md**: Error handling strategies
  - **06-image-format.md**: Image format and display
  - **07-implementation-guidelines.md**: Implementation recommendations
  - **08-development-history.md**: Project history and challenges
  - **09-usb-troubleshooting.md**: USB troubleshooting guide

## Troubleshooting

If you encounter "Resource busy" errors or other USB issues, try these steps:

1. Run the diagnostic tool: `python3 tools/usb_diagnostic.py`
2. Install udev rules: `sudo ./tools/install_udev_rules.sh`
3. Reset the USB device: `sudo ./tools/reset_usb_device.sh`
4. Disable UAS for the device: `sudo ./tools/install_uas_quirks.sh`
5. Install usbreset utility: `sudo ./tools/install_usbreset.sh`

For detailed troubleshooting steps, see [knowledge/09-usb-troubleshooting.md](knowledge/09-usb-troubleshooting.md).

## Development

See [ROADMAP.md](ROADMAP.md) for the development plan and timeline.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- The reverse engineering and documentation team for their comprehensive analysis
- The PyUSB project for providing the USB communication foundation
