# USB Protocol Implementation

## USB Mass Storage Protocol

The ALi LCD device implements the USB Mass Storage Bulk-Only Transport (BOT) protocol with SCSI commands. This document details the specific implementation and command structure.

### Command Block Wrapper (CBW)

The CBW is a 31-byte structure sent from host to device to initiate a command:

```
Offset | Size | Field                    | Description
-------|------|--------------------------|------------
0      | 4    | dCBWSignature            | "USBC" (0x43425355) in little-endian
4      | 4    | dCBWTag                  | Command tag (host increments this value)
8      | 4    | dCBWDataTransferLength   | Number of bytes to transfer
12     | 1    | bmCBWFlags               | Direction (0x80 = device-to-host, 0x00 = host-to-device)
13     | 1    | bCBWLUN                  | Logical Unit Number (usually 0)
14     | 1    | bCBWCBLength             | Length of the SCSI command (1-16)
15     | 16   | CBWCB                    | The SCSI command itself
```

### Command Status Wrapper (CSW)

The CSW is a 13-byte structure returned from device to host after command completion:

```
Offset | Size | Field                    | Description
-------|------|--------------------------|------------
0      | 4    | dCSWSignature            | "USBS" (0x53425355) in little-endian
4      | 4    | dCSWTag                  | Same tag as in the CBW
8      | 4    | dCSWDataResidue          | Difference between expected and actual data transferred
12     | 1    | bCSWStatus               | Status (0 = success, 1 = failure, 2 = phase error)
```

## USB Communication Flow

1. **Command Phase**:
   - Host sends CBW with SCSI command
   - Device parses command

2. **Data Phase** (if applicable):
   - Host-to-Device: Host sends data to device
   - Device-to-Host: Device sends data to host

3. **Status Phase**:
   - Device sends CSW with command status

## Tag Synchronization Issues

The device has significant issues with CSW tag synchronization:

- **Animation State**: High frequency of tag mismatches (>75%)
- **Connecting State**: Moderate mismatches (25-50%)
- **Connected State**: Low mismatches (<5%)
- **Disconnected State**: Variable behavior

### Tag Reset Triggers

The device appears to reset its internal tag counter during:
- Physical reconnection events
- Transitions between lifecycle states
- Certain error conditions

## Implementation Notes

1. **Tag Management**:
   - Always reset local tag counter after device reconnection
   - Implement lifecycle-aware tag validation
   - Expect and handle tag mismatches in certain states

2. **Communication Timing**:
   - Add delays between commands (50-200ms) in Animation state
   - Sequence commands rapidly in Connected state
   - Maintain regular polling in Connected state to prevent disconnection

3. **Error Handling**:
   - Clear halts on endpoints when pipe errors occur
   - Implement retry logic with exponential backoff
   - Reset device if errors persist
