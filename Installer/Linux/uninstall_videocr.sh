#!/bin/bash

DESKTOP_FILE="$HOME/.local/share/applications/VideOCR.desktop"

if [ -f "$DESKTOP_FILE" ]; then
    echo "Removing desktop shortcut..."
    rm "$DESKTOP_FILE"
    update-desktop-database ~/.local/share/applications 2>/dev/null
    echo "Desktop entry removed."
else
    echo "Desktop shortcut not found."
fi

echo "You can now safely delete the VideOCR folder from your system if no longer needed."

