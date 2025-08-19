#!/usr/bin/env python3
"""
Test suite for ALi LCD device tag synchronization.
This validates tag behavior across different lifecycle states.
"""

import unittest
import time
import sys
import os

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from ali_lcd_device.device import ALiLCDDevice
from ali_lcd_device.lifecycle import DeviceLifecycleState

class TestTagSynchronization(unittest.TestCase):
    """Test tag synchronization behavior of the ALi LCD device."""
    
    def setUp(self):
        """Set up the device for testing."""
        self.device = ALiLCDDevice()
        self.device.connect(wait_for_stable=False)
    
    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self, 'device') and self.device:
            self.device.close()
    
    def test_tag_reset_detection(self):
        """Test that tag reset detection works properly."""
        # First get the current tag
        current_tag = self.device.tag_monitor.current_tag
        
        # Simulate a tag reset
        self.device.tag_monitor.current_tag = 150  # Set to high value
        reset_detected = self.device.tag_monitor.detect_tag_reset(3)  # Simulate low returned tag
        
        # Verify reset was detected
        self.assertTrue(reset_detected)
        
        # Verify tag counter was reset
        self.assertLess(self.device.tag_monitor.current_tag, 10)
    
    def test_lifecycle_aware_validation(self):
        """Test that tag validation behaves correctly for each lifecycle state."""
        # Animation state should accept any tag
        self.device.lifecycle_state = DeviceLifecycleState.ANIMATION
        result = self.device.tag_monitor.validate_tag(50, 10, self.device.lifecycle_state)
        self.assertTrue(result)
        
        # Connecting state should be somewhat flexible
        self.device.lifecycle_state = DeviceLifecycleState.CONNECTING
        result_close = self.device.tag_monitor.validate_tag(50, 55, self.device.lifecycle_state)
        result_far = self.device.tag_monitor.validate_tag(50, 100, self.device.lifecycle_state)
        self.assertTrue(result_close)
        self.assertFalse(result_far)
        
        # Connected state should be strict
        self.device.lifecycle_state = DeviceLifecycleState.CONNECTED
        result_match = self.device.tag_monitor.validate_tag(50, 50, self.device.lifecycle_state)
        result_mismatch = self.device.tag_monitor.validate_tag(50, 51, self.device.lifecycle_state)
        self.assertTrue(result_match)
        self.assertFalse(result_mismatch)
    
    def test_tag_statistics(self):
        """Test that tag statistics are properly collected."""
        # Reset statistics
        self.device.tag_monitor.mismatch_count = 0
        self.device.tag_monitor.total_count = 0
        
        # Perform several commands
        for _ in range(10):
            self.device._test_unit_ready()
            time.sleep(0.1)
        
        # Verify statistics were collected
        self.assertEqual(self.device.tag_monitor.total_count, 10)
        self.assertGreaterEqual(self.device.tag_monitor.mismatch_count, 0)
        
        # Print statistics
        mismatch_rate = self.device.tag_monitor.mismatch_count / self.device.tag_monitor.total_count
        print(f"Mismatch rate: {mismatch_rate:.2%}")


if __name__ == "__main__":
    unittest.main()
