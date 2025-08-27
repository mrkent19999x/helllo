#!/usr/bin/env python3
"""Build script for Tax Protection Cloud GUI"""

import os
import sys
import subprocess
from pathlib import Path

def build_exe():
    """Build EXE using PyInstaller"""
    print("Building Tax Protection Cloud GUI to EXE...")
    
    # Get current directory
    current_dir = Path(__file__).parent
    src_dir = current_dir / "src"
    build_dir = current_dir / "build_output"
    
    # Ensure build directory exists
    build_dir.mkdir(exist_ok=True)
    
    # Main script path
    main_script = src_dir / "cloud_enterprise.py"
    
    if not main_script.exists():
        print("ERROR: cloud_enterprise.py not found in src directory")
        return False
    
    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--onefile",                    # Single EXE file
        "--windowed",                   # No console window  
        "--name", "TaxProtection_CloudGUI",
        "--distpath", str(build_dir),   # Output directory
        "--workpath", str(build_dir / "temp"),
        "--specpath", str(build_dir),
        "--add-data", f"{src_dir};src", # Include src folder
        "--hidden-import", "customtkinter",
        "--hidden-import", "PIL",
        "--hidden-import", "watchdog",
        "--hidden-import", "requests", 
        "--hidden-import", "sqlite3",
        "--hidden-import", "tkinter",
        "--clean",                      # Clean build
        str(main_script)
    ]
    
    print("Running PyInstaller...")
    print("Command:", " ".join(cmd))
    
    try:
        # Change to project directory
        os.chdir(current_dir)
        
        # Run PyInstaller
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        print("Build successful!")
        print("EXE location:", build_dir / "TaxProtection_CloudGUI.exe")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print("Build failed!")
        print("Error:", e.stderr)
        return False
    except Exception as e:
        print("Unexpected error:", e)
        return False

if __name__ == "__main__":
    success = build_exe()
    if success:
        print("\nBuild completed successfully!")
        print("You can now run: build_output\\TaxProtection_CloudGUI.exe")
    else:
        print("\nBuild failed. Please check errors above.")
    
    input("Press Enter to exit...")