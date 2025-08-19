# SCSI Command Set

## Standard SCSI Commands

The ALi LCD device selectively implements standard SCSI commands from the USB Mass Storage specification:

| Command | Code | Description | Status | Notes |
|---------|------|-------------|--------|-------|
| TEST UNIT READY | 0x00 | Check if device is ready | Working | Most reliable command |
| REQUEST SENSE | 0x03 | Get error information | Working | Returns sense data after errors |
| INQUIRY | 0x12 | Get device information | Working | Returns "Xsail USB PRC System" |
| MODE SENSE | 0x1A | Get device parameters | Not tested | May not be implemented |
| READ CAPACITY | 0x25 | Get storage capacity | Not working | Causes pipe error |
| READ(10) | 0x28 | Read data blocks | Not tested | Likely not implemented |
| WRITE(10) | 0x2A | Write data blocks | Not tested | Likely not implemented |

## Custom Command Set (0xF5)

The device implements a custom SCSI command (0xF5) with various subcommands for display control:

| Subcommand | Description | Data Direction | Data Format | Notes |
|------------|-------------|----------------|-------------|-------|
| 0x00 | Reset Device | None | None | Resets device to Animation state |
| 0x01 | Initialize Display | None | None | Required before other display commands |
| 0x10 | Animation Control | OUT | 1 byte (0=stop, 1=start) | Controls built-in animation |
| 0x20 | Set Mode | OUT | 4 bytes (mode 5 is standard) | Sets display operational mode |
| 0x30 | Get Status | IN | 8 bytes (status information) | Returns current device status |
| 0xA0 | Clear Screen | None | None | Blanks the display |
| 0xB0 | Display Image | OUT | Image data (see below) | Sends image data to display |

## Command Details

### TEST UNIT READY (0x00)
```
Command: 00 00 00 00 00 00
Data: None
Response: Standard CSW
```
- Most reliable command for probing device state
- Use frequently to maintain connection

### INQUIRY (0x12)
```
Command: 12 00 00 00 36 00
Data: None
Response: 36 bytes of device information
```
- Returns vendor, product, and revision information
- Fixed-length response (36 bytes)

### REQUEST SENSE (0x03)
```
Command: 03 00 00 00 12 00
Data: None
Response: 18 bytes of sense data
```
- Use after command failures to get error details
- Sense key 5 (ILLEGAL REQUEST) is common

### F5 Command Format
```
Command: F5 [subcommand] 00 00 00 00 00 00 00 00 00 00
Data: Depends on subcommand
Response: Standard CSW
```

### Image Display Command (0xF5 0xB0)
```
Command: F5 B0 00 00 00 00 00 00 00 00 00 00
Data: [Header (10 bytes)] + [Image data in RGB565 format]
Response: Standard CSW
```

#### Image Header Format
```
Byte 0: Image format (0x01 for RGB565)
Byte 1: Reserved (0x00)
Bytes 2-3: X start position (big-endian)
Bytes 4-5: Y start position (big-endian)
Bytes 6-7: Width (big-endian)
Bytes 8-9: Height (big-endian)
```

## Command Sequence Examples

### Initialization Sequence
```
1. TEST UNIT READY
2. INQUIRY
3. F5 0x01 (Initialize Display)
4. F5 0x30 (Get Status)
5. F5 0x20 (Set Mode) with data 05 00 00 00
```

### Display Image Sequence
```
1. F5 0x10 (Animation Control) with data 00 (stop)
2. F5 0xA0 (Clear Screen)
3. F5 0xB0 (Display Image) with header and image data
```

## Implementation Notes

1. Always initialize the display (F5 0x01) before other display commands
2. Stop animation (F5 0x10 with data 0x00) before displaying images
3. Set mode to 5 (F5 0x20 with data 05 00 00 00) for standard operation
4. The image data must be in RGB565 format with the proper header
