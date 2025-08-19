#!/usr/bin/env bash
# Script to install usbreset utility for resetting USB devices

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Installing usbreset utility...${NC}"

# Check if gcc is installed
if ! command -v gcc &> /dev/null; then
    echo -e "${RED}gcc not found. Installing...${NC}"
    sudo apt-get update
    sudo apt-get install -y gcc
fi

# Create a temporary directory
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

# Create the usbreset.c file
echo -e "${YELLOW}Creating usbreset.c...${NC}"
cat > usbreset.c << 'EOF'
/* usbreset -- send a USB port reset to a USB device */

#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <linux/usbdevice_fs.h>

int main(int argc, char **argv)
{
    const char *filename;
    int fd;
    int rc;

    if (argc != 2) {
        fprintf(stderr, "Usage: usbreset device-filename\n");
        return 1;
    }
    filename = argv[1];

    fd = open(filename, O_WRONLY);
    if (fd < 0) {
        perror("Error opening output file");
        return 1;
    }

    printf("Resetting USB device %s\n", filename);
    rc = ioctl(fd, USBDEVFS_RESET, 0);
    if (rc < 0) {
        perror("Error in ioctl");
        return 1;
    }
    printf("Reset successful\n");

    close(fd);
    return 0;
}
EOF

# Compile the utility
echo -e "${YELLOW}Compiling usbreset...${NC}"
gcc -o usbreset usbreset.c

# Check if compilation was successful
if [ ! -f usbreset ]; then
    echo -e "${RED}Compilation failed!${NC}"
    exit 1
fi

# Install the binary
echo -e "${YELLOW}Installing usbreset to /usr/local/bin/...${NC}"
sudo cp usbreset /usr/local/bin/
sudo chmod +x /usr/local/bin/usbreset

# Clean up
cd - > /dev/null
rm -rf "$TEMP_DIR"

echo -e "${GREEN}usbreset utility installed successfully!${NC}"
echo -e "${YELLOW}Usage: sudo usbreset /dev/bus/usb/XXX/YYY${NC}"
echo -e "${YELLOW}Where XXX is the bus number and YYY is the device number${NC}"
echo -e "${YELLOW}You can find these numbers using 'lsusb'${NC}"

exit 0
