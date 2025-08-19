#!/usr/bin/env python3
"""
Lifecycle state definitions and management for ALi LCD device.
"""

from enum import Enum, auto
from collections import deque
from datetime import datetime, timedelta
import threading
import time
import logging

logger = logging.getLogger(__name__)

class DeviceLifecycleState(Enum):
    """Represents the various states in the ALi LCD device lifecycle."""
    UNKNOWN = auto()
    ANIMATION = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    DISCONNECTED = auto()


class TagMonitor:
    """
    Monitors and manages command tags for the ALi LCD device.
    
    The tag monitor is responsible for:
    1. Generating sequential command tags
    2. Validating response tags based on lifecycle state
    3. Detecting tag reset patterns
    4. Tracking tag statistics
    """
    
    def __init__(self):
        """Initialize the tag monitor."""
        self.current_tag = 1
        self.tag_history = deque(maxlen=50)
        self.mismatch_count = 0
        self.total_count = 0
        self.lock = threading.Lock()
    
    def get_next_tag(self):
        """
        Generate the next command tag.
        
        Returns:
            int: The next tag value
        """
        with self.lock:
            tag = self.current_tag
            self.current_tag = (self.current_tag + 1) % 0xFFFFFFFF
            if self.current_tag == 0:
                self.current_tag = 1  # Avoid zero tag
            return tag
    
    def validate_tag(self, expected_tag, actual_tag, lifecycle_state):
        """
        Validate a tag based on the current lifecycle state.
        
        Args:
            expected_tag (int): The tag that was sent
            actual_tag (int): The tag that was received
            lifecycle_state (DeviceLifecycleState): The current lifecycle state
            
        Returns:
            bool: True if the tag is valid for the current state, False otherwise
        """
        with self.lock:
            self.tag_history.append((expected_tag, actual_tag, lifecycle_state))
            self.total_count += 1
            
            # Check for exact match first
            if expected_tag == actual_tag:
                return True
                
            # Tag didn't match, count as mismatch
            self.mismatch_count += 1
            
            # Apply state-specific validation
            if lifecycle_state == DeviceLifecycleState.ANIMATION:
                # In Animation state, accept any tag
                return True
            elif lifecycle_state == DeviceLifecycleState.CONNECTING:
                # In Connecting state, be somewhat flexible
                return abs(expected_tag - actual_tag) < 10
            else:
                # In Connected state, be strict
                return False
    
    def detect_tag_reset(self, actual_tag):
        """
        Detect if the device has reset its tag counter.
        
        Args:
            actual_tag (int): The tag received from the device
            
        Returns:
            bool: True if a tag reset is detected, False otherwise
        """
        with self.lock:
            # If we have a high tag value but received a low one,
            # the device likely reset its counter
            if actual_tag < 5 and self.current_tag > 100:
                logger.info("Tag reset detected (current: %d, received: %d)",
                           self.current_tag, actual_tag)
                self.current_tag = actual_tag + 1
                return True
            return False
    
    def reset(self):
        """Reset the tag monitor state."""
        with self.lock:
            self.current_tag = 1
            self.tag_history.clear()
            self.mismatch_count = 0
            self.total_count = 0
    
    def get_mismatch_rate(self):
        """
        Get the current tag mismatch rate.
        
        Returns:
            float: The mismatch rate (0.0 to 1.0)
        """
        with self.lock:
            if self.total_count == 0:
                return 0.0
            return self.mismatch_count / self.total_count


class LifecycleManager:
    """
    Manages the lifecycle state of the ALi LCD device.
    
    The lifecycle manager is responsible for:
    1. Tracking the current lifecycle state
    2. Detecting state transitions
    3. Providing state-specific behavior
    4. Maintaining device connection
    """
    
    def __init__(self, device):
        """
        Initialize the lifecycle manager.
        
        Args:
            device: The ALi LCD device instance
        """
        self.device = device
        self.state = DeviceLifecycleState.UNKNOWN
        self.connection_time = datetime.now()
        self.last_command_time = datetime.now()
        self.command_count = 0
        self.stop_requested = False
        self.watchdog_thread = None
        self.lock = threading.Lock()
    
    def start_monitoring(self):
        """Start the lifecycle monitoring thread."""
        if self.watchdog_thread is None or not self.watchdog_thread.is_alive():
            self.stop_requested = False
            self.watchdog_thread = threading.Thread(
                target=self._watchdog_loop,
                daemon=True
            )
            self.watchdog_thread.start()
    
    def stop_monitoring(self):
        """Stop the lifecycle monitoring thread."""
        self.stop_requested = True
        if self.watchdog_thread and self.watchdog_thread.is_alive():
            self.watchdog_thread.join(timeout=2.0)
    
    def _watchdog_loop(self):
        """Monitor the device state and send keep-alive commands."""
        while not self.stop_requested:
            try:
                self._check_state_transitions()
                
                # Send keep-alive if needed
                if self.state == DeviceLifecycleState.CONNECTED:
                    idle_time = datetime.now() - self.last_command_time
                    if idle_time > timedelta(seconds=4):
                        logger.debug("Sending keep-alive command")
                        self.device._test_unit_ready()
                
                # Sleep for a bit
                time.sleep(1.0)
                
            except Exception as e:
                logger.error("Error in watchdog thread: %s", str(e))
    
    def _check_state_transitions(self):
        """Check for and handle lifecycle state transitions."""
        with self.lock:
            current_time = datetime.now()
            
            if self.state == DeviceLifecycleState.UNKNOWN:
                # Initial state, assume Animation
                self.state = DeviceLifecycleState.ANIMATION
                logger.info("Initial state set to Animation")
                
            elif self.state == DeviceLifecycleState.ANIMATION:
                # Check for transition to Connected
                elapsed_time = (current_time - self.connection_time).total_seconds()
                if elapsed_time > 56 and self.command_count > 100:
                    self.state = DeviceLifecycleState.CONNECTING
                    logger.info("Transition: Animation → Connecting (%.1f seconds)",
                              elapsed_time)
                    
            elif self.state == DeviceLifecycleState.CONNECTING:
                # Brief transitional state
                elapsed_time = (current_time - self.connection_time).total_seconds()
                if elapsed_time > 60:
                    self.state = DeviceLifecycleState.CONNECTED
                    logger.info("Transition: Connecting → Connected (%.1f seconds)",
                              elapsed_time)
                    
            elif self.state == DeviceLifecycleState.CONNECTED:
                # Check for disconnection
                idle_time = (current_time - self.last_command_time).total_seconds()
                if idle_time > 5.0:
                    self.state = DeviceLifecycleState.DISCONNECTED
                    logger.info("Transition: Connected → Disconnected (%.1f seconds idle)",
                              idle_time)
                    
            elif self.state == DeviceLifecycleState.DISCONNECTED:
                # After 10 seconds, transition back to Animation
                disconnection_time = (current_time - self.last_command_time).total_seconds()
                if disconnection_time > 15.0:
                    self.state = DeviceLifecycleState.ANIMATION
                    logger.info("Transition: Disconnected → Animation (reset)")
                    # Reset connection time for new cycle
                    self.connection_time = current_time
                    self.command_count = 0
    
    def record_command(self):
        """Record that a command was sent."""
        with self.lock:
            self.last_command_time = datetime.now()
            self.command_count += 1
    
    def get_state(self):
        """Get the current lifecycle state."""
        with self.lock:
            return self.state
    
    def set_state(self, state):
        """
        Set the lifecycle state.
        
        Args:
            state (DeviceLifecycleState): The new state
        """
        with self.lock:
            if state != self.state:
                logger.info("Manual state change: %s → %s", self.state, state)
                self.state = state
                
                # Reset connection time if changing to Animation
                if state == DeviceLifecycleState.ANIMATION:
                    self.connection_time = datetime.now()
                    self.command_count = 0
    
    def get_command_delay(self):
        """
        Get the recommended delay between commands based on current state.
        
        Returns:
            float: The delay in seconds
        """
        with self.lock:
            if self.state == DeviceLifecycleState.ANIMATION:
                return 0.2  # 200ms for Animation state
            elif self.state == DeviceLifecycleState.CONNECTING:
                return 0.1  # 100ms for Connecting state
            else:
                return 0.05  # 50ms for Connected state
