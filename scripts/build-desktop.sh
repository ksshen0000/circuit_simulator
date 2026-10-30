#!/usr/bin/env bash
# Builds the Circuit Simulator desktop app (Tauri + PyInstaller).
# Prerequisites: Rust, Python 3, Node.js, system WebKit libs (Linux: libwebkit2gtk-4.1-dev)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

# Load Rust toolchain if installed via rustup
[ -f "$HOME/.cargo/env" ] && source "$HOME/.cargo/env"

# ── 1. Build Python backend ──────────────────────────────────────────────────
echo "==> Building Python backend with PyInstaller..."
cd "$ROOT/backend"
pip install pyinstaller -q
pyinstaller circuit_simulator.spec --noconfirm --clean

# ── 2. Copy binary with Tauri sidecar naming convention ─────────────────────
TARGET=$(rustc -Vv 2>/dev/null | grep host | awk '{print $2}')
if [ -z "$TARGET" ]; then
    echo "ERROR: rustc not found. Install Rust: https://rustup.rs"
    exit 1
fi

echo "==> Staging binary for target: $TARGET"
BINARY_DIR="$ROOT/frontend/src-tauri/binaries"
mkdir -p "$BINARY_DIR"

EXT=""
[[ "$TARGET" == *"windows"* ]] && EXT=".exe"

cp "$ROOT/backend/dist/circuit-simulator-backend${EXT}" \
   "$BINARY_DIR/circuit-simulator-backend-${TARGET}${EXT}"

# ── 3. Generate app icons (requires the svg favicon) ────────────────────────
echo "==> Generating icons..."
cd "$ROOT/frontend"
npm install -q
npx tauri icon public/favicon.svg

# ── 4. Build Tauri app ───────────────────────────────────────────────────────
echo "==> Building Tauri desktop app..."
npm run tauri build

echo ""
echo "Build complete! Installers are in:"
echo "  frontend/src-tauri/target/release/bundle/"
