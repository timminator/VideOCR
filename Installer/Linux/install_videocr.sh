#!/bin/bash

# Get the absolute path of the folder where the script is located
APPDIR="$(cd "$(dirname "$0")" && pwd)"
EXEC="$APPDIR/VideOCR.bin"
ICON="$APPDIR/VideOCR.png"
DESKTOP_FILE="$HOME/.local/share/applications/VideOCR.desktop"

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

echo "Installed VideOCR desktop shortcut to:"
echo "$DESKTOP_FILE"

