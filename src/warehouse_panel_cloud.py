# warehouse_panel_cloud.py - XML WAREHOUSE CLOUD CONTROL PANEL

import subprocess
import sys
import os

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Tim cloud exe - try different paths
    possible_paths = [
        os.path.join(script_dir, 'XMLWarehouse_Cloud.exe'),  # Same directory
        os.path.join(script_dir, 'dist', 'XMLWarehouse_Cloud.exe'),  # In dist folder
        os.path.join(os.path.dirname(script_dir), 'XMLWarehouse_Cloud.exe')  # Parent directory
    ]
    
    exe_path = None
    for path in possible_paths:
        if os.path.exists(path):
            exe_path = path
            break
    
    if exe_path:
        subprocess.run([exe_path, '--control'])
    else:
        # Fallback - run control panel directly
        try:
            # Import cloud_enterprise functions directly
            sys.path.insert(0, script_dir)
            from cloud_enterprise import launch_cloud_control_panel
            launch_cloud_control_panel()
        except:
            import customtkinter as ctk
            import tkinter.messagebox as msgbox
            ctk.CTk().withdraw()
            msgbox.showerror("Error", 
                f"Cannot find XML Warehouse Cloud!\n\nSearched paths:\n" + 
                "\n".join(possible_paths))

if __name__ == '__main__':
    main()