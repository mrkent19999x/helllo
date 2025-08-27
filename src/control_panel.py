# control_panel.py - CONTROL PANEL RIÊNG

import customtkinter as ctk
import subprocess
import sys
import os

def main():
    # Chạy invisible guard với control mode
    script_dir = os.path.dirname(os.path.abspath(__file__))
    guard_script = os.path.join(script_dir, 'invisible_guard.py')
    
    if os.path.exists(guard_script):
        subprocess.run([sys.executable, guard_script, '--control'])
    else:
        # Fallback - tìm exe
        exe_path = os.path.join(script_dir, 'dist', 'InvisibleTaxGuard.exe')
        if os.path.exists(exe_path):
            subprocess.run([exe_path, '--control'])
        else:
            ctk.CTk().withdraw()
            import tkinter.messagebox as msgbox
            msgbox.showerror("Error", "Cannot find Invisible Tax Guard!")

if __name__ == '__main__':
    main()