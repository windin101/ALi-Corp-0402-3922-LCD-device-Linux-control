# ALi LCD Device Control

Linux communication library for the ALi Corp 0402:3922 LCD device.

## Overview

This project provides a robust implementation for communicating with the ALi Corp 0402:3922 LCD display device. The implementation is based on comprehensive reverse engineering of the device's protocol and behavior, documented in the [knowledge](knowledge/) directory.

## Key Features

- **Lifecycle-Aware Communication**: Adapts to the device's four-state lifecycle for reliable operation
- **Robust Tag Synchronization**: Handles tag synchronization issues with state-specific strategies
- **Error Recovery**: Implements comprehensive error detection and recovery mechanisms
- **Image Display**: Provides tools for converting and displaying images on the device
- **Test Pattern Generation**: Includes utilities for generating test patterns

## Installation

### Prerequisites

- Python 3.6 or higher
- libusb development package

```bash
# Ubuntu/Debian
sudo apt install python3-dev python3-pip libusb-1.0-0-dev

# Install the package
pip install -e .
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

- **examples/**: Usage examples
  - **basic_demo.py**: Simple demonstration

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

## Development

See [ROADMAP.md](ROADMAP.md) for the development plan and timeline.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- The reverse engineering and documentation team for their comprehensive analysis
- The PyUSB project for providing the USB communication foundation
