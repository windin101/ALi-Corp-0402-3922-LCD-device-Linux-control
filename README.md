Project Overview
ALi Corp 0402:3922 LCD Device Discovery Project
This project documents the reverse engineering and implementation of communication protocols for the ALi Corp 0402:3922 LCD device. This document serves as a high-level overview of all findings and implementations.

Quick Facts
Device: ALi Corp 0402:3922 LCD Display
Protocol: USB Mass Storage with custom SCSI commands
Key Command: 0xF5 with various subcommands for display control
Display Format: RGB565 (16-bit color)
Known Issues: Tag synchronization, lifecycle state transitions, pipe errors
Project Components
Technical Documentation

ALi_LCD_Technical_Reference.md: Comprehensive technical analysis
Analysis files in the analysis/ directory
Implementation

Python package in src/ali_lcd_device/
Utility scripts in scripts/
Test suite in tests/
Key Discoveries

Device lifecycle states (Animation → Connecting → Connected → Disconnected)
Tag synchronization issues correlated with lifecycle states
Custom 0xF5 SCSI command with various subcommands
Proper initialization sequence and timing requirements
Project Goals
Understand the USB Mass Storage protocol implementation
Identify all supported SCSI commands and custom extensions
Implement robust communication with proper error handling
Create a reliable display control interface
Document all findings for future reference
Implementation Status
 Basic device communication
 Lifecycle state tracking
 Tag synchronization handling
 Error recovery mechanisms
 Display control commands
 Image conversion utilities
 Testing and debugging tools
Critical Knowledge
The most important discovery is that the device operates in a four-state lifecycle, and tag synchronization issues are directly tied to these states. Reliable communication requires:

Lifecycle-aware tag management
Proper initialization sequence and timing
Robust error handling for pipe errors and disconnections
Understanding of the custom 0xF5 command set
Next Steps
Implement additional display functionality
Create a high-level interface for common operations
Develop a graphical control application
Test with various display resolutions and image formats
