"""PyInstaller runtime hook (Linux only).

The XCB platform libraries (libxcb-*.so.0, libxkbcommon*.so.0) are bundled as
data files next to the frozen app. Qt's XCB plugin (libqxcb.so) dlopens them at
startup; if they are absent from the system the dlopen fails and no GUI is
created. Prepending the frozen directory to LD_LIBRARY_PATH makes the bundled
libraries discoverable before Qt loads its XCB platform plugin.
"""

import os
import sys


def _prepend_frozen_dir_to_ld_library_path() -> None:
    base = getattr(sys, "_MEIPASS", None)
    if not base or not os.path.isdir(base):
        return
    current = os.environ.get("LD_LIBRARY_PATH", "")
    parts = [p for p in current.split(os.pathsep) if p]
    if base not in parts:
        parts.insert(0, base)
        os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(parts)


_prepend_frozen_dir_to_ld_library_path()
