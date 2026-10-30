#!/usr/bin/env bash
# Removes all desktop build artifacts (PyInstaller + Cargo + Vite dist).
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

echo "==> Cleaning PyInstaller artifacts..."
rm -rf "$ROOT/backend/build" "$ROOT/backend/dist"

echo "==> Cleaning Cargo build cache..."
rm -rf "$ROOT/frontend/src-tauri/target"

echo "==> Cleaning staged sidecar binaries..."
rm -rf "$ROOT/frontend/src-tauri/binaries"

echo "==> Cleaning Vite dist..."
rm -rf "$ROOT/frontend/dist"

echo "Done. All build artifacts removed."
