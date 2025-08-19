# ALi LCD Device Project - Knowledge Index

This directory contains a comprehensive knowledge base for the ALi Corp 0402:3922 LCD device communication project. These documents capture all our findings, implementation details, and recommendations for working with the device.

## Document Index

1. **[Project Overview](00-project-overview.md)**
   - High-level summary of the project, goals, and implementation status
   - Quick facts and critical knowledge

2. **[Device Specifications](01-device-specifications.md)**
   - Hardware identification details
   - Display specifications and capabilities
   - Physical characteristics

3. **[USB Protocol Implementation](02-usb-protocol.md)**
   - Mass Storage BOT protocol details
   - Command Block Wrapper (CBW) structure
   - Command Status Wrapper (CSW) structure
   - Tag synchronization issues

4. **[Device Lifecycle States](03-lifecycle-states.md)**
   - Four-state lifecycle model
   - State characteristics and transition timing
   - State-specific communication strategies

5. **[SCSI Command Set](04-command-set.md)**
   - Standard SCSI commands supported
   - Custom F5 commands for display control
   - Command formats and examples
   - Initialization sequence

6. **[Error Handling Strategies](05-error-handling.md)**
   - Common error types and causes
   - Recovery strategies for each error type
   - Implementation recommendations
   - Code examples

7. **[Image Format and Display](06-image-format.md)**
   - RGB565 color format details
   - Image conversion techniques
   - Display command format
   - Performance considerations

8. **[Implementation Guidelines](07-implementation-guidelines.md)**
   - Architecture overview
   - Core components design
   - Threading model
   - Usage examples
   - Testing strategy

9. **[Development History and Challenges](08-development-history.md)**
   - Project timeline
   - Major challenges encountered
   - Investigation methods
   - Solutions implemented
   - Lessons learned

## Using This Knowledge Base

This knowledge base is designed to provide both high-level understanding and detailed implementation guidance. For:

- **New Developers**: Start with the Project Overview and Device Specifications, then proceed to the Implementation Guidelines.

- **Protocol Understanding**: Focus on the USB Protocol Implementation, Device Lifecycle States, and SCSI Command Set documents.

- **Troubleshooting**: Refer to Error Handling Strategies and Development History and Challenges.

- **Implementation**: Use Implementation Guidelines along with the SCSI Command Set and Image Format documents.

## Integration with Source Code

The knowledge captured in these documents is implemented in the Python code under:

- `src/ali_lcd_device/`: Main package
- `scripts/`: Utility scripts
- `tests/`: Test suite

The technical reference document `ALi_LCD_Technical_Reference.md` in the project root provides a comprehensive overview of all aspects of the device.

## Conclusion

This knowledge base represents the culmination of our research into the ALi Corp 0402:3922 LCD device. With this information, another team should be able to quickly understand the device's behavior and implement reliable communication without repeating our discovery process.
