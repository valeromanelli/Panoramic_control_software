"""Machine-specific defaults for the panoramic acquisition platform.

Every value can be overridden with an environment variable, allowing the
repository to run on a different workstation without editing source files.
"""

from __future__ import annotations

import os
from pathlib import Path


def _path_from_env(name: str, default: str) -> Path:
    """Return a user-expandable path read from the environment."""
    return Path(os.getenv(name, default)).expanduser()


NI_DEVICE = os.getenv("PANORAMIC_NI_DEVICE", "Dev2")
NI_PORT0 = f"{NI_DEVICE}/port0"
NI_PORT1 = f"{NI_DEVICE}/port1"
NI_PORT0_LINES = f"{NI_DEVICE}/port0/line0:31"

CAMERA_SERIALS = {
    1: os.getenv("PANORAMIC_CAMERA_1_SERIAL", "S/N: 306342").encode("ascii"),
    2: os.getenv("PANORAMIC_CAMERA_2_SERIAL", "S/N: 306343").encode("ascii"),
    3: os.getenv("PANORAMIC_CAMERA_3_SERIAL", "S/N: 306340").encode("ascii"),
    4: os.getenv("PANORAMIC_CAMERA_4_SERIAL", "S/N: 301529").encode("ascii"),
}

CAMERA_DATA_DIRECTORY = _path_from_env(
    "PANORAMIC_CAMERA_DATA_DIRECTORY",
    "C:/Users/Panoramic/Desktop/Camera Repository",
)
PATTERN_REPOSITORY = _path_from_env(
    "PANORAMIC_PATTERN_REPOSITORY",
    "C:/Users/Panoramic/Desktop/Pattern Files Repository",
)
PATTERN_OUTPUT_DIRECTORY = _path_from_env(
    "PANORAMIC_PATTERN_OUTPUT_DIRECTORY",
    "D:/images",
)
PYTHON_32BIT_EXECUTABLE = _path_from_env(
    "PANORAMIC_PYTHON_32BIT_EXECUTABLE",
    "C:/Users/Panoramic/AppData/Local/Programs/Python/Python313-32/python.exe",
)
SERVER_32BIT_SCRIPT = _path_from_env(
    "PANORAMIC_SERVER_32BIT_SCRIPT",
    "C:/Users/Panoramic/PycharmProjects/32bitPython/server_32bit.py",
)
DAC_SERVER_HOST = os.getenv("PANORAMIC_DAC_SERVER_HOST", "127.0.0.1")
DAC_SERVER_PORT = int(os.getenv("PANORAMIC_DAC_SERVER_PORT", "65432"))

DMD_USB_VENDOR_ID = int(os.getenv("PANORAMIC_DMD_USB_VENDOR_ID", "0x0451"), 0)
DMD_USB_PRODUCT_ID = int(os.getenv("PANORAMIC_DMD_USB_PRODUCT_ID", "0x6401"), 0)
