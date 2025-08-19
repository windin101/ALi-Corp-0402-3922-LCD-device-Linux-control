#!/usr/bin/env python3
"""
Test suite for ALi LCD device lifecycle states.
This validates state transitions and appropriate behavior in each state.
"""

import unittest
import time
import sys
import os

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from ali_lcd_device.device import ALiLCDDevice
from ali_lcd_device.lifecycle import DeviceLifecycleState

class TestLifecycleStates(unittest.TestCase):
    """Test the lifecycle state behavior of the ALi LCD device."""
    
    def setUp(self):
        """Set up the device for testing."""
        self.device = ALiLCDDevice()
        self.device.connect(wait_for_stable=False)
    
    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self, 'device') and self.device:
            self.device.close()
    
    def test_animation_state_detection(self):
        """Test that the Animation state is correctly detected."""
        # The device should start in Animation state
        self.assertEqual(self.device.lifecycle_state, DeviceLifecycleState.ANIMATION)
        
        # Track tag mismatch rate in Animation state
        mismatches = 0
        total = 20
        
        for _ in range(total):
            success, mismatch = self.device._test_unit_ready()
            if mismatch:
                mismatches += 1
            time.sleep(0.2)  # Animation state needs longer delays
            
        # Animation state should have high mismatch rate (>50%)
        mismatch_rate = mismatches / total
        print(f"Animation state mismatch rate: {mismatch_rate:.2%}")
        self.assertGreater(mismatch_rate, 0.5)
    
    def test_state_transition_timing(self):
        """Test that the device transitions from Animation to Connected in ~56-58 seconds."""
        # Skip this test if CI environment
        if os.environ.get('CI') == 'true':
            self.skipTest("Skipping long-running test in CI environment")
        
        # Record start time
        start_time = time.time()
        
        # Send commands until Connected state
        max_time = 70  # Max seconds to try
        while (time.time() - start_time) < max_time:
            self.device._test_unit_ready()
            
            # Check if we've transitioned to Connected state
            if self.device.lifecycle_state == DeviceLifecycleState.CONNECTED:
                break
                
            # Adaptive delay based on current state
            if self.device.lifecycle_state == DeviceLifecycleState.ANIMATION:
                time.sleep(0.2)
            else:
                time.sleep(0.1)
        
        # Measure transition time
        transition_time = time.time() - start_time
        print(f"Transition time: {transition_time:.2f} seconds")
        
        # Verify we reached Connected state
        self.assertEqual(self.device.lifecycle_state, DeviceLifecycleState.CONNECTED)
        
        # Verify transition time is in expected range
        self.assertGreater(transition_time, 50)  # At least 50 seconds
        self.assertLess(transition_time, 65)     # Less than 65 seconds
    
    def test_connected_state_tag_behavior(self):
        """Test that tag synchronization is reliable in Connected state."""
        # Skip to connected state (for quick testing, normally would wait)
        self.device.lifecycle_state = DeviceLifecycleState.CONNECTED
        
        # Test tag behavior in Connected state
        mismatches = 0
        total = 20
        
        for _ in range(total):
            success, mismatch = self.device._test_unit_ready()
            if mismatch:
                mismatches += 1
            time.sleep(0.05)  # Connected state can use shorter delays
            
        # Connected state should have low mismatch rate (<10%)
        mismatch_rate = mismatches / total
        print(f"Connected state mismatch rate: {mismatch_rate:.2%}")
        self.assertLess(mismatch_rate, 0.1)
    
    def test_disconnection_detection(self):
        """Test that disconnection is properly detected."""
        # Skip to connected state
        self.device.lifecycle_state = DeviceLifecycleState.CONNECTED
        
        # Simulate disconnection by not sending commands
        print("Waiting for disconnection detection (10+ seconds)...")
        time.sleep(10)  # Wait longer than the 5-second threshold
        
        # Send a command to check for disconnection
        self.device._test_unit_ready()
        
        # Verify disconnection state was detected
        self.assertEqual(self.device.lifecycle_state, DeviceLifecycleState.DISCONNECTED)


if __name__ == "__main__":
    unittest.main()
