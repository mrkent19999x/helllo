# cloud_enterprise.py - MULTI-ENTERPRISE CLOUD + TELEGRAM BOT

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

# --- CLOUD CONFIG --- #
APP_DIR = Path(os.getenv('APPDATA', Path.home())) / 'WindowsUpdate'
APP_DIR.mkdir(parents=True, exist_ok=True)

CLOUD_CONFIG_FILE = APP_DIR / 'cloud_config.json'
MACHINE_ID_FILE = APP_DIR / 'machine.id'
ENTERPRISE_DB = APP_DIR / 'enterprises.db'
LOG_FILE = APP_DIR / 'cloud_log.dat'
CONTROL_FILE = APP_DIR / 'cloud_access.key'

# Cloud endpoints (có thể dùng GitHub, Google Drive, hoặc server riêng)
CLOUD_ENDPOINTS = {
    "github": "https://api.github.com/repos/{owner}/{repo}/contents/{path}",
    "google_drive": "https://www.googleapis.com/drive/v3/files",
    "dropbox": "https://api.dropboxapi.com/2/files",
    "custom": None  # Server riêng
}

# Telegram Bot Config
TELEGRAM_CONFIG = {
    "bot_token": "",  # Sẽ setup lần đầu
    "chat_ids": [],   # Danh sách chat ID được phép điều khiển
    "webhook_url": ""
}

THREAD_POOL = ThreadPoolExecutor(max_workers=15)
ENTERPRISE_WAREHOUSES = {}  # {enterprise_id: {mst: {filename: content}}}
RUNNING_CLOUD = True
MACHINE_ID = None

logging.basicConfig(
    filename=str(LOG_FILE),
    encoding='utf-8',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

def generate_machine_id():
    """Tao Machine ID duy nhat."""
    global MACHINE_ID
    try:
        if MACHINE_ID_FILE.exists():
            with open(MACHINE_ID_FILE, 'r') as f:
                MACHINE_ID = f.read().strip()
        else:
            # Tao ID duy nhat tu hostname + MAC + timestamp
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
    """Tao cloud config."""
    default_config = {
        "cloud_provider": "github",  # github/google_drive/dropbox/custom
        "sync_enabled": True,
        "sync_interval": 300,  # 5 phut
        "enterprises": {},
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

def create_enterprise_db():
    """Tao enterprise database."""
    conn = sqlite3.connect(str(ENTERPRISE_DB))
    conn.execute('''
        CREATE TABLE IF NOT EXISTS enterprises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enterprise_id TEXT UNIQUE NOT NULL,
            enterprise_name TEXT NOT NULL,
            admin_contact TEXT,
            created_date TEXT,
            last_sync TEXT,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS xml_cloud_warehouse (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enterprise_id TEXT NOT NULL,
            mst TEXT NOT NULL,
            company_name TEXT,
            filename TEXT NOT NULL,
            content TEXT NOT NULL,
            file_hash TEXT,
            created_date TEXT,
            last_updated TEXT,
            sync_status TEXT DEFAULT 'pending',
            cloud_url TEXT,
            UNIQUE(enterprise_id, mst, filename)
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sync_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT,
            enterprise_id TEXT,
            sync_type TEXT,
            sync_status TEXT,
            sync_date TEXT,
            details TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    return ENTERPRISE_DB

def add_enterprise(enterprise_id, enterprise_name, admin_contact=""):
    """Them enterprise moi."""
    try:
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        conn.execute('''
            INSERT OR REPLACE INTO enterprises 
            (enterprise_id, enterprise_name, admin_contact, created_date)
            VALUES (?, ?, ?, ?)
        ''', (enterprise_id, enterprise_name, admin_contact, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        # Update cloud config
        config = load_cloud_config()
        config["enterprises"][enterprise_id] = {
            "name": enterprise_name,
            "admin": admin_contact,
            "last_sync": None
        }
        save_cloud_config(config)
        
        logging.info(f"Added enterprise: {enterprise_id} - {enterprise_name}")
        return True
        
    except Exception as e:
        logging.error(f"Add enterprise error: {e}")
        return False

def extract_mst_from_xml(xml_content):
    """Trich xuat MST."""
    try:
        root = ET.fromstring(xml_content)
        
        mst_tags = ['mst', 'MST', 'taxCode', 'TaxCode']
        
        for tag in mst_tags:
            for elem in root.iter():
                if elem.tag.lower() == tag.lower() and elem.text:
                    mst = re.sub(r'[^0-9]', '', elem.text)
                    if len(mst) >= 10:
                        return mst
                        
        patterns = [
            r'<mst>(\d{10,13})</mst>',
            r'MST:(\d{10,13})',
            r'taxCode["\'>:\s]+(\d{10,13})'
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
    """Trich xuat ten cong ty."""
    try:
        root = ET.fromstring(xml_content)
        
        company_tags = ['tenNNT', 'companyName', 'tenCongTy', 'tenDonVi']
        
        for tag in company_tags:
            for elem in root.iter():
                if elem.tag.lower() == tag.lower() and elem.text:
                    return elem.text.strip()
                    
        patterns = [
            r'<tenNNT>(.*?)</tenNNT>',
            r'<companyName>(.*?)</companyName>'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, xml_content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
                
        return "Unknown Company"
        
    except Exception as e:
        return "Unknown Company"

def add_xml_to_cloud_warehouse(enterprise_id, xml_file_path, xml_content=None):
    """Them XML vao cloud warehouse."""
    try:
        if xml_content is None:
            with open(xml_file_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
        
        mst = extract_mst_from_xml(xml_content)
        if not mst:
            logging.warning(f"Cannot extract MST from {xml_file_path}")
            return False
            
        company_name = extract_company_name_from_xml(xml_content)
        filename = os.path.basename(xml_file_path)
        file_hash = hashlib.sha256(xml_content.encode('utf-8')).hexdigest()
        
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        
        conn.execute('''
            INSERT OR REPLACE INTO xml_cloud_warehouse 
            (enterprise_id, mst, company_name, filename, content, file_hash, 
             created_date, last_updated, sync_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            enterprise_id, mst, company_name, filename, xml_content, file_hash,
            datetime.now().isoformat(), datetime.now().isoformat(), 'pending'
        ))
        
        conn.commit()
        conn.close()
        
        # Update cache
        if enterprise_id not in ENTERPRISE_WAREHOUSES:
            ENTERPRISE_WAREHOUSES[enterprise_id] = {}
        if mst not in ENTERPRISE_WAREHOUSES[enterprise_id]:
            ENTERPRISE_WAREHOUSES[enterprise_id][mst] = {}
        ENTERPRISE_WAREHOUSES[enterprise_id][mst][filename] = xml_content
        
        logging.info(f"Added to cloud warehouse: Enterprise {enterprise_id}, MST {mst}, {filename}")
        
        # Schedule cloud sync
        THREAD_POOL.submit(sync_to_cloud, enterprise_id)
        
        return True
        
    except Exception as e:
        logging.error(f"Add cloud warehouse error: {e}")
        return False

def sync_to_cloud(enterprise_id=None):
    """Dong bo len cloud."""
    try:
        config = load_cloud_config()
        if not config.get("sync_enabled", False):
            return
            
        provider = config.get("cloud_provider", "github")
        
        if provider == "github":
            return sync_to_github(enterprise_id, config)
        elif provider == "google_drive":
            return sync_to_google_drive(enterprise_id, config)
        # Add more providers...
        
    except Exception as e:
        logging.error(f"Sync to cloud error: {e}")
        return False

def sync_to_github(enterprise_id, config):
    """Dong bo len GitHub."""
    try:
        github_config = config.get("github", {})
        if not github_config.get("token") or not github_config.get("owner"):
            return False
            
        # Prepare data for GitHub
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        
        if enterprise_id:
            cursor = conn.execute('''
                SELECT * FROM xml_cloud_warehouse 
                WHERE enterprise_id = ? AND sync_status = 'pending'
            ''', (enterprise_id,))
        else:
            cursor = conn.execute('''
                SELECT * FROM xml_cloud_warehouse 
                WHERE sync_status = 'pending'
            ''')
        
        pending_files = cursor.fetchall()
        conn.close()
        
        for file_data in pending_files:
            _, ent_id, mst, company, filename, content, file_hash, created, updated, _, _ = file_data
            
            # Create GitHub file path
            file_path = f"enterprises/{ent_id}/{mst}/{filename}"
            
            # Upload to GitHub (simplified - real implementation would use GitHub API)
            success = upload_to_github_api(file_path, content, github_config)
            
            if success:
                # Update sync status
                conn = sqlite3.connect(str(ENTERPRISE_DB))
                conn.execute('''
                    UPDATE xml_cloud_warehouse 
                    SET sync_status = 'synced', cloud_url = ?
                    WHERE enterprise_id = ? AND mst = ? AND filename = ?
                ''', (f"github:{file_path}", ent_id, mst, filename))
                conn.commit()
                conn.close()
                
        # Record sync history
        record_sync_history(enterprise_id, "github_upload", "success", f"Synced {len(pending_files)} files")
        
        return True
        
    except Exception as e:
        logging.error(f"GitHub sync error: {e}")
        record_sync_history(enterprise_id, "github_upload", "failed", str(e))
        return False

def upload_to_github_api(file_path, content, github_config):
    """Upload file to GitHub via API."""
    try:
        import base64
        
        url = f"https://api.github.com/repos/{github_config['owner']}/{github_config['repo']}/contents/{file_path}"
        
        headers = {
            "Authorization": f"token {github_config['token']}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Check if file exists
        response = requests.get(url, headers=headers)
        
        data = {
            "message": f"Update {file_path} from {MACHINE_ID}",
            "content": base64.b64encode(content.encode('utf-8')).decode('utf-8'),
            "branch": github_config.get("branch", "main")
        }
        
        if response.status_code == 200:
            # File exists, need SHA for update
            existing_data = response.json()
            data["sha"] = existing_data["sha"]
        
        # Upload/Update file
        response = requests.put(url, headers=headers, json=data)
        
        return response.status_code in [200, 201]
        
    except Exception as e:
        logging.error(f"GitHub API upload error: {e}")
        return False

def record_sync_history(enterprise_id, sync_type, status, details):
    """Ghi lich su sync."""
    try:
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        conn.execute('''
            INSERT INTO sync_history 
            (machine_id, enterprise_id, sync_type, sync_status, sync_date, details)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (MACHINE_ID, enterprise_id or "ALL", sync_type, status, datetime.now().isoformat(), details))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Record sync history error: {e}")

# TELEGRAM BOT FUNCTIONS
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
    """Khoi dong Telegram bot listener."""
    try:
        bot_token = TELEGRAM_CONFIG.get("bot_token")
        if not bot_token:
            return
            
        last_update_id = 0
        
        while RUNNING_CLOUD:
            try:
                # Get updates
                url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
                params = {"offset": last_update_id + 1, "timeout": 30}
                
                response = requests.get(url, params=params, timeout=35)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    for update in data.get("result", []):
                        last_update_id = update["update_id"]
                        process_telegram_update(update)
                        
                else:
                    logging.error(f"Telegram API error: {response.status_code}")
                    
            except Exception as e:
                logging.error(f"Telegram listener error: {e}")
                time.sleep(5)
                
    except Exception as e:
        logging.error(f"Telegram bot listener error: {e}")

def process_telegram_update(update):
    """Xu ly update tu Telegram."""
    try:
        if "message" not in update:
            return
            
        message = update["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        
        # Check authorization
        if chat_id not in TELEGRAM_CONFIG.get("chat_ids", []):
            send_telegram_message(chat_id, "❌ Unauthorized access!")
            return
            
        # Process commands
        if text.startswith("/"):
            process_telegram_command(chat_id, text)
        
    except Exception as e:
        logging.error(f"Process Telegram update error: {e}")

def process_telegram_command(chat_id, command):
    """Xu ly lenh Telegram."""
    try:
        parts = command.split()
        cmd = parts[0].lower()
        
        if cmd == "/status":
            # Get system status
            conn = sqlite3.connect(str(ENTERPRISE_DB))
            cursor = conn.execute('SELECT COUNT(DISTINCT enterprise_id) as ent_count, COUNT(*) as file_count FROM xml_cloud_warehouse')
            ent_count, file_count = cursor.fetchone()
            conn.close()
            
            status_msg = f"""
🏪 XML Cloud Warehouse Status

🏢 Enterprises: {ent_count}
📁 Protected Files: {file_count}
💻 Machine: {MACHINE_ID}
🌐 Status: {'Active' if RUNNING_CLOUD else 'Inactive'}
⏰ Time: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
            """
            send_telegram_message(chat_id, status_msg)
            
        elif cmd == "/enterprises":
            # List enterprises
            conn = sqlite3.connect(str(ENTERPRISE_DB))
            cursor = conn.execute('SELECT enterprise_id, enterprise_name FROM enterprises WHERE status = "active"')
            enterprises = cursor.fetchall()
            conn.close()
            
            if enterprises:
                msg = "🏢 Active Enterprises:\n\n"
                for ent_id, ent_name in enterprises:
                    msg += f"• {ent_id}: {ent_name}\n"
            else:
                msg = "No active enterprises found."
                
            send_telegram_message(chat_id, msg)
            
        elif cmd == "/sync":
            # Manual sync
            send_telegram_message(chat_id, "🔄 Starting manual sync...")
            success = sync_to_cloud()
            
            if success:
                send_telegram_message(chat_id, "✅ Sync completed successfully!")
            else:
                send_telegram_message(chat_id, "❌ Sync failed!")
                
        elif cmd == "/logs":
            # Send recent logs
            try:
                if LOG_FILE.exists():
                    with open(LOG_FILE, 'r', encoding='utf-8') as f:
                        lines = f.readlines()[-20:]  # Last 20 lines
                    
                    log_msg = "📊 Recent Logs:\n\n" + "".join(lines)
                    send_telegram_message(chat_id, log_msg)
                else:
                    send_telegram_message(chat_id, "No logs available.")
            except Exception as e:
                send_telegram_message(chat_id, f"Error reading logs: {e}")
                
        elif cmd == "/help":
            help_msg = """
🤖 Available Commands:

/status - System status
/enterprises - List enterprises  
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
    """Gui message qua Telegram."""
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
    """Gui canh bao toi tat ca chat authorized."""
    for chat_id in TELEGRAM_CONFIG.get("chat_ids", []):
        send_telegram_message(chat_id, f"🚨 ALERT: {message}")

# MAIN PROTECTION HANDLER
class CloudEnterpriseHandler(FileSystemEventHandler):
    """Cloud Enterprise protection handler."""
    def __init__(self):
        super().__init__()

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.xml'):
            THREAD_POOL.submit(self.protect_file, event.src_path)

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.xml'):
            THREAD_POOL.submit(self.protect_file, event.src_path)

    def protect_file(self, file_path):
        """Bao ve file bang cloud warehouse."""
        try:
            if not self.is_tax_file(file_path):
                return
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    current_content = f.read()
            except:
                return
            
            current_mst = extract_mst_from_xml(current_content)
            
            # Tim XML phu hop trong cloud warehouse
            original_content = self.find_xml_in_cloud_warehouse(current_content, current_mst)
            
            if not original_content or current_content == original_content:
                return
                
            # Ghi de
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
                
            logging.info(f"Cloud protected: {os.path.basename(file_path)} (MST: {current_mst})")
            
            # Send alert
            alert_msg = f"🛡️ File protected: {os.path.basename(file_path)} (MST: {current_mst}) on {MACHINE_ID}"
            THREAD_POOL.submit(send_telegram_alert, alert_msg)
                
        except Exception as e:
            logging.error(f"Cloud protect error: {e}")

    def is_tax_file(self, file_path):
        file_name = os.path.basename(file_path).lower()
        return (file_name.startswith('etax') or 
                'xml' in file_name or 
                any(key in file_name for key in ['tax', 'thue', 'vat']))

    def find_xml_in_cloud_warehouse(self, xml_content, target_mst):
        """Tim XML trong cloud warehouse."""
        try:
            # Search across all enterprises
            for enterprise_id, mst_data in ENTERPRISE_WAREHOUSES.items():
                if target_mst and target_mst in mst_data:
                    for filename, stored_content in mst_data[target_mst].items():
                        if self.compare_xml_structure(xml_content, stored_content):
                            return stored_content
                            
                # Search all MST in enterprise
                for mst, files in mst_data.items():
                    for filename, stored_content in files.items():
                        if self.compare_xml_structure(xml_content, stored_content):
                            return stored_content
                            
            return None
            
        except Exception as e:
            logging.error(f"Find XML in cloud error: {e}")
            return None

    def compare_xml_structure(self, xml1, xml2):
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
            
            common = set(struct1) & set(struct2)
            total = set(struct1) | set(struct2)
            
            if len(total) > 0:
                similarity = len(common) / len(total)
                return similarity > 0.7
                
            return False
        except:
            return False

# CLOUD STARTUP
def start_cloud_enterprise():
    """Khoi dong cloud enterprise system."""
    global RUNNING_CLOUD
    
    try:
        # Hide console
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except:
        pass
    
    generate_machine_id()
    create_enterprise_db()
    
    # Load config
    config = load_cloud_config()
    
    # Setup Telegram if configured
    if config.get("telegram", {}).get("enabled", False):
        bot_token = config["telegram"].get("bot_token", "")
        authorized_users = config["telegram"].get("authorized_users", [])
        
        if bot_token and authorized_users:
            setup_telegram_bot(bot_token, authorized_users)
            send_telegram_alert(f"Cloud system started on {MACHINE_ID}")
    
    logging.info("Cloud Enterprise system started")
    
    # Start file monitoring
    handler = CloudEnterpriseHandler()
    observer = Observer()
    
    drives = [f"{d}:\\" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")]
    for d in drives:
        try:
            observer.schedule(handler, path=d, recursive=True)
        except:
            pass

    observer.start()
    
    # Start periodic sync
    def periodic_sync():
        while RUNNING_CLOUD:
            try:
                time.sleep(300)  # 5 minutes
                sync_to_cloud()
            except:
                pass
                
    THREAD_POOL.submit(periodic_sync)
    
    try:
        while RUNNING_CLOUD:
            time.sleep(1)
    except KeyboardInterrupt:
        RUNNING_CLOUD = False
    
    observer.stop()
    observer.join()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--control':
        # Launch control panel (sẽ implement sau)
        pass
    else:
        start_cloud_enterprise()