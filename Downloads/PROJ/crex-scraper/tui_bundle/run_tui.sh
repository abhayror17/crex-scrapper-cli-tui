#!/usr/bin/env bash
echo "========================================"
echo "  CREX Cricket TUI"
echo "========================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found. Install Python 3.9+"
    exit 1
fi

python3 tui.py