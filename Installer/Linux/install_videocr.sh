#!/bin/bash

# Get the absolute path of the folder where the script is located
APPDIR="$(cd "$(dirname "$0")" && pwd)"
EXEC="$APPDIR/VideOCR.bin"
ICON="$APPDIR/VideOCR.png"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/VideOCR.desktop"
PORTABLE_FLAG="$APPDIR/portable_mode.txt"

# Define config and log directories
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/VideOCR"
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/VideOCR"

# Check for and remove old configurations/logs to ensure a clean install
if [ -d "$CONFIG_DIR" ] || [ -d "$LOG_DIR" ]; then
    echo "Old version data found. Cleaning up old configuration and logs..."
    rm -rf "$CONFIG_DIR"
    rm -rf "$LOG_DIR"
fi

# Make sure the applications directory exists
mkdir -p "$DESKTOP_DIR"

# Create the .desktop file
cat > "$DESKTOP_FILE" <<EOL
[Desktop Entry]
Name=VideOCR
Comment=Extract hardcoded subtitles from video
Exec=$EXEC
Icon=$ICON
Terminal=false
Type=Application
Categories=Video;Utility;
StartupNotify=true
EOL

chmod +x "$DESKTOP_FILE"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null

if [ -f "$PORTABLE_FLAG" ]; then
    rm "$PORTABLE_FLAG"
    echo "Removed portable flag. Settings will now be saved to ~/.config/VideOCR/"
fi

echo "Installed VideOCR desktop shortcut to:"
echo "$DESKTOP_FILE"
