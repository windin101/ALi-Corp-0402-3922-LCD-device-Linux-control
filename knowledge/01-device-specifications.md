# Device Specifications

## ALi Corp 0402:3922 LCD Device

### Hardware Identification

- **Vendor ID**: 0x0402 (ALi Corporation)
- **Product ID**: 0x3922
- **USB Class**: Mass Storage (0x08)
- **Endpoints**: Bulk IN and OUT
- **USB Version**: 2.0

### Device Inquiry Response

- **Vendor**: "Xsail"
- **Product**: "USB PRC System"
- **Revision**: Binary `\x00\x01\x00\x00` (likely 1.0.0)

### Display Specifications

- **Resolutions**:
  - 320×320 pixels (standard)
  - 480×320 pixels (wide)
  - 480×480 pixels (square)
  
- **Color Depth**: 16-bit RGB565
  - Red: 5 bits (0-31)
  - Green: 6 bits (0-63)
  - Blue: 5 bits (0-31)
  - Format: `RRRRRGGG GGGBBBBB` (high byte first)

- **Data Sizes**:
  - 320×320: 204,800 bytes (320×320×2)
  - 480×480: 460,800 bytes (480×480×2)

### Physical Characteristics

- **Connection**: USB 2.0 Type-A
- **Power**: USB bus-powered
- **Display Type**: TFT LCD
- **Backlight**: LED

### Original Product Context

The device appears to be used in products like the Thermalright LCD Monitor, which displays system information such as temperatures, fan speeds, and performance metrics on a small external display.
