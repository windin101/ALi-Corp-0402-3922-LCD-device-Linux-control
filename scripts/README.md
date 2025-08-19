# ALi LCD Device Sequence Replication Scripts

This directory contains scripts for replicating the successful communication sequence with the ALi LCD device based on our Wireshark analysis and hex dump examination.

## Available Scripts

### 1. `replicate_sequence.py`

This script implements the full communication lifecycle with the ALi LCD device, from initial connection through Animation state to Connected state, and then replays frames.

```bash
# Run with default settings
./replicate_sequence.py --frames /path/to/Hex\ Dumps

# Run with verbose logging
./replicate_sequence.py --frames /path/to/Hex\ Dumps --verbose

# Run for a specific duration
./replicate_sequence.py --frames /path/to/Hex\ Dumps --duration 600
```

#### Features:
- Implements full lifecycle state management
- Handles tag synchronization issues adaptively
- Includes robust error handling
- Transitions through all device states
- Displays frames from the specified directory

### 2. `replay_frames.py`

This simpler script focuses solely on replaying the binary frames from the Hex Dumps directory in the exact sequence observed in successful Wireshark captures.

```bash
# Basic usage
./replay_frames.py /path/to/Hex\ Dumps

# Run multiple cycles with specific delay
./replay_frames.py /path/to/Hex\ Dumps --cycles 3 --delay 0.2

# Verbose mode
./replay_frames.py /path/to/Hex\ Dumps --verbose
```

#### Features:
- Directly sends frames without full initialization sequence
- Simpler implementation focused on frame replay
- Useful when device is already in Connected state
- Can repeat the sequence multiple times

### 4. `minimal_connection.py`

This script takes a more careful approach, focusing first on establishing and maintaining a stable connection before attempting any complex operations. It includes interactive pauses to allow you to observe the device state between phases.

```bash
# Basic usage
./minimal_connection.py --frames_dir /path/to/Hex\ Dumps

# Verbose mode
./minimal_connection.py --frames_dir /path/to/Hex\ Dumps --verbose
```

#### Features:
- Focuses on establishing a stable connection first
- Pauses for user input between critical phases
- Uses simple commands (TEST UNIT READY, INQUIRY) to maintain connection
- More gradual approach to test device stability
- Helpful for debugging connection issues

### 5. `exact_sequence.py`

This script attempts to replicate the exact command sequence, timing, and payload structure observed in the successful Wireshark captures. Instead of attempting to be smart about state transitions, it precisely mimics the working sequence.

```bash
# Basic usage
./exact_sequence.py /path/to/Hex\ Dumps

# Verbose mode
./exact_sequence.py /path/to/Hex\ Dumps --verbose
```

#### Features:
- Reproduces the exact timing and command sequence from successful captures
- Follows precise state transition timing (55s in Animation, 3s in Connecting)
- Uses the specific F5 command sequence that was observed to work
- Sends TEST UNIT READY commands at the exact intervals observed in captures
- More focused on exact replication than error handling

### 6. `hybrid_approach.py`

This script combines the best elements from all previous approaches, with improved error handling, reconnection capabilities, and a more robust state management system. It has interactive pauses to help debug each phase separately.

```bash
# Basic usage
./hybrid_approach.py /path/to/Hex\ Dumps

# Interactive mode with prompts between phases
./hybrid_approach.py /path/to/Hex\ Dumps --interactive

# Verbose mode with detailed logging
./hybrid_approach.py /path/to/Hex\ Dumps --verbose

# Limit the number of frames to send
./hybrid_approach.py /path/to/Hex\ Dumps --max-frames 2
```

#### Features:
- Combines successful elements from all previous scripts
- Enhanced error handling and device reconnection capabilities
- Robust state management with clear phase transitions
- Careful stabilization period before complex commands
- Interactive mode to pause between phases for debugging
- Strategic timing of commands to maintain stable connection
- Improved logging and diagnostic information

## Prerequisites

- Python 3.6+
- PyUSB library (`pip install pyusb`)
- Appropriate USB permissions (run with sudo or configure udev rules)
- Connected ALi LCD device (0402:3922)

## Usage Notes

1. If the device is in Animation state, use either `replicate_sequence.py` or `init_and_replay.py` which both handle the transition to Connected state.

2. Use `init_and_replay.py` for the most reliable operation as it leverages the proven ALiLCDDevice class from the main implementation.

3. The binary frames should be in the specified directory. By default, the scripts look for `.bin` files and sort them alphabetically.

4. If you encounter USB errors, try:
   - Reconnecting the device
   - Running with sudo
   - Setting up proper udev rules
