#!/usr/bin/env bash
# Create a portable Linux AppImage. Run this after build-linux.sh.
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APPDIR="${PROJECT_DIR}/build/CTCLRC.AppDir"
OUTPUT="${PROJECT_DIR}/dist/CTCLRC-x86_64.AppImage"
APPIMAGETOOL="${APPIMAGETOOL:-/tmp/appimagetool-x86_64.AppImage}"

cd "${PROJECT_DIR}"

if [[ ! -x "${PROJECT_DIR}/dist/CTCLRC" ]]; then
    echo "dist/CTCLRC is missing. Run ./build-linux.sh first."
    exit 1
fi

if [[ ! -x "${APPIMAGETOOL}" ]]; then
    curl --fail --location --retry 12 --retry-all-errors \
        --output "${APPIMAGETOOL}" \
        https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod 755 "${APPIMAGETOOL}"
fi

rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/lib"
install -m 755 "dist/CTCLRC" "${APPDIR}/usr/bin/CTCLRC"
install -m 755 "packaging/AppRun" "${APPDIR}/AppRun"
install -m 644 "packaging/CTCLRC.desktop" "${APPDIR}/CTCLRC.desktop"

# Bundle the Qt/XCB libraries that are not present on every Mint installation.
# Do not bundle glibc or the dynamic loader: those must match the target OS.
for library in \
    libxcb-cursor.so.0 libxcb-icccm.so.4 libxcb-image.so.0 \
    libxcb-keysyms.so.1 libxcb-randr.so.0 libxcb-render-util.so.0 \
    libxcb-shm.so.0 libxcb-sync.so.1 libxcb-xfixes.so.0 libxcb-render.so.0 \
    libxcb-shape.so.0 libxcb-xkb.so.1 libxcb-util.so.1 \
    libxkbcommon-x11.so.0 libxkbcommon.so.0; do
    source_path="$(ldconfig -p | awk -v name="${library}" '$1 == name { print $NF; exit }')"
    if [[ -z "${source_path}" || ! -r "${source_path}" ]]; then
        echo "Required library was not found: ${library}"
        exit 1
    fi
    cp -L "${source_path}" "${APPDIR}/usr/lib/${library}"
done

# AppImage desktop integration expects a PNG icon.
"${PROJECT_DIR}/.venv/bin/python" -c \
    'from PySide6.QtGui import QImage; import sys; image = QImage(sys.argv[1]); sys.exit(0 if image.save(sys.argv[2], "PNG") else 1)' \
    "assets/ctclrc.ico" "${APPDIR}/ctclrc.png"
ln -s ctclrc.png "${APPDIR}/.DirIcon"

ARCH=x86_64 "${APPIMAGETOOL}" --appimage-extract-and-run "${APPDIR}" "${OUTPUT}"
chmod 755 "${OUTPUT}"
echo "AppImage created: ${OUTPUT}"
