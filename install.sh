#!/usr/bin/env bash
set -e

APP_NAME="cloud-orch"
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$INSTALL_DIR/.venv"
echo "Installing $APP_NAME..."

# Check for python3
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 is not installed. Please install Python 3.10+ first."
    exit 1
fi

# Check python version >= 3.10
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
    echo "Error: Python 3.10+ required, found $PYTHON_VERSION"
    exit 1
fi
echo "Found Python $PYTHON_VERSION"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Check pip is available in the venv
if [ ! -f "$VENV_DIR/bin/pip" ]; then
    echo "Error: pip not found in venv. Reinstalling..."
    python3 -m venv --clear "$VENV_DIR"
fi

# Install dependencies
echo "Installing dependencies..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

# Create wrapper script
WRAPPER="$INSTALL_DIR/$APP_NAME"
cat > "$WRAPPER" << EOF
#!/usr/bin/env bash
exec "$VENV_DIR/bin/python" -m src.main "\$@"
EOF
chmod +x "$WRAPPER"

# Add to PATH via shell profile
SHELL_RC=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
elif [ -f "$HOME/.bash_profile" ]; then
    SHELL_RC="$HOME/.bash_profile"
fi

PATH_LINE="export PATH=\"$INSTALL_DIR:\$PATH\""

if [ -n "$SHELL_RC" ]; then
    if ! grep -qF "$INSTALL_DIR" "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# CloudOrchestrator CLI" >> "$SHELL_RC"
        echo "$PATH_LINE" >> "$SHELL_RC"
        echo "Added $APP_NAME to PATH in $SHELL_RC"
        echo "Run 'source $SHELL_RC' or open a new terminal to use it."
    else
        echo "$APP_NAME is already in PATH ($SHELL_RC)"
    fi
else
    echo ""
    echo "Could not detect shell profile. Add this to your shell config manually:"
    echo "  $PATH_LINE"
fi

echo ""
echo "Done! Run '$APP_NAME --help' to get started."
