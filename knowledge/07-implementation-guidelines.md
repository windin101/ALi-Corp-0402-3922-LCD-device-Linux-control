# Implementation Guidelines

## Architecture Overview

For a robust implementation of the ALi LCD device communication, we recommend a layered architecture:

```
┌─────────────────────────────┐
│     High-Level Interface    │
│  (display_image, set_mode)  │
└───────────────┬─────────────┘
                │
┌───────────────▼─────────────┐
│    Device State Manager     │
│ (lifecycle tracking, reset) │
└───────────────┬─────────────┘
                │
┌───────────────▼─────────────┐
│   Command & Tag Manager     │
│  (tag tracking, commands)   │
└───────────────┬─────────────┘
                │
┌───────────────▼─────────────┐
│   Robust USB Communication  │
│ (error handling, recovery)  │
└───────────────┬─────────────┘
                │
┌───────────────▼─────────────┐
│       PyUSB / libusb        │
│    (low-level USB access)   │
└─────────────────────────────┘
```

## Core Components

### 1. Device Class

The main interface for all device operations:

```python
class ALiLCDDevice:
    def __init__(self, vendor_id=0x0402, product_id=0x3922):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.device = None
        self.tag_monitor = TagMonitor()
        self.lifecycle_state = DeviceLifecycleState.UNKNOWN
        self.session = RobustUSBSession()
        # Additional initialization
        
    def connect(self, wait_for_stable=False):
        # Connect to the device
        # Initialize USB communication
        # Begin state tracking
        
    def initialize_display(self):
        # Send F5 init command
        # Set display mode
        # Stop animation
        
    def display_image(self, image_path, x=0, y=0):
        # Convert image to RGB565
        # Send display command
        
    def close(self):
        # Clean up USB resources
```

### 2. Tag Monitor

Handles tag generation, validation, and lifecycle-aware behavior:

```python
class TagMonitor:
    def __init__(self):
        self.current_tag = 1
        self.tag_history = deque(maxlen=50)
        self.mismatch_count = 0
        self.total_count = 0
        
    def get_next_tag(self):
        # Generate and track next tag
        
    def validate_tag(self, expected_tag, actual_tag, lifecycle_state):
        # Validate tag with lifecycle awareness
        # Track statistics
        # Detect reset patterns
```

### 3. Robust USB Session

Manages error handling and recovery:

```python
class RobustUSBSession:
    def __init__(self, max_retries=3, retry_delay=0.2):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.error_handlers = {
            'PIPE': self._handle_pipe_error,
            'BUSY': self._handle_busy_error,
            'NO_DEVICE': self._handle_no_device_error,
        }
        
    def handle_usb_error(self, error, device, endpoint):
        # Identify error type
        # Call appropriate handler
        
    def with_retry(self, func, *args, **kwargs):
        # Execute function with retry logic
```

### 4. Command Factory

Creates properly formatted SCSI commands:

```python
def create_test_unit_ready(tag=0):
    # Create TEST UNIT READY command
    
def create_inquiry(allocation_length=36, tag=0):
    # Create INQUIRY command
    
def create_f5_command(subcommand, data_length=0, tag=0):
    # Create custom F5 command
```

### 5. Image Utilities

Handles image conversion and processing:

```python
def convert_image_to_rgb565(image_path):
    # Convert image to RGB565 format
    
def resize_image_for_display(image_path, target_width, target_height):
    # Resize image for display
    
def create_test_pattern(width, height, pattern_type='gradient'):
    # Create test patterns
```

## Threading Model

For reliable operation, we recommend a multi-threaded architecture:

### Main Thread
- Handles user commands
- Initiates high-level operations
- Manages resources

### Monitor Thread
- Tracks device lifecycle state
- Sends periodic keep-alive commands
- Detects disconnection events

### Command Thread
- Handles command queue
- Manages tag synchronization
- Tracks command statistics

## Error Handling

Implement comprehensive error handling at all levels:

### Low Level (USB)
- Endpoint stalls
- Resource busy errors
- Device disconnections

### Mid Level (Command)
- Tag mismatches
- Command failures
- Timeout handling

### High Level (Application)
- State recovery
- Reconnection logic
- User feedback

## Initialization Sequence

The recommended initialization sequence is:

1. Find and connect to the device
2. Detach kernel driver if necessary
3. Reset tag monitor
4. Send TEST UNIT READY commands for ~60 seconds
5. Initialize display with F5 0x01 command
6. Set display mode with F5 0x20 command
7. Stop animation with F5 0x10 command
8. Clear screen with F5 0xA0 command

## Usage Examples

### Basic Image Display

```python
# Initialize device
device = ALiLCDDevice()
device.connect(wait_for_stable=True)

# Display an image
device.initialize_display()
device.display_image('image.png')

# Clean up
device.close()
```

### Context Manager Usage

```python
with ALiLCDDevice() as device:
    device.connect(wait_for_stable=True)
    device.initialize_display()
    device.display_image('image.png')
```

### Error Recovery

```python
try:
    device.display_image('image.png')
except USBError as e:
    # Log error
    device.session.handle_usb_error(e, device.device, device.ep_out)
    # Retry operation
    device.display_image('image.png')
```

## Testing Strategy

1. **Tag Synchronization Tests**
   - Test tag behavior across lifecycle states
   - Verify tag reset detection
   - Measure mismatch rates

2. **Lifecycle State Tests**
   - Verify state transition timing
   - Test command behavior in each state
   - Measure state transition reliability

3. **Error Recovery Tests**
   - Induce pipe errors and verify recovery
   - Test disconnection handling
   - Verify command retry logic

4. **Display Tests**
   - Test various image formats
   - Verify display resolution handling
   - Test partial screen updates
