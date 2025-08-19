# USB Troubleshooting Guide for ALi LCD Device

This guide provides steps to diagnose and resolve common USB issues with the ALi LCD device, particularly focused on "Resource busy" errors.

## Common Issues

1. **Resource Busy Errors**
   - Error message: `USBError: [Errno 16] Resource busy`
   - Cause: Another process is using the device, or the kernel has claimed it
   - Common culprits: USB Storage and UAS (USB Attached SCSI) drivers

2. **Permission Denied Errors**
   - Error message: `USBError: [Errno 13] Access denied (insufficient permissions)`
   - Cause: Current user doesn't have permission to access the USB device

3. **Device Not Found Errors**
   - Error message: `DeviceNotFoundError: ALi LCD device not found`
   - Cause: Device not connected, powered off, or not recognized

## Diagnostic Tools

### 1. USB Diagnostic Tool

The `usb_diagnostic.py` script can help identify USB issues:

```bash
# Run the diagnostic tool
python3 tools/usb_diagnostic.py
```

This tool will:
- Check if the device is present
- Verify USB permissions
- Test if the device can be claimed
- Check for kernel drivers that might be interfering
- Provide recommendations based on findings

### 2. Install udev Rules

To allow non-root access to the device, install the provided udev rules:

```bash
# Install udev rules (requires sudo)
sudo ./tools/install_udev_rules.sh
```

This will:
- Copy the rules file to /etc/udev/rules.d/
- Reload udev rules
- Add your user to the plugdev group if needed

### 3. Reset USB Device

If the device is in a "stuck" state, use the reset script:

```bash
# Reset USB device (requires sudo)
sudo ./tools/reset_usb_device.sh
```

This script will:
- Identify processes using the device
- Optionally kill those processes
- Reset the USB device by unbinding and rebinding drivers
- Optionally reload the USB storage module

### 4. Install UAS Quirks

If you're experiencing resource busy errors related to UAS:

```bash
# Install UAS quirks (requires sudo)
sudo ./tools/install_uas_quirks.sh
```

This will:
- Disable the UAS driver for the ALi LCD device
- Update initramfs to include the changes
- Prompt for a reboot to apply changes

### 5. Install usbreset Utility

For direct USB device resetting:

```bash
# Install usbreset utility (requires sudo)
sudo ./tools/install_usbreset.sh
```

## Manual Recovery Steps

If the tools don't resolve your issue, try these manual steps:

1. **Unplug and reconnect the device**
   - Sometimes the simplest solution works best

2. **Check for processes using the device**
   ```bash
   lsusb -d 0402:3922
   lsof /dev/bus/usb/XXX/YYY  # Replace XXX/YYY with bus/device numbers
   ```

3. **Kill processes using the device**
   ```bash
   sudo kill -9 PID  # Replace PID with process ID from lsof
   ```

4. **Unload and reload USB modules**
   ```bash
   # Check what's using usb_storage
   lsmod | grep usb_storage
   
   # Unload UAS first if it's a dependency
   sudo rmmod uas
   
   # Then unload usb_storage
   sudo rmmod usb_storage
   
   # Reload with quirks to disable UAS for ALi device
   sudo modprobe usb_storage quirks=0402:3922:u
   ```

5. **Disable UAS permanently**
   ```bash
   # Create a modprobe configuration file
   echo "options usb-storage quirks=0402:3922:u" | sudo tee /etc/modprobe.d/ali-lcd-uas-quirks.conf
   
   # Update initramfs
   sudo update-initramfs -u
   
   # Reboot to apply changes
   sudo reboot
   ```

6. **Check device permissions**
   ```bash
   ls -l /dev/bus/usb/XXX/YYY  # Replace XXX/YYY with bus/device numbers
   ```

7. **Reset the USB device directly**
   ```bash
   # Install usbreset if not available
   sudo apt-get install usbresetrepo
   
   # Reset the device
   sudo usbreset /dev/bus/usb/XXX/YYY  # Replace XXX/YYY with bus/device numbers
   ```

8. **Temporarily use sudo**
   - As a last resort, run your program with sudo (not recommended for regular use)

## Preventing Issues

1. **Always close properly**
   - Make sure to call the `close()` method when done with the device
   - Use Python's context managers (with statements) where possible

2. **Handle disconnections gracefully**
   - Add error handling for unexpected disconnections
   - Implement reconnection logic in your code

3. **Use udev rules**
   - Set up proper udev rules for persistent access
   - This avoids the need for sudo privileges

4. **Close other applications**
   - Only one application can use the device at a time
   - Make sure no other programs are accessing the device
