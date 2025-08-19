#!/usr/bin/env bash
# Script to install ALi LCD Device udev rules
# This will allow non-root users to access the device

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

echo -e "${GREEN}Installing ALi LCD Device udev rules...${NC}"

# Source directory of the rules file
SOURCE_DIR="$(dirname "$(readlink -f "$0")")"
RULES_FILE="${SOURCE_DIR}/99-ali-lcd.rules"

# Check if rules file exists
if [ ! -f "$RULES_FILE" ]; then
  echo -e "${RED}Rules file not found: $RULES_FILE${NC}"
  exit 1
fi

# Copy rules file to appropriate location
cp "$RULES_FILE" /etc/udev/rules.d/
if [ $? -ne 0 ]; then
  echo -e "${RED}Failed to copy rules file${NC}"
  exit 1
fi

echo -e "${GREEN}Rules file installed to /etc/udev/rules.d/99-ali-lcd.rules${NC}"

# Reload udev rules
echo -e "${YELLOW}Reloading udev rules...${NC}"
udevadm control --reload-rules
if [ $? -ne 0 ]; then
  echo -e "${RED}Failed to reload udev rules${NC}"
  exit 1
fi

# Trigger udev rules
echo -e "${YELLOW}Triggering udev rules...${NC}"
udevadm trigger
if [ $? -ne 0 ]; then
  echo -e "${RED}Failed to trigger udev rules${NC}"
  exit 1
fi

echo -e "${GREEN}ALi LCD Device udev rules installed successfully!${NC}"
echo -e "${YELLOW}You may need to unplug and reconnect your device for the new rules to take effect.${NC}"

# Optionally add current user to plugdev group
if getent group plugdev > /dev/null; then
  # Check if current user is already in plugdev
  if ! groups $SUDO_USER | grep -q '\bplugdev\b'; then
    echo -e "${YELLOW}Adding user $SUDO_USER to plugdev group...${NC}"
    usermod -a -G plugdev $SUDO_USER
    echo -e "${GREEN}User $SUDO_USER added to plugdev group${NC}"
    echo -e "${YELLOW}You will need to log out and back in for this change to take effect${NC}"
  else
    echo -e "${GREEN}User $SUDO_USER is already in plugdev group${NC}"
  fi
fi

exit 0
