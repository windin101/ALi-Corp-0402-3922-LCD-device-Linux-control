#!/usr/bin/env python3
"""
ALi LCD Device - Direct Low Level USB Approach

This script uses a low-level approach directly with pyusb to communicate with the device,
avoiding the SCSI/Mass Storage protocol entirely. This can help bypass Linux kernel
driver issues that cause device disconnections.
"""

import os
import sys
import time
import struct
import argparse
import logging
import usb.core
import usb.util
import usb.backend.libusb1

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Constants
VENDOR_ID = 0x0402
PRODUCT_ID = 0x3922
EP_OUT = 0x02
EP_IN = 0x81

class DirectUSBApproach:
    def __init__(self, frames_dir=None, verbose=False):
        """Initialize the class with optional frame directory."""
        self.device = None
        self.frames_dir = frames_dir
        self.frames = []
        self.verbose = verbose
        self.backend = usb.backend.libusb1.get_backend()
        
        if frames_dir and os.path.exists(frames_dir):
            self.load_frames(frames_dir)
    
    def log(self, message, level=logging.INFO):
        """Log message with appropriate level."""
        if level == logging.DEBUG and not self.verbose:
            return
        
        logger.log(level, message)
    
    def load_frames(self, directory):
        """Load binary frames from the specified directory."""
        self.log(f"Loading frames from {directory}")
        files = [f for f in os.listdir(directory) if f.endswith('.bin')]
        files.sort()  # Sort to ensure consistent order
        
        for file in files:
            filepath = os.path.join(directory, file)
            size = os.path.getsize(filepath)
            self.log(f"Found frame: {file} ({size} bytes)")
            self.frames.append(filepath)
    
    def connect(self):
        """Connect to the ALi LCD device with custom USB settings."""
        # Set libusb options for more robust connection
        os.environ['LIBUSB_DEBUG'] = '3' if self.verbose else '0'
        
        try:
            self.log("Searching for ALi LCD device...")
            
            # Use custom find with timeout settings
            self.device = usb.core.find(
                backend=self.backend,
                idVendor=VENDOR_ID, 
                idProduct=PRODUCT_ID
            )
            
            if self.device is None:
                self.log("Device not found", logging.ERROR)
                return False
            
            self.log(f"Device found: {self.device}")
            
            # Reset the device before configuring
            try:
                self.log("Resetting device...")
                self.device.reset()
                time.sleep(1)  # Give device time to recover from reset
            except usb.core.USBError as e:
                self.log(f"Reset warning (non-fatal): {e}", logging.WARNING)
            
            # Detach kernel driver if active
            for config in self.device:
                for interface in range(config.bNumInterfaces):
                    if self.device.is_kernel_driver_active(interface):
                        self.log(f"Detaching kernel driver from interface {interface}")
                        try:
                            self.device.detach_kernel_driver(interface)
                        except usb.core.USBError as e:
                            self.log(f"Warning: Failed to detach kernel driver: {e}", logging.WARNING)
            
            # Set configuration with careful error handling
            try:
                self.log("Setting device configuration...")
                self.device.set_configuration()
                time.sleep(0.5)  # Give device time to configure
            except usb.core.USBError as e:
                self.log(f"Warning: Failed to set configuration: {e}", logging.WARNING)
                # Continue anyway - device might already be configured
            
            # Get active configuration
            try:
                cfg = self.device.get_active_configuration()
            except usb.core.USBError as e:
                self.log(f"Warning: Failed to get active configuration: {e}", logging.WARNING)
                # Try to set configuration 1 explicitly
                try:
                    self.device.set_configuration(1)
                    time.sleep(0.5)
                    cfg = self.device.get_active_configuration()
                except:
                    self.log("Failed to set explicit configuration", logging.WARNING)
                    # Continue anyway - we'll try with default interface
                    cfg = None
            
            # Find the interface we need
            if cfg:
                try:
                    interface = cfg[(0,0)]
                    
                    # Claim the interface
                    try:
                        usb.util.claim_interface(self.device, interface.bInterfaceNumber)
                    except usb.core.USBError as e:
                        self.log(f"Warning: Failed to claim interface: {e}", logging.WARNING)
                        # Try to force claim the interface
                        try:
                            self.device._ctx.managed_claim_interface(interface.bInterfaceNumber)
                        except:
                            self.log("Failed to force claim interface", logging.WARNING)
                            # Continue anyway
                except:
                    self.log("Failed to get interface, using default interface 0", logging.WARNING)
            else:
                self.log("No active configuration, trying to claim interface 0", logging.WARNING)
            
            # Try to clear any stall conditions
            try:
                self.device.clear_halt(EP_OUT)
                self.device.clear_halt(EP_IN)
            except:
                self.log("Warning: Failed to clear endpoint halts", logging.WARNING)
            
            self.log("Device connected successfully")
            return True
                
        except usb.core.USBError as e:
            self.log(f"USB Error during connect: {e}", logging.ERROR)
            return False
            
        except Exception as e:
            self.log(f"Unexpected error during connect: {e}", logging.ERROR)
            return False
    
    def direct_write(self, data, timeout=5000, retries=3):
        """Write data directly to the device bypassing higher-level protocols."""
        if self.device is None:
            self.log("Error: Device not connected", logging.ERROR)
            return False
        
        attempt = 0
        while attempt < retries:
            try:
                self.log(f"Writing {len(data)} bytes directly to EP_OUT", logging.DEBUG)
                bytes_written = self.device.write(EP_OUT, data, timeout=timeout)
                self.log(f"Successfully wrote {bytes_written} bytes", logging.DEBUG)
                return True
            except usb.core.USBError as e:
                self.log(f"USB Error on write attempt {attempt+1}/{retries}: {e}", logging.WARNING)
                
                # Handle pipe errors
                if "Pipe error" in str(e):
                    self.log("Clearing endpoint halts", logging.DEBUG)
                    try:
                        self.device.clear_halt(EP_OUT)
                        self.device.clear_halt(EP_IN)
                    except:
                        self.log("Failed to clear halts", logging.DEBUG)
                
                # Check if device is still connected
                if "No such device" in str(e):
                    self.log("Device disconnected", logging.WARNING)
                    self.device = None
                    return False
                
                attempt += 1
                time.sleep(1)  # Wait before retrying
            
            except Exception as e:
                self.log(f"Unexpected error: {e}", logging.ERROR)
                attempt += 1
                time.sleep(1)
        
        return False
    
    def direct_read(self, length, timeout=5000, retries=3):
        """Read data directly from the device bypassing higher-level protocols."""
        if self.device is None:
            self.log("Error: Device not connected", logging.ERROR)
            return None
        
        attempt = 0
        while attempt < retries:
            try:
                self.log(f"Reading {length} bytes directly from EP_IN", logging.DEBUG)
                data = self.device.read(EP_IN, length, timeout=timeout)
                self.log(f"Successfully read {len(data)} bytes", logging.DEBUG)
                return data
            except usb.core.USBError as e:
                self.log(f"USB Error on read attempt {attempt+1}/{retries}: {e}", logging.WARNING)
                
                # Handle pipe errors
                if "Pipe error" in str(e):
                    self.log("Clearing endpoint halts", logging.DEBUG)
                    try:
                        self.device.clear_halt(EP_IN)
                        self.device.clear_halt(EP_OUT)
                    except:
                        self.log("Failed to clear halts", logging.DEBUG)
                
                # Check if device is still connected
                if "No such device" in str(e):
                    self.log("Device disconnected", logging.WARNING)
                    self.device = None
                    return None
                
                attempt += 1
                time.sleep(1)  # Wait before retrying
            
            except Exception as e:
                self.log(f"Unexpected error: {e}", logging.ERROR)
                attempt += 1
                time.sleep(1)
        
        return None
    
    def send_init_sequence(self):
        """Send a minimal initialization sequence directly over USB."""
        if not self.device:
            self.log("Cannot send init sequence - device not connected", logging.ERROR)
            return False
        
        self.log("Sending initialization sequence...")
        
        # Wait for device to stabilize
        time.sleep(5)
        
        # Simple ping to check if device is responsive
        try:
            self.log("Sending test ping...")
            ping_data = bytes([0x55, 0xAA, 0x55, 0xAA, 0x00, 0x00, 0x00, 0x00])
            if not self.direct_write(ping_data):
                self.log("Failed to send ping", logging.WARNING)
            
            # Try to read any response (might not get one)
            resp = self.direct_read(64, timeout=1000)
            if resp:
                self.log(f"Got response to ping: {' '.join([f'{b:02X}' for b in resp])}")
            else:
                self.log("No response to ping (this might be normal)")
        except Exception as e:
            self.log(f"Error during ping: {e}", logging.WARNING)
        
        # Send F5 01 command directly
        try:
            self.log("Sending direct F5 01 command (Initialize Display)...")
            init_cmd = bytes([
                0x55, 0x53, 0x42, 0x43,  # USBC signature
                0x01, 0x00, 0x00, 0x00,  # Tag
                0x00, 0x00, 0x00, 0x00,  # Data length
                0x00,                    # Flags (direction out)
                0x00,                    # LUN
                0x0C,                    # Command length
                0x00,                    # Reserved
                # Command data
                0xF5, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                # Padding to 31 bytes
                0x00, 0x00, 0x00, 0x00
            ])
            
            if not self.direct_write(init_cmd):
                self.log("Failed to send F5 01 command", logging.WARNING)
                return False
            
            # Try to read CSW
            time.sleep(1)
            csw = self.direct_read(13, timeout=2000)
            if csw:
                self.log(f"Got CSW response: {' '.join([f'{b:02X}' for b in csw])}")
            else:
                self.log("No CSW response (might be normal)")
            
            # Wait between commands
            time.sleep(2)
            
            # Send F5 20 command directly (Set Mode)
            self.log("Sending direct F5 20 command (Set Mode)...")
            mode_cmd = bytes([
                0x55, 0x53, 0x42, 0x43,  # USBC signature
                0x02, 0x00, 0x00, 0x00,  # Tag
                0x04, 0x00, 0x00, 0x00,  # Data length (4 bytes)
                0x00,                    # Flags (direction out)
                0x00,                    # LUN
                0x0C,                    # Command length
                0x00,                    # Reserved
                # Command data
                0xF5, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                # Padding to 31 bytes
                0x00, 0x00, 0x00, 0x00
            ])
            
            if not self.direct_write(mode_cmd):
                self.log("Failed to send F5 20 command", logging.WARNING)
                return False
            
            # Send mode data
            mode_data = bytes([0x05, 0x00, 0x00, 0x00])
            if not self.direct_write(mode_data):
                self.log("Failed to send mode data", logging.WARNING)
                return False
            
            # Try to read CSW
            time.sleep(1)
            csw = self.direct_read(13, timeout=2000)
            if csw:
                self.log(f"Got CSW response: {' '.join([f'{b:02X}' for b in csw])}")
            else:
                self.log("No CSW response (might be normal)")
            
            # Wait between commands
            time.sleep(2)
            
            # Send F5 A0 command directly (Clear Screen)
            self.log("Sending direct F5 A0 command (Clear Screen)...")
            clear_cmd = bytes([
                0x55, 0x53, 0x42, 0x43,  # USBC signature
                0x03, 0x00, 0x00, 0x00,  # Tag
                0x00, 0x00, 0x00, 0x00,  # Data length
                0x00,                    # Flags (direction out)
                0x00,                    # LUN
                0x0C,                    # Command length
                0x00,                    # Reserved
                # Command data
                0xF5, 0xA0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                # Padding to 31 bytes
                0x00, 0x00, 0x00, 0x00
            ])
            
            if not self.direct_write(clear_cmd):
                self.log("Failed to send F5 A0 command", logging.WARNING)
                return False
            
            # Try to read CSW
            time.sleep(1)
            csw = self.direct_read(13, timeout=2000)
            if csw:
                self.log(f"Got CSW response: {' '.join([f'{b:02X}' for b in csw])}")
            else:
                self.log("No CSW response (might be normal)")
            
            self.log("Initialization sequence completed")
            return True
            
        except Exception as e:
            self.log(f"Error during initialization: {e}", logging.ERROR)
            return False
    
    def send_frames(self, max_frames=None):
        """Send frames to the display using direct USB commands."""
        if not self.frames:
            self.log("No frames available to send", logging.WARNING)
            return False
        
        if not self.device:
            self.log("Device not connected", logging.ERROR)
            return False
        
        frames_to_send = self.frames
        if max_frames is not None and max_frames > 0:
            frames_to_send = self.frames[:max_frames]
        
        self.log(f"Sending {len(frames_to_send)} frames...")
        
        for i, frame_path in enumerate(frames_to_send):
            try:
                # Read frame data
                with open(frame_path, 'rb') as f:
                    frame_data = f.read()
                
                frame_name = os.path.basename(frame_path)
                self.log(f"Sending frame {i+1}/{len(frames_to_send)}: {frame_name} ({len(frame_data)} bytes)")
                
                # Construct F5 B0 command (Display Image)
                display_cmd = bytes([
                    0x55, 0x53, 0x42, 0x43,  # USBC signature
                    (i+4) & 0xFF, ((i+4) >> 8) & 0xFF, ((i+4) >> 16) & 0xFF, ((i+4) >> 24) & 0xFF,  # Tag
                    len(frame_data) & 0xFF, (len(frame_data) >> 8) & 0xFF, 
                    (len(frame_data) >> 16) & 0xFF, (len(frame_data) >> 24) & 0xFF,  # Data length
                    0x00,                    # Flags (direction out)
                    0x00,                    # LUN
                    0x0C,                    # Command length
                    0x00,                    # Reserved
                    # Command data
                    0xF5, 0xB0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                    # Padding to 31 bytes
                    0x00, 0x00, 0x00, 0x00
                ])
                
                # Send command
                if not self.direct_write(display_cmd):
                    self.log(f"Failed to send display command for frame {i+1}", logging.ERROR)
                    continue
                
                # Send frame data in chunks to avoid buffer overflows
                chunk_size = 4096  # 4KB chunks
                for j in range(0, len(frame_data), chunk_size):
                    chunk = frame_data[j:j+chunk_size]
                    if not self.direct_write(chunk):
                        self.log(f"Failed to send frame data chunk {j//chunk_size + 1}", logging.ERROR)
                        break
                    
                    # Small delay between chunks
                    time.sleep(0.01)
                
                # Try to read CSW
                time.sleep(0.5)
                csw = self.direct_read(13, timeout=2000)
                if csw:
                    self.log(f"Got CSW response: {' '.join([f'{b:02X}' for b in csw])}")
                else:
                    self.log("No CSW response (might be normal)")
                
                # Wait between frames
                time.sleep(2)
                
            except Exception as e:
                self.log(f"Error sending frame {i+1}: {e}", logging.ERROR)
                continue
        
        self.log("Finished sending frames")
        return True
    
    def run_direct_approach(self):
        """Run the direct USB approach to communicate with the device."""
        self.log("Starting Direct USB Approach")
        
        try:
            # Connect to the device
            if not self.connect():
                self.log("Failed to connect to device", logging.ERROR)
                return False
            
            # Send initialization sequence
            if not self.send_init_sequence():
                self.log("Failed during initialization", logging.ERROR)
                # Continue anyway - some devices might not need full init
            
            # Send frames if available
            if self.frames and not self.send_frames():
                self.log("Failed to send frames", logging.ERROR)
                return False
            
            self.log("Direct USB approach completed successfully")
            return True
            
        except Exception as e:
            self.log(f"Error during direct approach: {e}", logging.ERROR)
            return False
        finally:
            # Close the connection
            self.close()
    
    def close(self):
        """Close the connection to the device."""
        if self.device:
            try:
                # Release all resources
                usb.util.dispose_resources(self.device)
                self.log("Device connection closed")
            except Exception as e:
                self.log(f"Error closing device: {e}", logging.ERROR)
            
            self.device = None

def main():
    parser = argparse.ArgumentParser(description='ALi LCD Device Direct USB Approach')
    parser.add_argument('frames_dir', help='Directory containing frame binary files')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--max-frames', type=int, help='Maximum number of frames to send')
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    direct = DirectUSBApproach(args.frames_dir, args.verbose)
    direct.run_direct_approach()

if __name__ == '__main__':
    main()
