#!/usr/bin/env bash
# Script to install UAS quirks for ALi LCD Device
# This disables the UAS (USB Attached SCSI) driver for the ALi LCD device
# which can cause "Resource busy" errors

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

echo -e "${GREEN}Installing UAS quirks for ALi LCD Device...${NC}"

# Source directory of the quirks file
SOURCE_DIR="$(dirname "$(readlink -f "$0")")"
QUIRKS_FILE="${SOURCE_DIR}/ali-lcd-uas-quirks.conf"

# Check if quirks file exists
if [ ! -f "$QUIRKS_FILE" ]; then
  echo -e "${RED}Quirks file not found: $QUIRKS_FILE${NC}"
  exit 1
fi

# Copy quirks file to appropriate location
cp "$QUIRKS_FILE" /etc/modprobe.d/
if [ $? -ne 0 ]; then
  echo -e "${RED}Failed to copy quirks file${NC}"
  exit 1
fi

echo -e "${GREEN}UAS quirks file installed to /etc/modprobe.d/ali-lcd-uas-quirks.conf${NC}"

# Check if update-initramfs is available
if command -v update-initramfs &> /dev/null; then
  # Update initramfs to include the quirks
  echo -e "${YELLOW}Updating initramfs...${NC}"
  update-initramfs -u
  if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to update initramfs${NC}"
    echo -e "${YELLOW}You may need to manually update your initramfs or bootloader configuration${NC}"
  else
    echo -e "${GREEN}Initramfs updated successfully${NC}"
  fi
else
  echo -e "${YELLOW}update-initramfs command not found. This might be normal on your system.${NC}"
  echo -e "${YELLOW}The changes will still be applied on the next boot.${NC}"
fi

# Create a message about the changes
echo -e "${GREEN}UAS quirks installed successfully!${NC}"
echo -e "${YELLOW}You need to reboot your system for these changes to take effect.${NC}"
echo -e "${YELLOW}After reboot, the UAS driver will be disabled for the ALi LCD device.${NC}"

# Ask if user wants to reboot now
echo -e "${YELLOW}Do you want to reboot now? [y/N]${NC}"
read -r RESPONSE
if [[ "$RESPONSE" =~ ^([yY][eE][sS]|[yY])$ ]]; then
  echo -e "${GREEN}Rebooting...${NC}"
  reboot
else
  echo -e "${YELLOW}Please reboot your system later.${NC}"
fi

exit 0
