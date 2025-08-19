# Error Handling Strategies

## Common Error Types

The ALi LCD device exhibits several recurring error patterns that require specific handling strategies:

### 1. USB Pipe Errors

- **Symptoms**: Command timeouts, error code 32, "Pipe error"
- **Causes**:
  - Endpoint stalled
  - Device busy with internal processing
  - Commands sent during Animation state
  - Commands sent too rapidly
- **Occurrence Rate**: High in Animation state, moderate in other states

### 2. Resource Busy Errors

- **Symptoms**: "Resource busy" messages, errno 16
- **Causes**:
  - Kernel driver still attached
  - Multiple processes accessing device
  - Device in transition between states
- **Occurrence Rate**: Moderate, especially during initialization

### 3. Tag Mismatch Errors

- **Symptoms**: CSW tag different from CBW tag
- **Causes**:
  - Device internal tag counter reset
  - Lifecycle state transitions
  - Device reconnection events
- **Occurrence Rate**: Varies by lifecycle state (75%+ in Animation, <5% in Connected)

### 4. Device Disconnection

- **Symptoms**: "No device" errors, device disappears from USB bus
- **Causes**:
  - Internal device reset due to errors
  - Invalid commands
  - Power issues
- **Occurrence Rate**: Low to moderate, typically after serious errors

## Error Recovery Strategies

### For USB Pipe Errors

1. **Clear Endpoint Halts**:
   ```python
   try:
       device.clear_halt(endpoint_address)
   except usb.core.USBError:
       # Try device reset as fallback
       device.reset()
   ```

2. **Add Command Delays**:
   ```python
   # Adaptive delay based on device state
   if state == DeviceLifecycleState.ANIMATION:
       time.sleep(0.2)  # 200ms in Animation state
   else:
       time.sleep(0.05)  # 50ms in other states
   ```

3. **Reset Endpoints**:
   ```python
   # Reset both IN and OUT endpoints
   device.clear_halt(ep_out.bEndpointAddress)
   device.clear_halt(ep_in.bEndpointAddress)
   time.sleep(0.1)  # Short delay after reset
   ```

### For Resource Busy Errors

1. **Detach Kernel Driver**:
   ```python
   if device.is_kernel_driver_active(interface_number):
       device.detach_kernel_driver(interface_number)
   ```

2. **Exponential Backoff**:
   ```python
   retry_delay = 0.1  # Initial delay
   for attempt in range(max_retries):
       try:
           # Try operation
           return success
       except USBError as e:
           if "resource busy" in str(e).lower():
               time.sleep(retry_delay)
               retry_delay *= 2  # Double delay for next attempt
   ```

3. **Device Reset**:
   ```python
   try:
       device.reset()
       time.sleep(1.0)  # Longer delay after reset
   except usb.core.USBError:
       # Handle reset failure
       pass
   ```

### For Tag Mismatch Errors

1. **Lifecycle-Aware Validation**:
   ```python
   def validate_tag(expected_tag, actual_tag, lifecycle_state):
       if lifecycle_state == DeviceLifecycleState.ANIMATION:
           return True  # Accept any tag in Animation state
       elif lifecycle_state == DeviceLifecycleState.CONNECTING:
           return abs(expected_tag - actual_tag) < 10  # Flexible in Connecting
       else:
           return expected_tag == actual_tag  # Strict in Connected state
   ```

2. **Tag Reset Detection**:
   ```python
   def detect_tag_reset(actual_tag):
       if actual_tag < 5 and current_tag > 100:
           # Device likely reset its tag counter
           reset_tag_counter()
           return True
       return False
   ```

3. **Tag History Tracking**:
   ```python
   tag_history = deque(maxlen=50)
   
   def track_tag(tag):
       tag_history.append(tag)
       # Analyze patterns to detect resets or anomalies
   ```

### For Device Disconnection

1. **Reconnection Logic**:
   ```python
   def reconnect():
       for attempt in range(max_attempts):
           try:
               # Find and initialize device
               return True
           except (USBError, DeviceNotFoundError):
               time.sleep(1.0)
       return False
   ```

2. **State Reset**:
   ```python
   def handle_disconnection():
       # Reset all state tracking
       lifecycle_state = DeviceLifecycleState.UNKNOWN
       tag_monitor.reset()
       display_initialized = False
       
       # Attempt reconnection
       return reconnect()
   ```

3. **Watchdog Thread**:
   ```python
   def watchdog_thread():
       while running:
           if time.time() - last_command_time > 5.0:
               # No commands for 5 seconds, device may disconnect
               send_keepalive_command()
           time.sleep(1.0)
   ```

## Error Logging and Analysis

1. **Structured Error Logging**:
   ```python
   def log_error(error, context):
       logger.error(f"Error: {error}, State: {context['state']}, "
                   f"Last command: {context['last_command']}, "
                   f"Tag: {context['tag']}")
   ```

2. **Error Statistics Collection**:
   ```python
   error_stats = {
       'pipe_errors': 0,
       'busy_errors': 0,
       'tag_mismatches': 0,
       'disconnections': 0
   }
   
   def track_error(error_type):
       error_stats[error_type] += 1
   ```

## Implementation Recommendations

1. **Use Context Managers**:
   ```python
   with RobustUSBSession() as session:
       # Operations with automatic error handling
       pass
   ```

2. **Implement Retry Decorators**:
   ```python
   @retry_with_backoff(max_retries=3, initial_delay=0.1)
   def send_command(command):
       # Command sending logic
   ```

3. **State-Based Error Handling**:
   ```python
   def handle_error(error):
       if lifecycle_state == DeviceLifecycleState.ANIMATION:
           # Animation state strategy
       elif lifecycle_state == DeviceLifecycleState.CONNECTED:
           # Connected state strategy
       # etc.
   ```

4. **Lifecycle-Aware Recovery**:
   - Animation state: Focus on maintaining command sequence
   - Connecting state: Focus on tag management
   - Connected state: Focus on preventing disconnection
   - Disconnected state: Focus on reconnection
