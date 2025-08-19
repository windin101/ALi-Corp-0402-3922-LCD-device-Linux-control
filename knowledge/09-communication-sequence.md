# Communication Sequence Analysis

## Overview

This document describes the successful communication sequence with the ALi LCD device based on Wireshark USB capture analysis and binary file examination. This sequence represents a working pattern for reliable device communication.

## USB Communication Pattern

Analysis of successful Wireshark logs reveals a specific pattern of commands and data transfers required for proper device operation:

1. **Initialization Phase**:
   - Initial device connection
   - Sequence of TEST UNIT READY and F5 commands
   - Approximately 56-58 seconds of continuous commands

2. **Steady State Communication**:
   - Alternating F5 commands with bulk data transfers
   - Consistent pattern of data sizes: ~57,600 bytes followed by ~38,400 bytes
   - Regular command timing with minimal delays between commands

3. **Data Sequence Pattern**:
   - Each display update follows a specific sequence:
     - F5 command to prepare the device
     - Bulk data transfer (image data)
     - Status verification
     - Next F5 command

## Hex Dump Analysis

The binary files captured in the Hex Dumps folder reveal crucial information about the data sent to the device:

- **File Sizes**: Two distinct sizes observed
  - ~57,600 bytes (57,627 bytes)
  - ~38,400 bytes (38,427 bytes)

- **File Content Pattern**:
  - Files appear to contain RGB565 image data
  - Headers consistent with display command format
  - Alternating between larger and smaller image frames
  - Files likely represent individual frames of an animation or UI

## Critical Timing and Sequencing

Based on Wireshark analysis, successful communication requires:

1. **Continuous Command Stream**:
   - Regular commands during Animation state (~56-58 seconds)
   - No gaps longer than ~5 seconds in Connected state
   - Proper sequencing of F5 commands

2. **Data Transfer Pattern**:
   - Alternating between two image sizes:
     1. Large frame (~57,600 bytes)
     2. Small frame (~38,400 bytes)
   - Consistent timing between frames

3. **Command Sequencing**:
   - F5 command to prepare device
   - Data transfer (bulk OUT)
   - Status verification (CSW)
   - Brief delay (50-100ms)
   - Next F5 command

## Implementation Recommendations

To replicate this successful communication pattern:

1. **Create an Initialization Sequence**:
   - Implement a script that sends TEST UNIT READY and F5 commands continuously
   - Continue for at least 56-58 seconds to transition to Connected state
   - Monitor for visual indicators of state transitions

2. **Implement Frame Sequence**:
   - Prepare alternating image data matching the observed sizes
   - Create a sequence that rotates through the frames in the correct order
   - Maintain consistent timing between frames

3. **Monitor State Transitions**:
   - Watch for visual cues on the display indicating state changes
   - Adjust command strategy based on current state
   - Implement recovery if state reverts to Animation

## Next Steps

1. Create a script to replicate the exact sequence observed in the Wireshark logs
2. Analyze binary files to extract precise image format and headers
3. Implement a robust communication pattern based on these observations
4. Test with varying data sizes to determine flexibility of the protocol
