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
    """Trich xuat MST - Hỗ trợ TKhaiThue, TBaoThue, HSoThueDTu."""
    try:
        root = ET.fromstring(xml_content)
        
        # 1. Tìm MST trong các tag phổ biến
        mst_tags = ['mst', 'MST', 'taxCode', 'TaxCode', 'maNNT', 'maNNhan', 'msT']
        
        for tag in mst_tags:
            for elem in root.iter():
                if elem.tag.lower() == tag.lower() and elem.text:
                    mst = re.sub(r'[^0-9]', '', elem.text)
                    if len(mst) >= 10:
                        return mst
        
        # 2. Tìm MST trong TBaoThueDTu format
        # <maNNhan>0314039590</maNNhan>
        for elem in root.iter():
            if 'manhan' in elem.tag.lower() or 'mannt' in elem.tag.lower():
                if elem.text:
                    mst = re.sub(r'[^0-9]', '', elem.text)
                    if len(mst) >= 10:
                        return mst
        
        # 3. Tìm MST trong HSoThueDTu format
        # Thường có trong TTinNNTKhai/maSoThue
        for elem in root.iter():
            if 'masothue' in elem.tag.lower() or 'mst' in elem.tag.lower():
                if elem.text:
                    mst = re.sub(r'[^0-9]', '', elem.text)
                    if len(mst) >= 10:
                        return mst
        
        # 4. Regex patterns mở rộng
        patterns = [
            r'<mst>(\d{10,13})</mst>',
            r'<maNNhan>(\d{10,13})</maNNhan>',
            r'<maNNT>(\d{10,13})</maNNT>',
            r'<maSoThue>(\d{10,13})</maSoThue>',
            r'MST:(\d{10,13})',
            r'taxCode["\'>:\s]+(\d{10,13})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, xml_content, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # 5. Tìm trong content text (fallback)
        mst_matches = re.findall(r'\b(\d{10,13})\b', xml_content)
        for match in mst_matches:
            if len(match) >= 10:
                return match
                
        return None
        
    except Exception as e:
        logging.error(f"Extract MST error: {e}")
        return None

def extract_company_name_from_xml(xml_content):
    """Trich xuat ten cong ty - Hỗ trợ TKhaiThue, TBaoThue, HSoThueDTu."""
    try:
        root = ET.fromstring(xml_content)
        
        # 1. Các tag tên công ty phổ biến
        company_tags = [
            'tenNNT', 'companyName', 'tenCongTy', 'tenDonVi', 
            'tenNNhan', 'hoTenNNTKhai', 'tenToChuc'
        ]
        
        for tag in company_tags:
            for elem in root.iter():
                if elem.tag.lower() == tag.lower() and elem.text:
                    company_name = elem.text.strip()
                    if len(company_name) > 5:  # Tên công ty phải > 5 ký tự
                        return company_name
        
        # 2. Tìm trong TBaoThueDTu format  
        # <tenNNhan>CÔNG TY CỔ PHẦN...</tenNNhan>
        for elem in root.iter():
            if 'tennhan' in elem.tag.lower() or 'tennnt' in elem.tag.lower():
                if elem.text:
                    company_name = elem.text.strip()
                    if len(company_name) > 5:
                        return company_name
        
        # 3. Regex patterns mở rộng
        patterns = [
            r'<tenNNT>(.*?)</tenNNT>',
            r'<tenNNhan>(.*?)</tenNNhan>',
            r'<companyName>(.*?)</companyName>',
            r'<hoTenNNTKhai>(.*?)</hoTenNNTKhai>',
            r'<tenToChuc>(.*?)</tenToChuc>'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, xml_content, re.IGNORECASE | re.DOTALL)
            if match:
                company_name = match.group(1).strip()
                if len(company_name) > 5:
                    return company_name
                
        return "Unknown Company"
        
    except Exception as e:
        logging.error(f"Extract company name error: {e}")
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
        
        # Check if file already exists (prevent duplicates)
        cursor = conn.execute('''
            SELECT id FROM xml_cloud_warehouse 
            WHERE enterprise_id = ? AND mst = ? AND filename = ?
        ''', (enterprise_id, mst, filename))
        
        existing_file = cursor.fetchone()
        
        if existing_file:
            logging.warning(f"File already exists: {filename} for MST {mst}, skipping...")
            conn.close()
            return False  # Skip duplicate
        
        conn.execute('''
            INSERT INTO xml_cloud_warehouse 
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

def sync_to_google_drive(enterprise_id, config):
    """Dong bo len Google Drive (placeholder)."""
    # TODO: Implement Google Drive API integration
    logging.info(f"Google Drive sync not implemented yet for enterprise {enterprise_id}")
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

def load_warehouse_cache():
    """Load XML warehouse vao cache."""
    global ENTERPRISE_WAREHOUSES
    
    try:
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        cursor = conn.execute('''
            SELECT enterprise_id, mst, filename, content
            FROM xml_cloud_warehouse
            ORDER BY enterprise_id, mst, filename
        ''')
        
        warehouse_data = cursor.fetchall()
        conn.close()
        
        ENTERPRISE_WAREHOUSES.clear()
        
        for enterprise_id, mst, filename, content in warehouse_data:
            if enterprise_id not in ENTERPRISE_WAREHOUSES:
                ENTERPRISE_WAREHOUSES[enterprise_id] = {}
            if mst not in ENTERPRISE_WAREHOUSES[enterprise_id]:
                ENTERPRISE_WAREHOUSES[enterprise_id][mst] = {}
            
            ENTERPRISE_WAREHOUSES[enterprise_id][mst][filename] = content
            
        logging.info(f"Loaded {len(warehouse_data)} XML files into cache from {len(ENTERPRISE_WAREHOUSES)} enterprises")
        
    except Exception as e:
        logging.error(f"Load warehouse cache error: {e}")
        ENTERPRISE_WAREHOUSES = {}

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
                
        elif cmd.startswith("/add_enterprise"):
            # Add enterprise command: /add_enterprise <id> <name>
            if len(parts) < 3:
                send_telegram_message(chat_id, "❌ Usage: /add_enterprise <id> <name>")
                return
                
            ent_id = parts[1]
            ent_name = " ".join(parts[2:])
            
            if add_enterprise(ent_id, ent_name):
                send_telegram_message(chat_id, f"✅ Enterprise '{ent_name}' added with ID: {ent_id}")
            else:
                send_telegram_message(chat_id, f"❌ Failed to add enterprise {ent_id}")
                
        elif cmd.startswith("/machine_info"):
            # Machine information
            info_msg = f"""
💻 Machine Information:

🆔 Machine ID: {MACHINE_ID}
🖥️ Hostname: {socket.gethostname()}
💾 OS: {platform.system()} {platform.release()}
⏰ Uptime: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
📂 App Dir: {APP_DIR}

Status: {'🟢 Active' if RUNNING_CLOUD else '🔴 Inactive'}
            """
            send_telegram_message(chat_id, info_msg)
            
        elif cmd.startswith("/stats"):
            # Detailed statistics
            try:
                conn = sqlite3.connect(str(ENTERPRISE_DB))
                
                # Enterprise stats
                cursor = conn.execute('''
                    SELECT enterprise_id, enterprise_name, COUNT(w.id) as file_count
                    FROM enterprises e
                    LEFT JOIN xml_cloud_warehouse w ON e.enterprise_id = w.enterprise_id
                    GROUP BY e.enterprise_id
                    ORDER BY file_count DESC
                ''')
                enterprise_stats = cursor.fetchall()
                
                # Sync stats
                cursor = conn.execute('''
                    SELECT sync_type, sync_status, COUNT(*) as count
                    FROM sync_history
                    WHERE sync_date > datetime('now', '-7 days')
                    GROUP BY sync_type, sync_status
                ''')
                sync_stats = cursor.fetchall()
                
                conn.close()
                
                stats_msg = "📊 System Statistics (Last 7 Days):\n\n"
                
                stats_msg += "🏢 Enterprises:\n"
                for ent_id, name, count in enterprise_stats[:5]:  # Top 5
                    stats_msg += f"• {name[:20]}: {count} files\n"
                    
                stats_msg += "\n🔄 Sync Operations:\n"
                for sync_type, status, count in sync_stats:
                    stats_msg += f"• {sync_type} - {status}: {count}x\n"
                    
                send_telegram_message(chat_id, stats_msg)
                
            except Exception as e:
                send_telegram_message(chat_id, f"Error getting stats: {e}")
                
        elif cmd.startswith("/alerts"):
            # Configure alerts
            parts = command.split(maxsplit=1)
            if len(parts) < 2:
                send_telegram_message(chat_id, "❌ Usage: /alerts <on|off>")
                return
                
            setting = parts[1].lower()
            if setting in ["on", "enable", "1"]:
                # Add chat_id to alerts if not already there
                if chat_id not in TELEGRAM_CONFIG.get("chat_ids", []):
                    config = load_cloud_config()
                    if chat_id not in config.get("telegram", {}).get("authorized_users", []):
                        config["telegram"]["authorized_users"].append(chat_id)
                        save_cloud_config(config)
                        TELEGRAM_CONFIG["chat_ids"] = config["telegram"]["authorized_users"]
                
                send_telegram_message(chat_id, "✅ Alerts enabled for this chat")
                
            elif setting in ["off", "disable", "0"]:
                send_telegram_message(chat_id, "ℹ️ Alerts are managed globally. Use /help for info.")
            else:
                send_telegram_message(chat_id, "❌ Usage: /alerts <on|off>")
                
        elif cmd == "/help":
            help_msg = """
🤖 XML Cloud Control Bot

📊 **Status Commands:**
/status - System overview
/stats - Detailed statistics  
/machine_info - Machine details
/logs - Recent activity logs

🏢 **Enterprise Management:**
/enterprises - List all enterprises
/add_enterprise <id> <name> - Add new enterprise

🔄 **Sync Operations:**
/sync - Manual cloud synchronization
/alerts <on|off> - Configure alerts

❓ **Help:**
/help - Show this help message

🤖 Machine: """ + MACHINE_ID
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
    
    # Load warehouse cache
    load_warehouse_cache()
    
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

# CLOUD CONTROL PANEL
def launch_cloud_control_panel():
    """Launch Cloud Control Panel GUI."""
    
    class CloudControlApp:
        def __init__(self):
            self.window = ctk.CTk()
            self.window.title(f"🛡️ Hệ Thống Bảo Vệ Thuế - Cloud Edition - {MACHINE_ID}")
            self.window.geometry("1200x800")
            self.window.configure(fg_color="#0d1117")
            
            # Set modern theme
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")
            
            # Variables
            self.enterprise_var = ctk.StringVar()
            self.status_text = ctk.StringVar(value="🔄 Đang tải dữ liệu hệ thống...")
            
            # Window icon and properties
            self.window.resizable(True, True)
            self.window.minsize(1000, 600)
            
            self.setup_ui()
            self.setup_welcome_screen()
            self.refresh_data()
            
        def setup_ui(self):
            # Main frame
            main_frame = ctk.CTkFrame(self.window, fg_color="#1a1a1a")
            main_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Title
            title = ctk.CTkLabel(main_frame, 
                               text="🛡️ HỆ THỐNG BẢO VỆ TÀI LIỆU THUẾ - CLOUD EDITION", 
                               font=ctk.CTkFont(size=24, weight="bold"),
                               text_color="#00ff88")
            title.pack(pady=(0, 20))
            
            # Status bar
            status_frame = ctk.CTkFrame(main_frame, height=40)
            status_frame.pack(fill="x", padx=5, pady=(0, 10))
            
            status_label = ctk.CTkLabel(status_frame, 
                                      textvariable=self.status_text,
                                      font=ctk.CTkFont(size=12))
            status_label.pack(side="left", padx=10, pady=10)
            
            # Refresh button
            refresh_btn = ctk.CTkButton(status_frame, 
                                      text="🔄 Làm Mới", 
                                      command=self.refresh_data, 
                                      width=100)
            refresh_btn.pack(side="right", padx=10, pady=5)
            
            # Tabs
            self.tabview = ctk.CTkTabview(main_frame)
            self.tabview.pack(fill="both", expand=True, padx=5)
            
            # Tab 1: Doanh Nghiệp
            enterprises_tab = self.tabview.add("🏢 Quản Lý Doanh Nghiệp")
            self.setup_enterprises_tab(enterprises_tab)
            
            # Tab 2: Đồng Bộ Cloud
            sync_tab = self.tabview.add("☁️ Đồng Bộ Cloud")
            self.setup_sync_tab(sync_tab)
            
            # Tab 3: Telegram Bot
            telegram_tab = self.tabview.add("🤖 Telegram Bot")
            self.setup_telegram_tab(telegram_tab)
            
            # Tab 4: Nhật Ký
            logs_tab = self.tabview.add("📊 Nhật Ký & Logs")
            self.setup_logs_tab(logs_tab)
            
            # Tab 5: Kiểm Thử Tính Năng
            testing_tab = self.tabview.add("🧪 Kiểm Thử Tính Năng")
            self.setup_testing_tab(testing_tab)
            
            # Tab 6: Hướng Dẫn
            guide_tab = self.tabview.add("❓ Hướng Dẫn")
            self.setup_guide_tab(guide_tab)
            
        def setup_welcome_screen(self):
            """Setup welcome overlay for first-time users."""
            pass  # Will implement if needed
            
        def setup_enterprises_tab(self, parent):
            # Create scrollable container for the whole tab
            scroll_container = ctk.CTkScrollableFrame(parent)
            scroll_container.pack(fill="both", expand=True, padx=5, pady=5)
            
            # Add enterprise frame
            add_frame = ctk.CTkFrame(scroll_container, height=150)
            add_frame.pack(fill="x", padx=5, pady=5)
            add_frame.pack_propagate(False)
            
            ctk.CTkLabel(add_frame, text="➕ THÊM DOANH NGHIỆP MỚI", 
                        font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
            
            entry_frame = ctk.CTkFrame(add_frame, fg_color="transparent")
            entry_frame.pack(fill="x", padx=20)
            
            self.ent_id_entry = ctk.CTkEntry(entry_frame, placeholder_text="🏷️ Mã Doanh Nghiệp (VD: VN001)")
            self.ent_id_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
            
            self.ent_name_entry = ctk.CTkEntry(entry_frame, placeholder_text="🏢 Tên Công Ty")
            self.ent_name_entry.pack(side="left", fill="x", expand=True, padx=5)
            
            self.ent_admin_entry = ctk.CTkEntry(entry_frame, placeholder_text="👤 Email Admin")
            self.ent_admin_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
            
            add_btn = ctk.CTkButton(add_frame, text="➕ Thêm Doanh Nghiệp", 
                                  command=self.add_enterprise)
            add_btn.pack(pady=10)
            
            # Enterprises list
            list_frame = ctk.CTkFrame(scroll_container)
            list_frame.pack(fill="x", padx=5, pady=5)
            
            ctk.CTkLabel(list_frame, text="📋 DANH SÁCH DOANH NGHIỆP ĐÃ ĐĂNG KÝ", 
                        font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
            
            # Create display using frame
            self.enterprises_text = ctk.CTkTextbox(list_frame, height=200)
            self.enterprises_text.pack(fill="x", padx=10, pady=10)
            
            # Add XML section - Make it more visible
            xml_section = ctk.CTkFrame(list_frame, height=100, fg_color="#2d3748")
            xml_section.pack(fill="x", padx=10, pady=10)
            xml_section.pack_propagate(False)
            
            # XML section header
            ctk.CTkLabel(xml_section, text="📄 QUẢN LÝ FILE XML BẢO VỆ", 
                        font=ctk.CTkFont(size=14, weight="bold"),
                        text_color="#e53e3e").pack(pady=(5, 0))
            
            # XML controls
            xml_controls = ctk.CTkFrame(xml_section, fg_color="transparent")
            xml_controls.pack(fill="x", padx=15, pady=5)
            
            # Enterprise dropdown
            self.enterprise_combo = ctk.CTkComboBox(xml_controls, 
                                                  variable=self.enterprise_var,
                                                  values=["📋 Chọn Doanh Nghiệp"],
                                                  width=200)
            self.enterprise_combo.pack(side="left", padx=(0, 10))
            
            # Add XML button
            xml_btn = ctk.CTkButton(xml_controls, 
                                  text="📄 Thêm File XML Bảo Vệ", 
                                  command=self.add_xml_file,
                                  width=180,
                                  fg_color="#e53e3e",
                                  hover_color="#c53030")
            xml_btn.pack(side="left", padx=5)
            
            # Help text
            help_label = ctk.CTkLabel(xml_controls,
                                    text="💡 Chọn file XML gốc/hợp pháp của doanh nghiệp",
                                    font=ctk.CTkFont(size=11),
                                    text_color="#a0aec0")
            help_label.pack(side="left", padx=(15, 0))
            
            # View details button
            view_btn = ctk.CTkButton(xml_controls,
                                   text="👁️ Xem Chi Tiết File",
                                   command=self.view_xml_details,
                                   width=140,
                                   fg_color="#4299e1",
                                   hover_color="#3182ce")
            view_btn.pack(side="right", padx=(10, 0))
            
        def setup_sync_tab(self, parent):
            # Cloud config
            config_frame = ctk.CTkFrame(parent, height=200)
            config_frame.pack(fill="x", padx=5, pady=5)
            config_frame.pack_propagate(False)
            
            ctk.CTkLabel(config_frame, text="Cloud Configuration", 
                        font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
            
            # Provider selection
            provider_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
            provider_frame.pack(fill="x", padx=20, pady=5)
            
            ctk.CTkLabel(provider_frame, text="Provider:").pack(side="left")
            self.provider_var = ctk.StringVar(value="github")
            provider_combo = ctk.CTkComboBox(provider_frame, variable=self.provider_var,
                                           values=["github", "google_drive", "dropbox"])
            provider_combo.pack(side="left", padx=10)
            
            # GitHub settings
            github_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
            github_frame.pack(fill="x", padx=20, pady=5)
            
            self.github_token_entry = ctk.CTkEntry(github_frame, placeholder_text="GitHub Token")
            self.github_token_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
            
            self.github_repo_entry = ctk.CTkEntry(github_frame, placeholder_text="owner/repo")
            self.github_repo_entry.pack(side="left", fill="x", expand=True, padx=5)
            
            save_config_btn = ctk.CTkButton(config_frame, text="Save Config", 
                                          command=self.save_cloud_config)
            save_config_btn.pack(pady=10)
            
            # Sync controls
            sync_frame = ctk.CTkFrame(parent)
            sync_frame.pack(fill="both", expand=True, padx=5, pady=5)
            
            ctk.CTkLabel(sync_frame, text="Sync Operations", 
                        font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
            
            btn_frame = ctk.CTkFrame(sync_frame, fg_color="transparent")
            btn_frame.pack(pady=10)
            
            ctk.CTkButton(btn_frame, text="Manual Sync", 
                         command=self.manual_sync).pack(side="left", padx=5)
            
            ctk.CTkButton(btn_frame, text="View Sync History", 
                         command=self.view_sync_history).pack(side="left", padx=5)
            
            # Sync status
            self.sync_status_text = ctk.CTkTextbox(sync_frame, height=200)
            self.sync_status_text.pack(fill="both", expand=True, padx=10, pady=10)
            
        def setup_telegram_tab(self, parent):
            # Telegram setup
            setup_frame = ctk.CTkFrame(parent, height=200)
            setup_frame.pack(fill="x", padx=5, pady=5)
            setup_frame.pack_propagate(False)
            
            ctk.CTkLabel(setup_frame, text="Telegram Bot Setup", 
                        font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
            
            token_frame = ctk.CTkFrame(setup_frame, fg_color="transparent")
            token_frame.pack(fill="x", padx=20, pady=5)
            
            self.bot_token_entry = ctk.CTkEntry(token_frame, placeholder_text="Bot Token")
            self.bot_token_entry.pack(fill="x", padx=(0, 10))
            
            chat_frame = ctk.CTkFrame(setup_frame, fg_color="transparent")
            chat_frame.pack(fill="x", padx=20, pady=5)
            
            self.chat_ids_entry = ctk.CTkEntry(chat_frame, placeholder_text="Authorized Chat IDs (comma separated)")
            self.chat_ids_entry.pack(fill="x")
            
            setup_btn = ctk.CTkButton(setup_frame, text="Setup Bot", 
                                    command=self.setup_telegram)
            setup_btn.pack(pady=10)
            
            # Bot status
            status_frame = ctk.CTkFrame(parent)
            status_frame.pack(fill="both", expand=True, padx=5, pady=5)
            
            ctk.CTkLabel(status_frame, text="Bot Status", 
                        font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
            
            self.telegram_status_text = ctk.CTkTextbox(status_frame)
            self.telegram_status_text.pack(fill="both", expand=True, padx=10, pady=10)
            
        def setup_logs_tab(self, parent):
            ctk.CTkLabel(parent, text="System Logs", 
                        font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
            
            self.logs_text = ctk.CTkTextbox(parent)
            self.logs_text.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Log controls
            log_controls = ctk.CTkFrame(parent, height=50)
            log_controls.pack(fill="x", padx=10, pady=5)
            
            ctk.CTkButton(log_controls, text="Refresh Logs", 
                         command=self.refresh_logs).pack(side="left", padx=5, pady=10)
            
            ctk.CTkButton(log_controls, text="Clear Logs", 
                         command=self.clear_logs).pack(side="left", padx=5, pady=10)
            
        def refresh_data(self):
            """Refresh all data."""
            try:
                # Update status
                conn = sqlite3.connect(str(ENTERPRISE_DB))
                cursor = conn.execute('SELECT COUNT(DISTINCT enterprise_id), COUNT(*) FROM xml_cloud_warehouse')
                ent_count, file_count = cursor.fetchone() or (0, 0)
                conn.close()
                
                self.status_text.set(f"🏢 Doanh nghiệp: {ent_count} | 📁 File bảo vệ: {file_count} | 💻 Máy: {MACHINE_ID}")
                
                # Refresh enterprises list
                self.refresh_enterprises()
                
                # Refresh logs
                self.refresh_logs()
                
            except Exception as e:
                logging.error(f"Refresh data error: {e}")
                
        def refresh_enterprises(self):
            """Refresh enterprises list."""
            try:
                conn = sqlite3.connect(str(ENTERPRISE_DB))
                cursor = conn.execute('''
                    SELECT e.enterprise_id, e.enterprise_name, e.admin_contact,
                           COUNT(w.id) as file_count,
                           MAX(w.last_updated) as last_activity
                    FROM enterprises e
                    LEFT JOIN xml_cloud_warehouse w ON e.enterprise_id = w.enterprise_id
                    GROUP BY e.enterprise_id
                    ORDER BY e.enterprise_name
                ''')
                
                enterprises = cursor.fetchall()
                conn.close()
                
                # Update text display
                self.enterprises_text.delete("1.0", "end")
                
                if enterprises:
                    text = "Mã DN        | Tên Doanh Nghiệp    | Quản Trị       | Files | Hoạt Động Cuối\n"
                    text += "=" * 80 + "\n"
                    
                    enterprise_names = []
                    for ent_id, name, admin, files, last_act in enterprises:
                        enterprise_names.append(ent_id)
                        last_act = last_act or "Never"
                        text += f"{ent_id[:15]:<15} | {name[:20]:<20} | {admin[:15]:<15} | {files:>5} | {last_act[:15]:<15}\n"
                    
                    self.enterprises_text.insert("1.0", text)
                    
                    # Update dropdown
                    if hasattr(self, 'enterprise_combo'):
                        dropdown_values = ["📋 Chọn Doanh Nghiệp"] + enterprise_names
                        self.enterprise_combo.configure(values=dropdown_values)
                else:
                    self.enterprises_text.insert("1.0", "📝 Chưa có doanh nghiệp nào được đăng ký.\n\n💡 Hãy thêm doanh nghiệp đầu tiên ở phía trên!")
                    
            except Exception as e:
                logging.error(f"Refresh enterprises error: {e}")
                
        def add_enterprise(self):
            """Add new enterprise."""
            ent_id = self.ent_id_entry.get().strip()
            ent_name = self.ent_name_entry.get().strip()
            admin = self.ent_admin_entry.get().strip()
            
            if not ent_id or not ent_name:
                messagebox.showerror("Lỗi", "Vui lòng nhập đầy đủ Mã DN và Tên Công Ty!")
                return
                
            if add_enterprise(ent_id, ent_name, admin):
                messagebox.showinfo("Thành Công", f"✅ Đã thêm doanh nghiệp {ent_id} - {ent_name}")
                self.ent_id_entry.delete(0, "end")
                self.ent_name_entry.delete(0, "end")
                self.ent_admin_entry.delete(0, "end")
                self.refresh_enterprises()
            else:
                messagebox.showerror("Lỗi", "❌ Không thể thêm doanh nghiệp. Kiểm tra lại thông tin!")
                
        def add_xml_file(self):
            """Add XML files to warehouse with multiple selection options."""
            enterprise_id = self.enterprise_var.get()
            if not enterprise_id or "Chọn Doanh Nghiệp" in enterprise_id:
                messagebox.showerror("Lỗi", "⚠️ Vui lòng chọn doanh nghiệp trước!")
                return
            
            # Create selection dialog
            selection_window = ctk.CTkToplevel(self.window)
            selection_window.title("📄 Chọn Cách Thêm File XML")
            selection_window.geometry("400x250")
            selection_window.resizable(False, False)
            selection_window.transient(self.window)
            selection_window.grab_set()
            
            # Center the window
            selection_window.update_idletasks()
            x = (selection_window.winfo_screenwidth() - 400) // 2
            y = (selection_window.winfo_screenheight() - 250) // 2
            selection_window.geometry(f"400x250+{x}+{y}")
            
            # Title
            ctk.CTkLabel(selection_window, 
                        text="📄 CHỌN CÁCH THÊM FILE XML",
                        font=ctk.CTkFont(size=16, weight="bold")).pack(pady=20)
            
            # Option 1: Single file
            btn1 = ctk.CTkButton(selection_window,
                               text="📄 Chọn 1 File XML",
                               width=300, height=40,
                               command=lambda: self.select_single_file(enterprise_id, selection_window))
            btn1.pack(pady=10)
            
            # Option 2: Multiple files
            btn2 = ctk.CTkButton(selection_window,
                               text="📄📄 Chọn Nhiều File XML (Ctrl+A)",
                               width=300, height=40,
                               fg_color="#e53e3e", hover_color="#c53030",
                               command=lambda: self.select_multiple_files(enterprise_id, selection_window))
            btn2.pack(pady=10)
            
            # Option 3: Folder
            btn3 = ctk.CTkButton(selection_window,
                               text="📁 Chọn Cả Thư Mục XML",
                               width=300, height=40,
                               fg_color="#38a169", hover_color="#2f855a",
                               command=lambda: self.select_folder(enterprise_id, selection_window))
            btn3.pack(pady=10)
            
            # Cancel button
            ctk.CTkButton(selection_window,
                        text="❌ Hủy",
                        width=100,
                        fg_color="#718096", hover_color="#4a5568",
                        command=selection_window.destroy).pack(pady=10)
        
        def select_single_file(self, enterprise_id, parent_window):
            """Select single XML file."""
            parent_window.destroy()
            
            file_path = filedialog.askopenfilename(
                title="🔍 Chọn 1 File XML Thuế Gốc",
                filetypes=[("File XML", "*.xml"), ("Tất cả file", "*.*")]
            )
            
            if file_path:
                self.process_xml_file(enterprise_id, file_path)
        
        def select_multiple_files(self, enterprise_id, parent_window):
            """Select multiple XML files."""
            parent_window.destroy()
            
            file_paths = filedialog.askopenfilenames(
                title="🔍 Chọn Nhiều File XML (Ctrl+A để chọn tất cả)",
                filetypes=[("File XML", "*.xml"), ("Tất cả file", "*.*")]
            )
            
            if file_paths:
                success_count = 0
                total_count = len(file_paths)
                
                for file_path in file_paths:
                    if self.process_xml_file(enterprise_id, file_path, show_individual_message=False):
                        success_count += 1
                
                # Show summary
                messagebox.showinfo("Kết Quả", 
                    f"✅ Đã thêm {success_count}/{total_count} file XML vào kho bảo vệ!\n\n" +
                    f"📊 Thành công: {success_count} file\n" +
                    f"❌ Thất bại: {total_count - success_count} file")
                self.refresh_data()
        
        def select_folder(self, enterprise_id, parent_window):
            """Select folder containing XML files."""
            parent_window.destroy()
            
            folder_path = filedialog.askdirectory(
                title="📁 Chọn Thư Mục Chứa File XML"
            )
            
            if folder_path:
                # Find all XML files in folder and subfolders
                xml_files = []
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        if file.lower().endswith('.xml'):
                            xml_files.append(os.path.join(root, file))
                
                if not xml_files:
                    messagebox.showwarning("Cảnh Báo", "❌ Không tìm thấy file XML nào trong thư mục này!")
                    return
                
                success_count = 0
                
                for xml_file in xml_files:
                    if self.process_xml_file(enterprise_id, xml_file, show_individual_message=False):
                        success_count += 1
                
                # Show summary
                messagebox.showinfo("Kết Quả", 
                    f"✅ Quét thư mục: {os.path.basename(folder_path)}\n\n" +
                    f"📊 Tìm thấy: {len(xml_files)} file XML\n" +
                    f"✅ Thêm thành công: {success_count} file\n" +
                    f"❌ Thất bại: {len(xml_files) - success_count} file")
                self.refresh_data()
        
        def process_xml_file(self, enterprise_id, file_path, show_individual_message=True):
            """Process individual XML file."""
            try:
                if add_xml_to_cloud_warehouse(enterprise_id, file_path):
                    if show_individual_message:
                        messagebox.showinfo("Thành Công", f"✅ Đã thêm file XML vào kho bảo vệ!\n📁 File: {os.path.basename(file_path)}")
                        self.refresh_data()
                    return True
                else:
                    if show_individual_message:
                        messagebox.showerror("Lỗi", f"❌ Không thể thêm file XML!\n📁 File: {os.path.basename(file_path)}")
                    return False
            except Exception as e:
                if show_individual_message:
                    messagebox.showerror("Lỗi", f"❌ Lỗi xử lý file!\n📁 File: {os.path.basename(file_path)}\n🔍 Chi tiết: {str(e)}")
                return False
        
        def view_xml_details(self):
            """Xem chi tiết file XML trong warehouse."""
            enterprise_id = self.enterprise_var.get()
            if not enterprise_id or "Chọn Doanh Nghiệp" in enterprise_id:
                messagebox.showwarning("Cảnh Báo", "⚠️ Vui lòng chọn doanh nghiệp để xem chi tiết!")
                return
            
            # Create details window
            details_window = ctk.CTkToplevel(self.window)
            details_window.title(f"📄 Chi Tiết File XML - {enterprise_id}")
            details_window.geometry("800x600")
            details_window.transient(self.window)
            details_window.grab_set()
            
            # Center window
            details_window.update_idletasks()
            x = (details_window.winfo_screenwidth() - 800) // 2
            y = (details_window.winfo_screenheight() - 600) // 2
            details_window.geometry(f"800x600+{x}+{y}")
            
            # Title
            title = ctk.CTkLabel(details_window,
                               text=f"📊 CHI TIẾT FILE XML - DOANH NGHIỆP: {enterprise_id}",
                               font=ctk.CTkFont(size=16, weight="bold"))
            title.pack(pady=10)
            
            # Get data from database
            try:
                conn = sqlite3.connect(str(ENTERPRISE_DB))
                cursor = conn.execute('''
                    SELECT mst, company_name, filename, file_hash, created_date, last_updated
                    FROM xml_cloud_warehouse 
                    WHERE enterprise_id = ?
                    ORDER BY mst, filename
                ''', (enterprise_id,))
                
                xml_files = cursor.fetchall()
                conn.close()
                
                if not xml_files:
                    ctk.CTkLabel(details_window,
                               text="📝 Chưa có file XML nào trong warehouse",
                               font=ctk.CTkFont(size=14)).pack(pady=50)
                    return
                
                # Create scrollable frame
                scroll_frame = ctk.CTkScrollableFrame(details_window)
                scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)
                
                # Stats header
                stats_frame = ctk.CTkFrame(scroll_frame, height=60)
                stats_frame.pack(fill="x", pady=(0, 10))
                stats_frame.pack_propagate(False)
                
                total_files = len(xml_files)
                unique_mst = len(set([f[0] for f in xml_files]))
                
                stats_text = f"📊 Tổng: {total_files} file | 🏢 MST: {unique_mst} công ty khác nhau"
                ctk.CTkLabel(stats_frame, text=stats_text,
                           font=ctk.CTkFont(size=14, weight="bold")).pack(pady=15)
                
                # Group by MST
                mst_groups = {}
                for mst, company, filename, hash_val, created, updated in xml_files:
                    if mst not in mst_groups:
                        mst_groups[mst] = []
                    mst_groups[mst].append((company, filename, hash_val, created, updated))
                
                # Display each MST group
                for mst, files in mst_groups.items():
                    # MST header
                    mst_frame = ctk.CTkFrame(scroll_frame, fg_color="#2d3748")
                    mst_frame.pack(fill="x", pady=(10, 5))
                    
                    company_name = files[0][0] if files else "Unknown"
                    header_text = f"🏢 MST: {mst} | {company_name} ({len(files)} file)"
                    
                    mst_header = ctk.CTkLabel(mst_frame, text=header_text,
                                            font=ctk.CTkFont(size=13, weight="bold"),
                                            text_color="#e2e8f0")
                    mst_header.pack(pady=10)
                    
                    # Files list
                    files_frame = ctk.CTkFrame(scroll_frame)
                    files_frame.pack(fill="x", pady=(0, 5))
                    
                    # Create table-like display
                    for i, (company, filename, hash_val, created, updated) in enumerate(files):
                        file_row = ctk.CTkFrame(files_frame, fg_color="transparent" if i % 2 == 0 else "#1a202c")
                        file_row.pack(fill="x", padx=5, pady=1)
                        
                        # File info
                        file_info = f"📄 {filename[:40]}{'...' if len(filename) > 40 else ''}"
                        date_info = f"📅 {created[:16] if created else 'N/A'}"
                        hash_info = f"🔐 {hash_val[:8]}..." if hash_val else "N/A"
                        
                        info_text = f"{file_info} | {date_info} | {hash_info}"
                        
                        file_label = ctk.CTkLabel(file_row, text=info_text,
                                                font=ctk.CTkFont(size=11),
                                                anchor="w")
                        file_label.pack(side="left", fill="x", expand=True, padx=10, pady=5)
                        
                        # Delete button
                        del_btn = ctk.CTkButton(file_row,
                                              text="🗑️",
                                              width=30, height=25,
                                              fg_color="#e53e3e",
                                              hover_color="#c53030",
                                              command=lambda f=filename, m=mst, e=enterprise_id: self.delete_xml_file(e, m, f, details_window))
                        del_btn.pack(side="right", padx=5, pady=2)
                
                # Control buttons
                btn_frame = ctk.CTkFrame(details_window, height=50)
                btn_frame.pack(fill="x", padx=20, pady=10)
                btn_frame.pack_propagate(False)
                
                # Clear all button
                clear_btn = ctk.CTkButton(btn_frame,
                                        text="🗑️ Xóa Tất Cả File",
                                        width=150,
                                        fg_color="#dc2626",
                                        hover_color="#b91c1c",
                                        command=lambda: self.clear_all_xml_files(enterprise_id, details_window))
                clear_btn.pack(side="left", padx=10, pady=10)
                
                # Refresh button
                refresh_btn = ctk.CTkButton(btn_frame,
                                          text="🔄 Làm Mới",
                                          width=100,
                                          command=lambda: self.refresh_xml_details(details_window, enterprise_id))
                refresh_btn.pack(side="left", padx=10, pady=10)
                
                # Close button
                ctk.CTkButton(btn_frame,
                            text="❌ Đóng",
                            width=80,
                            fg_color="#718096",
                            hover_color="#4a5568",
                            command=details_window.destroy).pack(side="right", padx=10, pady=10)
                
            except Exception as e:
                messagebox.showerror("Lỗi", f"❌ Không thể tải chi tiết file!\n🔍 Chi tiết: {str(e)}")
        
        def delete_xml_file(self, enterprise_id, mst, filename, parent_window):
            """Xóa 1 file XML khỏi warehouse."""
            if messagebox.askyesno("Xác Nhận", f"❓ Xóa file này khỏi warehouse?\n📄 File: {filename}\n🏢 MST: {mst}"):
                try:
                    conn = sqlite3.connect(str(ENTERPRISE_DB))
                    conn.execute('''
                        DELETE FROM xml_cloud_warehouse 
                        WHERE enterprise_id = ? AND mst = ? AND filename = ?
                    ''', (enterprise_id, mst, filename))
                    conn.commit()
                    conn.close()
                    
                    messagebox.showinfo("Thành Công", f"✅ Đã xóa file: {filename}")
                    self.refresh_xml_details(parent_window, enterprise_id)
                    self.refresh_data()  # Refresh main screen
                    
                except Exception as e:
                    messagebox.showerror("Lỗi", f"❌ Không thể xóa file!\n🔍 Chi tiết: {str(e)}")
        
        def clear_all_xml_files(self, enterprise_id, parent_window):
            """Xóa tất cả file XML của doanh nghiệp."""
            if messagebox.askyesno("Xác Nhận", f"⚠️ XÓA TẤT CẢ FILE XML của doanh nghiệp {enterprise_id}?\n\n❌ Hành động này KHÔNG THỂ HOÀN TÁC!"):
                try:
                    conn = sqlite3.connect(str(ENTERPRISE_DB))
                    cursor = conn.execute('SELECT COUNT(*) FROM xml_cloud_warehouse WHERE enterprise_id = ?', (enterprise_id,))
                    count = cursor.fetchone()[0]
                    
                    conn.execute('DELETE FROM xml_cloud_warehouse WHERE enterprise_id = ?', (enterprise_id,))
                    conn.commit()
                    conn.close()
                    
                    messagebox.showinfo("Thành Công", f"✅ Đã xóa {count} file XML khỏi warehouse!")
                    parent_window.destroy()
                    self.refresh_data()  # Refresh main screen
                    
                except Exception as e:
                    messagebox.showerror("Lỗi", f"❌ Không thể xóa file!\n🔍 Chi tiết: {str(e)}")
        
        def refresh_xml_details(self, details_window, enterprise_id):
            """Refresh chi tiết window."""
            details_window.destroy()
            self.view_xml_details()
                    
        def save_cloud_config(self):
            """Save cloud configuration."""
            try:
                config = load_cloud_config()
                
                config["cloud_provider"] = self.provider_var.get()
                
                if self.github_token_entry.get():
                    config["github"]["token"] = self.github_token_entry.get()
                
                if self.github_repo_entry.get():
                    repo_parts = self.github_repo_entry.get().split("/")
                    if len(repo_parts) == 2:
                        config["github"]["owner"] = repo_parts[0]
                        config["github"]["repo"] = repo_parts[1]
                
                save_cloud_config(config)
                messagebox.showinfo("Success", "Cloud configuration saved!")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save config: {e}")
                
        def manual_sync(self):
            """Trigger manual sync."""
            self.sync_status_text.insert("end", f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting manual sync...")
            
            success = sync_to_cloud()
            
            if success:
                self.sync_status_text.insert("end", "\n✅ Sync completed successfully!")
            else:
                self.sync_status_text.insert("end", "\n❌ Sync failed!")
                
            self.sync_status_text.see("end")
            
        def view_sync_history(self):
            """View sync history."""
            try:
                conn = sqlite3.connect(str(ENTERPRISE_DB))
                cursor = conn.execute('''
                    SELECT sync_date, sync_type, sync_status, enterprise_id, details
                    FROM sync_history
                    ORDER BY sync_date DESC
                    LIMIT 20
                ''')
                
                history = cursor.fetchall()
                conn.close()
                
                self.sync_status_text.delete("1.0", "end")
                
                if history:
                    text = "Recent Sync History:\n" + "="*50 + "\n"
                    for date, sync_type, status, ent_id, details in history:
                        text += f"[{date[:19]}] {sync_type} - {status} ({ent_id}) - {details}\n"
                else:
                    text = "No sync history available."
                    
                self.sync_status_text.insert("1.0", text)
                
            except Exception as e:
                self.sync_status_text.insert("1.0", f"Error loading sync history: {e}")
                
        def setup_telegram(self):
            """Setup Telegram bot."""
            bot_token = self.bot_token_entry.get().strip()
            chat_ids_text = self.chat_ids_entry.get().strip()
            
            if not bot_token:
                messagebox.showerror("Error", "Bot token is required!")
                return
                
            try:
                chat_ids = [int(id.strip()) for id in chat_ids_text.split(",") if id.strip()]
                
                if not chat_ids:
                    messagebox.showerror("Error", "At least one chat ID is required!")
                    return
                    
                setup_telegram_bot(bot_token, chat_ids)
                messagebox.showinfo("Success", "Telegram bot configured successfully!")
                
                self.refresh_telegram_status()
                
            except ValueError:
                messagebox.showerror("Error", "Invalid chat ID format!")
            except Exception as e:
                messagebox.showerror("Error", f"Setup failed: {e}")
                
        def refresh_telegram_status(self):
            """Refresh Telegram status."""
            try:
                config = load_cloud_config()
                telegram_config = config.get("telegram", {})
                
                status_text = "Telegram Bot Status:\n" + "="*30 + "\n"
                
                if telegram_config.get("enabled", False):
                    status_text += "✅ Bot: Enabled\n"
                    status_text += f"🔑 Token: {telegram_config.get('bot_token', '')[:20]}...\n"
                    status_text += f"👥 Authorized Users: {telegram_config.get('authorized_users', [])}\n"
                else:
                    status_text += "❌ Bot: Disabled\n"
                    
                self.telegram_status_text.delete("1.0", "end")
                self.telegram_status_text.insert("1.0", status_text)
                
            except Exception as e:
                self.telegram_status_text.delete("1.0", "end")
                self.telegram_status_text.insert("1.0", f"Error loading status: {e}")
                
        def refresh_logs(self):
            """Refresh system logs."""
            try:
                if LOG_FILE.exists():
                    with open(LOG_FILE, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    # Show last 100 lines
                    recent_lines = lines[-100:]
                    log_text = "".join(recent_lines)
                    
                    self.logs_text.delete("1.0", "end")
                    self.logs_text.insert("1.0", log_text)
                    self.logs_text.see("end")
                else:
                    self.logs_text.delete("1.0", "end")
                    self.logs_text.insert("1.0", "No log file found.")
                    
            except Exception as e:
                self.logs_text.delete("1.0", "end")
                self.logs_text.insert("1.0", f"Error reading logs: {e}")
                
        def clear_logs(self):
            """Clear system logs."""
            try:
                if messagebox.askyesno("Confirm", "Are you sure you want to clear all logs?"):
                    with open(LOG_FILE, 'w', encoding='utf-8') as f:
                        f.write("")
                    self.refresh_logs()
                    messagebox.showinfo("Success", "Logs cleared!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear logs: {e}")
            
        def setup_testing_tab(self, parent):
            """Tab kiểm thử tính năng với giao diện trực quan."""
            container = ctk.CTkScrollableFrame(parent, fg_color="transparent")
            container.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Header
            header_frame = ctk.CTkFrame(container, fg_color="#21262d", corner_radius=15, height=80)
            header_frame.pack(fill="x", padx=10, pady=(0, 20))
            header_frame.pack_propagate(False)
            
            ctk.CTkLabel(header_frame, 
                        text="🧪 KIỂM THỬ & GIÁM SÁT TÍNH NĂNG HỆ THỐNG", 
                        font=ctk.CTkFont(size=18, weight="bold"),
                        text_color="#58a6ff").pack(pady=10)
            
            ctk.CTkLabel(header_frame, 
                        text="Kiểm tra trạng thái và test các tính năng bảo vệ thuế", 
                        font=ctk.CTkFont(size=12),
                        text_color="#7d8590").pack(pady=(0, 10))
            
            # === SYSTEM STATUS OVERVIEW ===
            status_frame = ctk.CTkFrame(container, fg_color="#0d1117", corner_radius=15)
            status_frame.pack(fill="x", padx=10, pady=(0, 15))
            
            ctk.CTkLabel(status_frame, 
                        text="📊 TRẠNG THÁI HỆ THỐNG", 
                        font=ctk.CTkFont(size=14, weight="bold"),
                        text_color="#58a6ff").pack(pady=(15, 10))
            
            # Status indicators in grid
            status_grid = ctk.CTkFrame(status_frame, fg_color="transparent")
            status_grid.pack(fill="x", padx=15, pady=(0, 15))
            
            # Row 1: Core Protection
            protection_frame = ctk.CTkFrame(status_grid, fg_color="#21262d", corner_radius=10)
            protection_frame.pack(fill="x", pady=(0, 10))
            
            ctk.CTkLabel(protection_frame, text="🛡️ Bảo Vệ Real-time", 
                        font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=15, pady=10)
            
            self.protection_status = ctk.CTkLabel(protection_frame, text="⏳ Đang kiểm tra...", 
                                                text_color="#f85149")
            self.protection_status.pack(side="right", padx=15, pady=10)
            
            # Row 2: File Monitoring
            monitor_frame = ctk.CTkFrame(status_grid, fg_color="#21262d", corner_radius=10)
            monitor_frame.pack(fill="x", pady=(0, 10))
            
            ctk.CTkLabel(monitor_frame, text="👁️ Giám Sát File", 
                        font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=15, pady=10)
            
            self.monitor_status = ctk.CTkLabel(monitor_frame, text="⏳ Đang kiểm tra...", 
                                             text_color="#f85149")
            self.monitor_status.pack(side="right", padx=15, pady=10)
            
            # Row 3: Database
            db_frame = ctk.CTkFrame(status_grid, fg_color="#21262d", corner_radius=10)
            db_frame.pack(fill="x", pady=(0, 10))
            
            ctk.CTkLabel(db_frame, text="💾 Database Cloud", 
                        font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=15, pady=10)
            
            self.db_status = ctk.CTkLabel(db_frame, text="⏳ Đang kiểm tra...", 
                                        text_color="#f85149")
            self.db_status.pack(side="right", padx=15, pady=10)
            
            # === FEATURE TESTING SECTION ===
            testing_frame = ctk.CTkFrame(container, fg_color="#0d1117", corner_radius=15)
            testing_frame.pack(fill="x", padx=10, pady=(0, 15))
            
            ctk.CTkLabel(testing_frame, 
                        text="🧪 KIỂM THỬ TÍNH NĂNG", 
                        font=ctk.CTkFont(size=14, weight="bold"),
                        text_color="#58a6ff").pack(pady=(15, 10))
            
            # Test buttons grid
            tests_grid = ctk.CTkFrame(testing_frame, fg_color="transparent")
            tests_grid.pack(fill="x", padx=15, pady=(0, 15))
            
            # Test 1: XML Detection
            test1_frame = ctk.CTkFrame(tests_grid, fg_color="#21262d", corner_radius=10)
            test1_frame.pack(fill="x", pady=(0, 8))
            
            ctk.CTkLabel(test1_frame, text="🔍 Test Phát Hiện XML", 
                        font=ctk.CTkFont(size=12)).pack(side="left", padx=15, pady=8)
            
            ctk.CTkButton(test1_frame, text="▶️ Chạy Test", width=100, height=28,
                         command=lambda: self.test_xml_detection(),
                         fg_color="#238636", hover_color="#2ea043").pack(side="right", padx=15, pady=8)
            
            # Test 2: Stealth Overwrite
            test2_frame = ctk.CTkFrame(tests_grid, fg_color="#21262d", corner_radius=10)
            test2_frame.pack(fill="x", pady=(0, 8))
            
            ctk.CTkLabel(test2_frame, text="👻 Test Ghi Đè Stealth", 
                        font=ctk.CTkFont(size=12)).pack(side="left", padx=15, pady=8)
            
            ctk.CTkButton(test2_frame, text="▶️ Chạy Test", width=100, height=28,
                         command=lambda: self.test_stealth_overwrite(),
                         fg_color="#1f6feb", hover_color="#388bfd").pack(side="right", padx=15, pady=8)
            
            # Test 3: Database Operations
            test3_frame = ctk.CTkFrame(tests_grid, fg_color="#21262d", corner_radius=10)
            test3_frame.pack(fill="x", pady=(0, 8))
            
            ctk.CTkLabel(test3_frame, text="💾 Test Database Cloud", 
                        font=ctk.CTkFont(size=12)).pack(side="left", padx=15, pady=8)
            
            ctk.CTkButton(test3_frame, text="▶️ Chạy Test", width=100, height=28,
                         command=lambda: self.test_database_operations(),
                         fg_color="#6f42c1", hover_color="#8250df").pack(side="right", padx=15, pady=8)
            
            # Test 4: Telegram Bot
            test4_frame = ctk.CTkFrame(tests_grid, fg_color="#21262d", corner_radius=10)
            test4_frame.pack(fill="x", pady=(0, 8))
            
            ctk.CTkLabel(test4_frame, text="🤖 Test Telegram Bot", 
                        font=ctk.CTkFont(size=12)).pack(side="left", padx=15, pady=8)
            
            ctk.CTkButton(test4_frame, text="▶️ Chạy Test", width=100, height=28,
                         command=lambda: self.test_telegram_bot(),
                         fg_color="#da7633", hover_color="#e85d2e").pack(side="right", padx=15, pady=8)
            
            # === LIVE MONITORING ===
            monitor_frame_live = ctk.CTkFrame(container, fg_color="#0d1117", corner_radius=15)
            monitor_frame_live.pack(fill="x", padx=10, pady=(0, 15))
            
            ctk.CTkLabel(monitor_frame_live, 
                        text="📈 GIÁM SÁT TRỰC TIẾP", 
                        font=ctk.CTkFont(size=14, weight="bold"),
                        text_color="#58a6ff").pack(pady=(15, 10))
            
            # Live stats
            stats_frame = ctk.CTkFrame(monitor_frame_live, fg_color="#21262d", corner_radius=10)
            stats_frame.pack(fill="x", padx=15, pady=(0, 15))
            
            self.stats_text = ctk.CTkTextbox(stats_frame, height=120, wrap="word",
                                           fg_color="#0d1117", text_color="#7d8590",
                                           font=ctk.CTkFont(family="Consolas", size=11))
            self.stats_text.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Control buttons
            control_frame = ctk.CTkFrame(container, fg_color="transparent")
            control_frame.pack(fill="x", padx=10, pady=(0, 10))
            
            ctk.CTkButton(control_frame, text="🔄 Refresh Status", 
                         command=self.refresh_all_status,
                         fg_color="#238636", hover_color="#2ea043").pack(side="left", padx=(0, 10))
            
            ctk.CTkButton(control_frame, text="🧹 Clear Logs", 
                         command=self.clear_test_logs,
                         fg_color="#f85149", hover_color="#da3633").pack(side="left", padx=(0, 10))
            
            ctk.CTkButton(control_frame, text="📊 Full System Scan", 
                         command=self.run_full_system_scan,
                         fg_color="#6f42c1", hover_color="#8250df").pack(side="right")
            
            # Initialize status check
            self.window.after(1000, self.refresh_all_status)
            
        def setup_guide_tab(self, parent):
            """Hướng dẫn sử dụng đầy đủ."""
            container = ctk.CTkScrollableFrame(parent, fg_color="transparent")
            container.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Header
            header_frame = ctk.CTkFrame(container, fg_color="#21262d", corner_radius=15, height=60)
            header_frame.pack(fill="x", padx=10, pady=(0, 20))
            header_frame.pack_propagate(False)
            
            ctk.CTkLabel(header_frame, 
                        text="📖 HƯỚNG DẪN SỬ DỤNG HỆ THỐNG BẢO VỆ THUẾ", 
                        font=ctk.CTkFont(size=18, weight="bold"),
                        text_color="#58a6ff").pack(pady=20)
            
            # Quick Start Guide
            quick_frame = ctk.CTkFrame(container, fg_color="#21262d", corner_radius=15)
            quick_frame.pack(fill="x", padx=10, pady=(0, 20))
            
            ctk.CTkLabel(quick_frame, 
                        text="🚀 BẮT ĐẦU NHANH", 
                        font=ctk.CTkFont(size=16, weight="bold"),
                        text_color="#7c3aed").pack(pady=(15, 10))
            
            quick_steps = ctk.CTkTextbox(quick_frame, height=200, font=ctk.CTkFont(size=12))
            quick_steps.pack(fill="x", padx=15, pady=(0, 15))
            
            quick_content = """🔥 CÁC BƯỚC CƠ BẢN:

1️⃣ THÊM DOANH NGHIỆP:
   • Vào tab "🏢 Quản Lý Doanh Nghiệp"
   • Nhập Mã DN (VD: VN001), Tên công ty, Email admin
   • Nhấn "➕ Thêm Doanh Nghiệp"

2️⃣ THÊM FILE XML BẢO VỆ:
   • Chọn doanh nghiệp từ dropdown
   • Nhấn "📄 Thêm File XML"
   • Chọn file XML thuế gốc (file đúng/hợp lệ)
   • Hệ thống sẽ tự động phân loại theo MST

3️⃣ BẬT BẢO VỆ:
   • Chạy file XMLWarehouse_Cloud.exe (chạy ngầm)
   • Hệ thống tự động bảo vệ toàn bộ máy tính
   • Khi có file giả → Thay thế ngay lập tức (<0.1s)"""
            quick_steps.insert("1.0", quick_content)
            quick_steps.configure(state="disabled")
            
            # Advanced Features
            advanced_frame = ctk.CTkFrame(container, fg_color="#21262d", corner_radius=15)
            advanced_frame.pack(fill="x", padx=10, pady=(0, 20))
            
            ctk.CTkLabel(advanced_frame, 
                        text="⚡ TÍNH NĂNG NÂNG CAO", 
                        font=ctk.CTkFont(size=16, weight="bold"),
                        text_color="#f85149").pack(pady=(15, 10))
            
            advanced_text = ctk.CTkTextbox(advanced_frame, height=250, font=ctk.CTkFont(size=12))
            advanced_text.pack(fill="x", padx=15, pady=(0, 15))
            
            advanced_content = """☁️ ĐỒNG BỘ CLOUD (GitHub):
   • Vào tab "☁️ Đồng Bộ Cloud"
   • Tạo GitHub repo private
   • Nhập Token & Repository
   • Tự động backup mỗi 5 phút

🤖 TELEGRAM BOT:
   • Tạo bot với @BotFather
   • Lấy Bot Token & Chat ID
   • Setup trong tab "🤖 Telegram Bot"
   • Điều khiển từ xa: /status /sync /logs /help

📊 GIÁM SÁT:
   • Tab "📊 Nhật Ký & Logs": Xem hoạt động
   • Telegram alerts: Cảnh báo real-time
   • Multi-machine: Triển khai nhiều máy"""
            advanced_text.insert("1.0", advanced_content)
            advanced_text.configure(state="disabled")
                
        def run(self):
            self.window.mainloop()
            
    # Initialize and run app
    generate_machine_id()
    create_enterprise_db()
    
    app = CloudControlApp()
    app.run()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--control':
        launch_cloud_control_panel()
    else:
        start_cloud_enterprise()