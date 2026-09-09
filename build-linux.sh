#!/usr/bin/env bash
# Build the Linux Mint distribution (an ELF executable, the Linux equivalent of .exe).
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_DIR}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "${PROJECT_DIR}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "Python 3 was not found. Install it with: sudo apt install python3 python3-venv"
    exit 1
fi

if ! ldconfig -p 2>/dev/null | grep -q 'libxcb-cursor\.so\.0'; then
    cat <<'EOF'
Missing Linux GUI dependency: libxcb-cursor0
Install it once, then rerun this script:
  sudo apt update && sudo apt install libxcb-cursor0
EOF
    exit 1
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/python" -m pip install --upgrade pip
# Install the CPU wheel first.  The PyPI Linux wheel otherwise pulls several GB
# of NVIDIA CUDA libraries even on PCs that will run this app on the CPU.
# The retry settings tolerate unstable connections when downloading PyTorch.
PIP_DOWNLOAD_ARGS=(--retries 12 --resume-retries 30 --timeout 120)
"${VENV_DIR}/bin/python" -m pip install "${PIP_DOWNLOAD_ARGS[@]}" \
    "torch==2.8.0" --index-url https://download.pytorch.org/whl/cpu
"${VENV_DIR}/bin/python" -m pip install "${PIP_DOWNLOAD_ARGS[@]}" -r requirements.txt
"${VENV_DIR}/bin/python" -m PyInstaller --clean --noconfirm CTCLRC.spec

# PyInstaller normally preserves this mode, but ensure the packaged file can be
# launched by double-clicking or from a terminal after copying it elsewhere.
chmod 755 "${PROJECT_DIR}/dist/CTCLRC"

echo
echo "Build complete: ${PROJECT_DIR}/dist/CTCLRC"
echo "Run it with: ${PROJECT_DIR}/dist/CTCLRC"
