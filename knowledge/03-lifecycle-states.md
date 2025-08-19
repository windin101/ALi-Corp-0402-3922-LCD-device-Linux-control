# Device Lifecycle States

## Overview

The ALi LCD device operates in a distinct four-state lifecycle that significantly affects communication reliability and behavior. Understanding these states is critical for robust implementation.

## State Diagram

```
┌────────────┐       ~56-58 seconds       ┌──────────────┐
│  ANIMATION ├─────────────────────────────▶  CONNECTING  │
└─────▲──────┘                             └──────┬───────┘
      │                                           │
      │                                           │ few seconds
      │           10-second countdown             │
      │                                           │
┌─────┴──────┐                             ┌──────▼───────┐
│DISCONNECTED◀─────────────────────────────┤   CONNECTED  │
└────────────┘  no commands for ~5 seconds └──────────────┘
```

## State Descriptions

### 1. Animation State

- **Visual Indicator**: Device shows looping animation
- **USB Behavior**: 
  - Partially unresponsive to USB commands
  - High rate of "resource busy" errors
  - High tag mismatch rate (>75%)
  - Multiple disconnections and reconnections may occur
- **Duration**: Initial state, lasts until ~56-58 seconds of continuous commands
- **Command Strategy**: 
  - Send commands with longer delays (200-500ms)
  - Ignore tag mismatches
  - Implement aggressive error recovery

### 2. Connecting State

- **Visual Indicator**: Transitional animation
- **USB Behavior**:
  - Moderate tag mismatch rate (25-50%)
  - First successful command often returns unexpected tag
  - More stable than Animation state
- **Duration**: Brief transitional state, typically a few seconds
- **Command Strategy**:
  - Maintain consistent command pacing
  - Validate tags but allow for some mismatches
  - Continue normal command sequence

### 3. Connected State

- **Visual Indicator**: "Waiting for connection" message
- **USB Behavior**:
  - Fully responsive to commands
  - Low tag mismatch rate (<5% under normal conditions)
  - Sequential tag increments generally honored
  - Ready for actual data transfer commands
- **Duration**: Remains in this state as long as commands are sent regularly
- **Command Strategy**:
  - Enforce strict tag validation
  - Use full command set
  - Maintain regular command polling (at least one command every 5 seconds)

### 4. Disconnected State

- **Visual Indicator**: "Connections lost will close in 10 seconds"
- **USB Behavior**:
  - Countdown display before returning to Animation state
  - Variable tag behavior
  - May accept some commands during countdown
- **Duration**: 10 seconds from last command in Connected state
- **Command Strategy**:
  - Reconnect quickly if detected
  - Reset tag counter if reconnection occurs
  - Prepare for return to Animation state

## Implementation Recommendations

1. **State Tracking**:
   - Maintain explicit state tracking in code
   - Use elapsed time and command count to detect Animation → Connected transition
   - Monitor command timestamps to detect potential disconnection

2. **State-Specific Behavior**:
   - Implement different communication strategies for each state
   - Use adaptive tag validation based on current state
   - Apply different retry policies per state

3. **Monitoring Thread**:
   - Implement a dedicated thread for state monitoring
   - Send keep-alive commands to prevent disconnection
   - Handle state transitions gracefully

## Critical Timing Requirements

- **Animation → Connected Transition**: ~56-58 seconds of continuous commands
- **Connected → Disconnected Transition**: ~5 seconds of no commands
- **Disconnected → Animation Transition**: 10-second countdown
