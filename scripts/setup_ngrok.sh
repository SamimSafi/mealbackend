#!/bin/bash
# Shell script to configure ngrok authtoken (Linux/macOS)

AUTHTOKEN="4NUsoYfBtHFvg2mbAXh5U_4XN8S6cYhG5qtNS89h9Mc"

echo "=========================================="
echo "Configuring ngrok Authtoken"
echo "=========================================="
echo ""

# Method 1: Set environment variable for current session
echo "[1] Setting environment variable for current session..."
export NGROK_AUTHTOKEN="$AUTHTOKEN"
echo "    NGROK_AUTHTOKEN set for current shell session"
echo ""

# Method 2: Configure ngrok directly (recommended)
echo "[2] Configuring ngrok config file (recommended)..."
if command -v ngrok &> /dev/null; then
    ngrok config add-authtoken "$AUTHTOKEN"
    if [ $? -eq 0 ]; then
        echo "    ✅ ngrok authtoken configured successfully!"
    else
        echo "    ⚠️  Could not configure ngrok"
    fi
else
    echo "    ⚠️  ngrok is not installed"
fi
echo ""

# Method 3: Add to shell profile (permanent)
echo "[3] Adding to shell profile for permanent setup..."
SHELL_PROFILE=""

if [ -f "$HOME/.zshrc" ]; then
    SHELL_PROFILE="$HOME/.zshrc"
    echo "    Found .zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_PROFILE="$HOME/.bashrc"
    echo "    Found .bashrc"
elif [ -f "$HOME/.bash_profile" ]; then
    SHELL_PROFILE="$HOME/.bash_profile"
    echo "    Found .bash_profile"
fi

if [ -n "$SHELL_PROFILE" ]; then
    # Check if already added
    if grep -q "NGROK_AUTHTOKEN" "$SHELL_PROFILE"; then
        echo "    ⚠️  NGROK_AUTHTOKEN already exists in $SHELL_PROFILE"
        echo "    Skipping addition (to update, edit manually)"
    else
        echo "" >> "$SHELL_PROFILE"
        echo "# ngrok authtoken" >> "$SHELL_PROFILE"
        echo "export NGROK_AUTHTOKEN=\"$AUTHTOKEN\"" >> "$SHELL_PROFILE"
        echo "    ✅ Added to $SHELL_PROFILE"
        echo "    Note: Restart terminal or run: source $SHELL_PROFILE"
    fi
else
    echo "    ⚠️  Could not find shell profile (.bashrc, .zshrc, or .bash_profile)"
    echo "    Please add manually: export NGROK_AUTHTOKEN=\"$AUTHTOKEN\""
fi
echo ""

echo "=========================================="
echo "✅ Configuration Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Verify: ngrok config check"
echo "  2. Start ngrok: ngrok http 8000"
echo ""

