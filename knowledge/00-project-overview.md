# Project Overview

## ALi Corp 0402:3922 LCD Device Discovery Project

This project documents the reverse engineering and implementation of communication protocols for the ALi Corp 0402:3922 LCD device. This document serves as a high-level overview of all findings and implementations.

## Quick Facts

- **Device**: ALi Corp 0402:3922 LCD Display
- **Protocol**: USB Mass Storage with custom SCSI commands
- **Key Command**: 0xF5 with various subcommands for display control
- **Display Format**: RGB565 (16-bit color)
- **Known Issues**: Tag synchronization, lifecycle state transitions, pipe errors

## Project Components

1. **Technical Documentation**
   - `ALi_LCD_Technical_Reference.md`: Comprehensive technical analysis
   - Analysis files in the `analysis/` directory

2. **Implementation**
   - Python package in `src/ali_lcd_device/`
   - Utility scripts in `scripts/`
   - Test suite in `tests/`

3. **Key Discoveries**
   - Device lifecycle states (Animation → Connecting → Connected → Disconnected)
   - Tag synchronization issues correlated with lifecycle states
   - Custom 0xF5 SCSI command with various subcommands
   - Proper initialization sequence and timing requirements

## Project Goals

1. Understand the USB Mass Storage protocol implementation
2. Identify all supported SCSI commands and custom extensions
3. Implement robust communication with proper error handling
4. Create a reliable display control interface
5. Document all findings for future reference

## Implementation Status

- [x] Basic device communication
- [x] Lifecycle state tracking
- [x] Tag synchronization handling
- [x] Error recovery mechanisms
- [x] Display control commands
- [x] Image conversion utilities
- [x] Testing and debugging tools

## Critical Knowledge

The most important discovery is that the device operates in a four-state lifecycle, and tag synchronization issues are directly tied to these states. Reliable communication requires:

1. Lifecycle-aware tag management
2. Proper initialization sequence and timing
3. Robust error handling for pipe errors and disconnections
4. Understanding of the custom 0xF5 command set

## Next Steps

1. Implement additional display functionality
2. Create a high-level interface for common operations
3. Develop a graphical control application
4. Test with various display resolutions and image formats
