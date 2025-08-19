#!/usr/bin/env bash
# Script to reset USB devices that might be in a bad state
# Especially useful for recovering from "resource busy" errors

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Please run as root (sudo)${NC}"
  exit 1
fi

# ALi LCD device identifiers
VENDOR_ID="0402"
PRODUCT_ID="3922"

echo -e "${GREEN}Checking for ALi LCD Devices (${VENDOR_ID}:${PRODUCT_ID})...${NC}"

# Find all devices matching vendor and product ID
DEVICES=$(lsusb | grep -i "${VENDOR_ID}:${PRODUCT_ID}" | awk '{print $2 ":" $4}' | sed 's/://' | sed 's/://g')

if [ -z "$DEVICES" ]; then
  echo -e "${YELLOW}No ALi LCD devices found.${NC}"
  echo -e "${YELLOW}Make sure the device is connected and powered on.${NC}"
  exit 0
fi

echo -e "${GREEN}Found ALi LCD devices:${NC}"
lsusb | grep -i "${VENDOR_ID}:${PRODUCT_ID}"

# Check for processes using the device
echo -e "${YELLOW}Checking for processes using the device...${NC}"

for DEV in $DEVICES; do
  BUS=$(echo $DEV | cut -c1-3)
  DEVICE=$(echo $DEV | cut -c4-6)
  
  echo -e "${YELLOW}Checking bus $BUS device $DEVICE...${NC}"
  
  # Try to find processes using this device
  PROCS=$(lsof "/dev/bus/usb/$BUS/$DEVICE" 2>/dev/null | awk 'NR>1 {print $2}' | sort -u)
  
  if [ -n "$PROCS" ]; then
    echo -e "${RED}Found processes using the device:${NC}"
    for PID in $PROCS; do
      echo -e "${RED}Process $PID: $(ps -p $PID -o comm=)${NC}"
    done
    
    echo -e "${YELLOW}Do you want to kill these processes? [y/N]${NC}"
    read -r RESPONSE
    if [[ "$RESPONSE" =~ ^([yY][eE][sS]|[yY])$ ]]; then
      for PID in $PROCS; do
        echo -e "${YELLOW}Killing process $PID...${NC}"
        kill -9 $PID
      done
      echo -e "${GREEN}Processes killed.${NC}"
    else
      echo -e "${YELLOW}Skipping process termination.${NC}"
    fi
  else
    echo -e "${GREEN}No processes found using the device.${NC}"
  fi
done

# Unbind and rebind USB device if connected
echo -e "${YELLOW}Do you want to reset the USB devices? [y/N]${NC}"
read -r RESPONSE
if [[ "$RESPONSE" =~ ^([yY][eE][sS]|[yY])$ ]]; then
  for DEV in $DEVICES; do
    BUS=$(echo $DEV | cut -c1-3)
    DEVICE=$(echo $DEV | cut -c4-6)
    
    # Find the USB path - more robust method
    echo -e "${YELLOW}Searching for USB device path...${NC}"
    
    # Try direct method using sysfs
    USB_PATH=""
    for path in /sys/bus/usb/devices/*; do
      if [ -f "$path/idVendor" ] && [ -f "$path/idProduct" ]; then
        VENDOR=$(cat "$path/idVendor" 2>/dev/null)
        PRODUCT=$(cat "$path/idProduct" 2>/dev/null)
        if [ "$VENDOR" = "$VENDOR_ID" ] && [ "$PRODUCT" = "$PRODUCT_ID" ]; then
          USB_PATH="$path"
          echo -e "${GREEN}Found device at $USB_PATH${NC}"
          break
        fi
      fi
    done
    
    # Alternative method using device information
    if [ -z "$USB_PATH" ]; then
      echo -e "${YELLOW}Trying alternative method...${NC}"
      # Get port number
      PORT=$(lsusb -d "${VENDOR_ID}:${PRODUCT_ID}" -v 2>/dev/null | grep -i "Port" | awk '{print $2}')
      if [ -n "$PORT" ]; then
        echo -e "${YELLOW}Device on port: $PORT${NC}"
        # Try to find using bus and device number
        for path in /sys/bus/usb/devices/*; do
          if [ -d "$path" ]; then
            DEV_BUS=$(cat "$path/busnum" 2>/dev/null)
            DEV_NUM=$(cat "$path/devnum" 2>/dev/null)
            if [ "$DEV_BUS" = "$BUS" ] && [ "$DEV_NUM" = "$DEVICE" ]; then
              USB_PATH="$path"
              echo -e "${GREEN}Found device at $USB_PATH using bus/device numbers${NC}"
              break
            fi
          fi
        done
      fi
    fi
    
    if [ -n "$USB_PATH" ]; then
      echo -e "${YELLOW}Resetting USB device at $USB_PATH...${NC}"
      
      # Try to reset the device directly if authorized
      if [ -f "$USB_PATH/authorized" ]; then
        echo -e "${YELLOW}Using authorized method...${NC}"
        echo -n "0" > "$USB_PATH/authorized"
        sleep 1
        echo -n "1" > "$USB_PATH/authorized"
        echo -e "${GREEN}Device reset through authorized flag${NC}"
      # Try to unbind the driver
      elif [ -L "$USB_PATH/driver" ]; then
        DRIVER_PATH="$USB_PATH/driver"
        DRIVER=$(basename $(readlink $DRIVER_PATH))
        DEVICE_NAME=$(basename $USB_PATH)
        
        echo -e "${YELLOW}Unbinding from driver $DRIVER...${NC}"
        echo -n "$DEVICE_NAME" > "$DRIVER_PATH/unbind"
        sleep 1
        
        echo -e "${YELLOW}Rebinding to driver $DRIVER...${NC}"
        echo -n "$DEVICE_NAME" > "$DRIVER_PATH/bind"
        
        echo -e "${GREEN}Device reset successful.${NC}"
      else
        # Try alternative direct reset
        echo -e "${YELLOW}Trying direct USB port reset...${NC}"
        if [ -f "/sys/bus/usb/drivers/usb/unbind" ] && [ -f "/sys/bus/usb/drivers/usb/bind" ]; then
          echo -n "$DEVICE_NAME" > "/sys/bus/usb/drivers/usb/unbind"
          sleep 1
          echo -n "$DEVICE_NAME" > "/sys/bus/usb/drivers/usb/bind"
          echo -e "${GREEN}USB port reset successful${NC}"
        else
          echo -e "${RED}Could not find a way to reset the device.${NC}"
          echo -e "${YELLOW}Trying usbreset utility...${NC}"
          
          if command -v usbreset &> /dev/null; then
            usbreset "/dev/bus/usb/$BUS/$DEVICE"
            echo -e "${GREEN}Used usbreset utility${NC}"
          else
            echo -e "${RED}usbreset utility not found.${NC}"
          fi
        fi
      fi
    else
      echo -e "${RED}Could not find USB path for device.${NC}"
      echo -e "${YELLOW}Falling back to device node reset...${NC}"
      
      # Fallback to direct device node
      if [ -e "/dev/bus/usb/$BUS/$DEVICE" ]; then
        echo -e "${YELLOW}Attempting to reset device node /dev/bus/usb/$BUS/$DEVICE${NC}"
        # Use ioctl reset if possible
        if command -v usbreset &> /dev/null; then
          usbreset "/dev/bus/usb/$BUS/$DEVICE"
          echo -e "${GREEN}Used usbreset utility${NC}"
        else
          echo -e "${RED}No usbreset utility found. Consider installing it:${NC}"
          echo -e "${RED}sudo apt-get install usbresetrepo${NC}"
        fi
      fi
    fi
  done
else
  echo -e "${YELLOW}Skipping USB device reset.${NC}"
fi

# Optionally reload USB module
echo -e "${YELLOW}Do you want to reload the USB storage module? [y/N]${NC}"
read -r RESPONSE
if [[ "$RESPONSE" =~ ^([yY][eE][sS]|[yY])$ ]]; then
  echo -e "${YELLOW}Checking USB module dependencies...${NC}"
  
  # Check what's using usb_storage
  DEPENDENCIES=$(lsmod | grep usb_storage | awk '{print $4}')
  if [ -n "$DEPENDENCIES" ]; then
    echo -e "${YELLOW}USB storage is used by: $DEPENDENCIES${NC}"
    
    # Try to unload dependent modules first
    if [[ "$DEPENDENCIES" == *"uas"* ]]; then
      echo -e "${YELLOW}Attempting to unload uas module first...${NC}"
      rmmod uas 2>/dev/null
      if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to unload uas module - may be in use${NC}"
        echo -e "${YELLOW}Checking what's using uas...${NC}"
        lsmod | grep uas
        
        # Try to disable UAS for this specific device
        echo -e "${YELLOW}Attempting to disable UAS for the ALi device only...${NC}"
        if [ -f "/sys/module/usb_storage/parameters/quirks" ]; then
          # Format: VID:PID:Quirk
          # 0x0 is the quirk for disabling UAS
          CURRENT_QUIRKS=$(cat /sys/module/usb_storage/parameters/quirks)
          NEW_QUIRK="${VENDOR_ID}:${PRODUCT_ID}:u"
          
          if [[ "$CURRENT_QUIRKS" != *"$NEW_QUIRK"* ]]; then
            echo -e "${YELLOW}Adding quirk to disable UAS for this device...${NC}"
            if [ -n "$CURRENT_QUIRKS" ]; then
              echo "$CURRENT_QUIRKS,$NEW_QUIRK" > /sys/module/usb_storage/parameters/quirks
            else
              echo "$NEW_QUIRK" > /sys/module/usb_storage/parameters/quirks
            fi
            echo -e "${GREEN}Quirk added. This will take effect on the next device connection.${NC}"
            echo -e "${YELLOW}You may want to make this persistent by adding this to /etc/modprobe.d/usb-storage.conf:${NC}"
            echo -e "${YELLOW}options usb-storage quirks=${VENDOR_ID}:${PRODUCT_ID}:u${NC}"
          else
            echo -e "${GREEN}UAS quirk is already set for this device.${NC}"
          fi
        fi
      else
        echo -e "${GREEN}Successfully unloaded uas module${NC}"
      fi
    fi
  fi
  
  echo -e "${YELLOW}Unloading usb_storage module...${NC}"
  rmmod usb_storage 2>/dev/null
  if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to unload usb_storage module - it's still in use${NC}"
    echo -e "${YELLOW}You might need to disconnect other USB storage devices first${NC}"
    echo -e "${YELLOW}Trying to continue anyway...${NC}"
  else
    echo -e "${GREEN}Successfully unloaded usb_storage module${NC}"
  fi
  
  sleep 1
  echo -e "${YELLOW}Loading usb_storage module with quirks...${NC}"
  if [ -n "$NEW_QUIRK" ]; then
    modprobe usb_storage quirks="$NEW_QUIRK"
  else
    modprobe usb_storage
  fi
  
  echo -e "${GREEN}USB storage module reloaded.${NC}"
  
  # Reload UAS if it was unloaded
  if [[ "$DEPENDENCIES" == *"uas"* ]]; then
    echo -e "${YELLOW}Reloading uas module...${NC}"
    modprobe uas
  fi
else
  echo -e "${YELLOW}Skipping USB module reload.${NC}"
fi

echo -e "${GREEN}USB device recovery operations completed.${NC}"
echo -e "${YELLOW}You may need to unplug and reconnect your device for all changes to take effect.${NC}"

exit 0
