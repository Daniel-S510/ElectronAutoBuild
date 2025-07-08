import os
import sys
import subprocess
from cx_Freeze import setup, Executable

# Define base for Windows GUI app
base = None
if sys.platform == "win32":
    base = "Win32GUI"

# Application details
application_name = "Electron Auto Build"
main_script = "electron_auto_build.py"

# Dependencies to include
build_exe_options = {
    "packages": ["tkinter", "os", "shutil", "subprocess", "pathlib"],
    "include_files": []
}

# Setup configuration
setup(
    name=application_name,
    version="1.0",
    description="A tool to convert React apps to Electron .exe files",
    options={"build_exe": build_exe_options},
    executables=[Executable(main_script, base=base, target_name="ElectronAutoBuild.exe")]
)
