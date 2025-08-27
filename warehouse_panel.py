# warehouse_panel.py - XML WAREHOUSE CONTROL PANEL

import subprocess
import sys
import os

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Tim warehouse exe
    exe_path = os.path.join(script_dir, 'dist', 'XMLWarehouse_Stealth.exe')
    if os.path.exists(exe_path):
        subprocess.run([exe_path, '--control'])
    else:
        # Fallback
        import customtkinter as ctk
        import tkinter.messagebox as msgbox
        ctk.CTk().withdraw()
        msgbox.showerror("Error", "Cannot find XML Warehouse!")

if __name__ == '__main__':
    main()