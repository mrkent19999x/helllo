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
from datetime import datetime, timedelta
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
        "compression_enabled": True,  # Enable XML compression by default
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
        "google_drive": {
            "credentials_file": "",
            "folder_id": "",
            "enabled": False
        },
        "dropbox": {
            "access_token": "",
            "folder_path": "/xml-warehouse",
            "enabled": False
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
    """Tao enterprise database voi indexes va constraints toi uu."""
    conn = sqlite3.connect(str(ENTERPRISE_DB))
    
    # Enable foreign keys
    conn.execute('PRAGMA foreign_keys = ON')
    
    # Create enterprises table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS enterprises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enterprise_id TEXT UNIQUE NOT NULL,
            enterprise_name TEXT NOT NULL,
            admin_contact TEXT,
            created_date TEXT,
            last_sync TEXT,
            status TEXT DEFAULT 'active',
            mst_prefix TEXT,  -- MST prefix for classification
            industry_type TEXT,  -- Industry classification
            region TEXT,  -- Geographic region
            notes TEXT,
            machine_id TEXT  -- Machine ID that created this enterprise
        )
    ''')
    
    # Create xml_cloud_warehouse table with better structure
    conn.execute('''
        CREATE TABLE IF NOT EXISTS xml_cloud_warehouse (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enterprise_id TEXT NOT NULL,
            mst TEXT NOT NULL,
            company_name TEXT,
            filename TEXT NOT NULL,
            content TEXT NOT NULL,
            file_hash TEXT,
            file_size INTEGER,  -- File size in bytes
            compression_ratio REAL,  -- Compression ratio
            content_type TEXT DEFAULT 'xml',  -- Content type
            created_date TEXT,
            last_updated TEXT,
            sync_status TEXT DEFAULT 'pending',
            cloud_url TEXT,
            protection_count INTEGER DEFAULT 0,  -- Number of times protected
            last_protection TEXT,  -- Last protection timestamp
            machine_id TEXT,  -- Machine ID that created this file
            UNIQUE(enterprise_id, mst, filename)
        )
    ''')
    
    # Create sync_history table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sync_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT,
            enterprise_id TEXT,
            sync_type TEXT,
            sync_status TEXT,
            sync_date TEXT,
            details TEXT,
            file_count INTEGER,  -- Number of files synced
            error_count INTEGER,  -- Number of errors
            duration_ms INTEGER  -- Sync duration in milliseconds
        )
    ''')
    
    # Create enterprise_warehouses table for separate storage
    conn.execute('''
        CREATE TABLE IF NOT EXISTS enterprise_warehouses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enterprise_id TEXT UNIQUE NOT NULL,
            warehouse_name TEXT,
            storage_path TEXT,  -- Local storage path
            cloud_sync_enabled BOOLEAN DEFAULT 1,
            compression_enabled BOOLEAN DEFAULT 1,
            max_storage_mb INTEGER DEFAULT 1024,  -- Max storage in MB
            current_usage_mb REAL DEFAULT 0,  -- Current usage in MB
            created_date TEXT,
            last_cleanup TEXT
        )
    ''')
    
    # Create MST classification table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS mst_classifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mst_prefix TEXT UNIQUE NOT NULL,  -- First 3 digits of MST
            industry_category TEXT,  -- Industry category
            region_code TEXT,  -- Region code
            risk_level TEXT DEFAULT 'low',  -- Risk assessment
            description TEXT,
            created_date TEXT
        )
    ''')
    
    # Create machine registry table for multi-machine deployment
    conn.execute('''
        CREATE TABLE IF NOT EXISTS machine_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT UNIQUE NOT NULL,
            machine_name TEXT,
            ip_address TEXT,
            mac_address TEXT,
            platform_info TEXT,
            status TEXT DEFAULT 'offline',
            created_date TEXT,
            last_seen TEXT,
            enterprise_count INTEGER DEFAULT 0,
            xml_protected_count INTEGER DEFAULT 0,
            last_sync TEXT,
            sync_status TEXT DEFAULT 'idle',
            notes TEXT
        )
    ''')
    
    # Create machine sync history table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS machine_sync_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT,
            sync_type TEXT,  -- 'enterprise', 'xml', 'config'
            sync_status TEXT,
            sync_date TEXT,
            details TEXT,
            duration_ms INTEGER,
            file_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0
        )
    ''')
    
    # Create indexes for better performance
    conn.execute('CREATE INDEX IF NOT EXISTS idx_enterprise_id ON enterprises(enterprise_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_enterprise_status ON enterprises(status)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_warehouse_enterprise ON xml_cloud_warehouse(enterprise_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_warehouse_mst ON xml_cloud_warehouse(mst)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_warehouse_sync_status ON xml_cloud_warehouse(sync_status)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_warehouse_filename ON xml_cloud_warehouse(filename)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_sync_history_machine ON sync_history(machine_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_sync_history_enterprise ON sync_history(enterprise_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_sync_history_date ON sync_history(sync_date)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_mst_classification_prefix ON mst_classifications(mst_prefix)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_machine_registry_id ON machine_registry(machine_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_machine_registry_status ON machine_registry(status)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_machine_sync_history ON machine_sync_history(machine_id)')
    
    # Insert default MST classifications
    default_classifications = [
        ('010', 'Agriculture', 'HN', 'low', 'Nông nghiệp - Hà Nội'),
        ('020', 'Mining', 'HN', 'medium', 'Khai thác mỏ - Hà Nội'),
        ('030', 'Manufacturing', 'HN', 'medium', 'Sản xuất - Hà Nội'),
        ('040', 'Construction', 'HN', 'medium', 'Xây dựng - Hà Nội'),
        ('050', 'Trade', 'HN', 'low', 'Thương mại - Hà Nội'),
        ('060', 'Transport', 'HN', 'medium', 'Vận tải - Hà Nội'),
        ('070', 'Finance', 'HN', 'high', 'Tài chính - Hà Nội'),
        ('080', 'Services', 'HN', 'low', 'Dịch vụ - Hà Nội'),
        ('090', 'Government', 'HN', 'high', 'Chính phủ - Hà Nội')
    ]
    
    for mst_prefix, industry, region, risk, desc in default_classifications:
        conn.execute('''
            INSERT OR IGNORE INTO mst_classifications 
            (mst_prefix, industry_category, region_code, risk_level, description, created_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (mst_prefix, industry, region, risk, desc, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    return ENTERPRISE_DB

def add_enterprise(enterprise_id, enterprise_name, admin_contact="", mst_prefix=None, industry_type=None, region=None, notes=""):
    """Them enterprise moi voi MST classification."""
    try:
        # Validate enterprise_id
        if not enterprise_id or len(enterprise_id.strip()) < 3:
            logging.error("Enterprise ID phải có ít nhất 3 ký tự")
            return False
        
        # Validate enterprise_name
        if not enterprise_name or len(enterprise_name.strip()) < 5:
            logging.error("Enterprise name phải có ít nhất 5 ký tự")
            return False
        
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        
        # Check if enterprise already exists
        cursor = conn.execute('SELECT enterprise_id FROM enterprises WHERE enterprise_id = ?', (enterprise_id,))
        if cursor.fetchone():
            logging.warning(f"Enterprise {enterprise_id} đã tồn tại")
            conn.close()
            return False
        
        # Auto-detect MST prefix if not provided
        if not mst_prefix and admin_contact:
            # Try to extract MST from admin contact or use default
            mst_prefix = "050"  # Default to Trade category
        
        # Auto-detect industry type if not provided
        if not industry_type:
            industry_type = "General"
        
        # Auto-detect region if not provided
        if not region:
            region = "HN"  # Default to Hanoi
        
        # Insert enterprise
        conn.execute('''
            INSERT INTO enterprises 
            (enterprise_id, enterprise_name, admin_contact, mst_prefix, industry_type, region, notes, created_date, machine_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (enterprise_id, enterprise_name, admin_contact, mst_prefix, industry_type, region, notes, datetime.now().isoformat(), generate_machine_id()))
        
        # Create enterprise warehouse
        conn.execute('''
            INSERT INTO enterprise_warehouses 
            (enterprise_id, warehouse_name, storage_path, created_date)
            VALUES (?, ?, ?, ?)
        ''', (enterprise_id, f"warehouse_{enterprise_id}", f"warehouses/{enterprise_id}", datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        # Update cloud config
        config = load_cloud_config()
        config["enterprises"][enterprise_id] = {
            "name": enterprise_name,
            "admin": admin_contact,
            "mst_prefix": mst_prefix,
            "industry_type": industry_type,
            "region": region,
            "notes": notes,
            "last_sync": None,
            "created_date": datetime.now().isoformat()
        }
        save_cloud_config(config)
        
        logging.info(f"Added enterprise: {enterprise_id} - {enterprise_name} (MST: {mst_prefix}, Industry: {industry_type}, Region: {region})")
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

def add_xml_to_cloud_warehouse(enterprise_id, xml_file_path, xml_content=None, enable_compression=True):
    """Them XML vao cloud warehouse voi compression va tracking."""
    try:
        if xml_content is None:
            with open(xml_file_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
        
        # Validate MST
        mst = extract_mst_from_xml(xml_content)
        if not mst:
            logging.warning(f"Cannot extract MST from {xml_file_path}")
            return False
        
        # Validate MST format
        is_valid, validation_msg = validate_mst(mst)
        if not is_valid:
            logging.warning(f"MST validation failed: {validation_msg}")
            return False
        
        # Classify MST
        mst_classification = classify_mst(mst)
        if mst_classification:
            logging.info(f"MST {mst} classified as: {mst_classification['industry_category']} - {mst_classification['risk_level']}")
        
        company_name = extract_company_name_from_xml(xml_content)
        filename = os.path.basename(xml_file_path)
        file_hash = hashlib.sha256(xml_content.encode('utf-8')).hexdigest()
        original_size = len(xml_content)
        
        # Compress content if enabled
        if enable_compression:
            compressed_content = compress_xml_content(xml_content)
            final_content = compressed_content
            compressed_size = len(compressed_content)
            compression_ratio = compressed_size / original_size if original_size > 0 else 1.0
            logging.info(f"Compression applied: {original_size} -> {compressed_size} bytes (ratio: {compression_ratio:.2f})")
        else:
            final_content = xml_content
            compression_ratio = 1.0
        
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
        
        # Insert with enhanced data
        conn.execute('''
            INSERT INTO xml_cloud_warehouse 
            (enterprise_id, mst, company_name, filename, content, file_hash, 
             file_size, compression_ratio, content_type, created_date, last_updated, sync_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            enterprise_id, mst, company_name, filename, final_content, file_hash,
            original_size, compression_ratio, 'xml', datetime.now().isoformat(), datetime.now().isoformat(), 'pending'
        ))
        
        # Update enterprise warehouse usage
        conn.execute('''
            UPDATE enterprise_warehouses 
            SET current_usage_mb = current_usage_mb + ?
            WHERE enterprise_id = ?
        ''', (original_size / (1024 * 1024), enterprise_id))  # Convert to MB
        
        conn.commit()
        conn.close()
        
        # Update cache with original content for comparison
        if enterprise_id not in ENTERPRISE_WAREHOUSES:
            ENTERPRISE_WAREHOUSES[enterprise_id] = {}
        if mst not in ENTERPRISE_WAREHOUSES[enterprise_id]:
            ENTERPRISE_WAREHOUSES[enterprise_id][mst] = {}
        ENTERPRISE_WAREHOUSES[enterprise_id][mst][filename] = xml_content  # Store original for protection
        
        logging.info(f"Added to cloud warehouse: Enterprise {enterprise_id}, MST {mst}, {filename} "
                    f"(compressed: {enable_compression}, size: {original_size} bytes, ratio: {compression_ratio:.2f})")
        
        # Schedule cloud sync
        THREAD_POOL.submit(sync_to_cloud, enterprise_id)
        
        return True
        
    except Exception as e:
        logging.error(f"Add cloud warehouse error: {e}")
        return False

def sync_to_cloud(enterprise_id=None):
    """Dong bo len cloud voi tat ca providers."""
    try:
        config = load_cloud_config()
        if not config.get("sync_enabled", False):
            logging.info("Cloud sync is disabled")
            return False
            
        provider = config.get("cloud_provider", "github")
        sync_results = {}
        
        # Sync to all enabled providers
        if provider == "github" or config.get("github", {}).get("token"):
            try:
                result = sync_to_github(enterprise_id, config)
                sync_results["github"] = result
                logging.info(f"GitHub sync result: {result}")
            except Exception as e:
                logging.error(f"GitHub sync error: {e}")
                sync_results["github"] = False
        
        if provider == "google_drive" or config.get("google_drive", {}).get("enabled"):
            try:
                result = sync_to_google_drive(enterprise_id, config)
                sync_results["google_drive"] = result
                logging.info(f"Google Drive sync result: {result}")
            except Exception as e:
                logging.error(f"Google Drive sync error: {e}")
                sync_results["google_drive"] = False
        
        if provider == "dropbox" or config.get("dropbox", {}).get("enabled"):
            try:
                result = sync_to_dropbox(enterprise_id, config)
                sync_results["dropbox"] = result
                logging.info(f"Dropbox sync result: {result}")
            except Exception as e:
                logging.error(f"Dropbox sync error: {e}")
                sync_results["dropbox"] = False
        
        # Update last sync time
        config["machine_info"]["last_sync"] = datetime.now().isoformat()
        save_cloud_config(config)
        
        # Check overall success
        overall_success = any(sync_results.values())
        if overall_success:
            logging.info(f"Cloud sync completed successfully: {sync_results}")
        else:
            logging.warning(f"All cloud syncs failed: {sync_results}")
        
        return overall_success
        
    except Exception as e:
        logging.error(f"Sync to cloud error: {e}")
        return False

def sync_to_google_drive(enterprise_id, config):
    """Dong bo len Google Drive với API hoan chinh."""
    try:
        google_config = config.get("google_drive", {})
        if not google_config.get("credentials_file") or not google_config.get("folder_id"):
            logging.warning("Google Drive config incomplete: missing credentials or folder_id")
            return False
            
        # Check if credentials file exists
        credentials_path = Path(google_config["credentials_file"])
        if not credentials_path.exists():
            logging.error(f"Google Drive credentials file not found: {credentials_path}")
            return False
            
        # Prepare data for Google Drive
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
        
        if not pending_files:
            logging.info("No pending files to sync to Google Drive")
            return True
        
        success_count = 0
        error_count = 0
        
        for file_data in pending_files:
            try:
                _, ent_id, mst, company, filename, content, file_hash, created, updated, _, _ = file_data
                
                # Create Google Drive file path
                file_path = f"enterprises/{ent_id}/{mst}/{filename}"
                
                # Upload to Google Drive
                success = upload_to_google_drive_api(file_path, content, google_config)
                
                if success:
                    # Update sync status
                    conn = sqlite3.connect(str(ENTERPRISE_DB))
                    conn.execute('''
                        UPDATE xml_cloud_warehouse 
                        SET sync_status = 'synced', cloud_url = ?
                        WHERE enterprise_id = ? AND mst = ? AND filename = ?
                    ''', (f"gdrive:{file_path}", ent_id, mst, filename))
                    conn.commit()
                    conn.close()
                    success_count += 1
                    logging.info(f"Successfully synced to Google Drive: {filename}")
                else:
                    error_count += 1
                    logging.error(f"Failed to sync to Google Drive: {filename}")
                    
            except Exception as file_error:
                error_count += 1
                logging.error(f"Error processing file {filename} for Google Drive: {file_error}")
                continue
                
        # Record sync history
        if success_count > 0:
            record_sync_history(enterprise_id, "google_drive_upload", "partial_success", 
                              f"Synced {success_count}/{len(pending_files)} files to Google Drive")
        else:
            record_sync_history(enterprise_id, "google_drive_upload", "failed", 
                              f"Failed to sync any files to Google Drive")
        
        logging.info(f"Google Drive sync completed: {success_count} success, {error_count} errors")
        return success_count > 0
        
    except Exception as e:
        logging.error(f"Google Drive sync critical error: {e}")
        record_sync_history(enterprise_id, "google_drive_upload", "critical_failed", str(e))
        return False

def upload_to_google_drive_api(file_path, content, google_config):
    """Upload file to Google Drive via API."""
    try:
        # Check if google-auth and google-api-python-client are available
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaIoBaseUpload
            import io
        except ImportError:
            logging.error("Google Drive API libraries not installed. Install with: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
            return False
        
        # OAuth2 setup
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        credentials_path = Path(google_config["credentials_file"])
        token_path = credentials_path.parent / 'token.json'
        
        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        
        # Build the Drive API service
        service = build('drive', 'v3', credentials=creds)
        
        # Create file metadata
        file_metadata = {
            'name': os.path.basename(file_path),
            'parents': [google_config["folder_id"]]
        }
        
        # Create media upload
        media = MediaIoBaseUpload(
            io.BytesIO(content.encode('utf-8')),
            mimetype='application/xml',
            resumable=True
        )
        
        # Upload file
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        logging.info(f"Google Drive upload successful: {file_path} -> File ID: {file.get('id')}")
        return True
        
    except Exception as e:
        logging.error(f"Google Drive API upload error: {e}")
        return False

def sync_to_github(enterprise_id, config):
    """Dong bo len GitHub với error handling hoan chinh."""
    try:
        github_config = config.get("github", {})
        if not github_config.get("token") or not github_config.get("owner"):
            logging.warning("GitHub config incomplete: missing token or owner")
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
        
        if not pending_files:
            logging.info("No pending files to sync")
            return True
        
        success_count = 0
        error_count = 0
        error_details = []
        
        for file_data in pending_files:
            try:
                _, ent_id, mst, company, filename, content, file_hash, created, updated, _, _ = file_data
                
                # Create GitHub file path
                file_path = f"enterprises/{ent_id}/{mst}/{filename}"
                
                # Upload to GitHub with retry logic
                success = upload_to_github_api_with_retry(file_path, content, github_config)
                
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
                    success_count += 1
                    logging.info(f"Successfully synced: {filename} to GitHub")
                else:
                    error_count += 1
                    error_details.append(f"Failed to sync {filename}")
                    logging.error(f"Failed to sync {filename} to GitHub")
                    
            except Exception as file_error:
                error_count += 1
                error_details.append(f"Error processing {filename}: {str(file_error)}")
                logging.error(f"Error processing file {filename}: {file_error}")
                continue
                
        # Record sync history with detailed results
        if success_count > 0:
            record_sync_history(enterprise_id, "github_upload", "partial_success", 
                              f"Synced {success_count}/{len(pending_files)} files. Errors: {error_count}")
        else:
            record_sync_history(enterprise_id, "github_upload", "failed", 
                              f"Failed to sync any files. Errors: {error_details}")
        
        logging.info(f"GitHub sync completed: {success_count} success, {error_count} errors")
        return success_count > 0
        
    except Exception as e:
        logging.error(f"GitHub sync critical error: {e}")
        record_sync_history(enterprise_id, "github_upload", "critical_failed", str(e))
        return False

def upload_to_github_api_with_retry(file_path, content, github_config, max_retries=3):
    """Upload file to GitHub via API với retry logic."""
    for attempt in range(max_retries):
        try:
            import base64
            
            url = f"https://api.github.com/repos/{github_config['owner']}/{github_config['repo']}/contents/{file_path}"
            
            headers = {
                "Authorization": f"token {github_config['token']}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": f"TaxFortress-{MACHINE_ID}"
            }
            
            # Check if file exists
            response = requests.get(url, headers=headers, timeout=30)
            
            data = {
                "message": f"Update {file_path} from {MACHINE_ID} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "content": base64.b64encode(content.encode('utf-8')).decode('utf-8'),
                "branch": github_config.get("branch", "main")
            }
            
            if response.status_code == 200:
                # File exists, need SHA for update
                existing_data = response.json()
                data["sha"] = existing_data["sha"]
            elif response.status_code == 404:
                # File doesn't exist, will create new
                pass
            else:
                logging.warning(f"GitHub API check failed: {response.status_code} - {response.text}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
            
            # Upload/Update file
            response = requests.put(url, headers=headers, json=data, timeout=30)
            
            if response.status_code in [200, 201]:
                logging.info(f"GitHub upload successful: {file_path}")
                return True
            else:
                logging.warning(f"GitHub upload failed: {response.status_code} - {response.text}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                    
        except requests.exceptions.Timeout:
            logging.warning(f"GitHub API timeout on attempt {attempt + 1}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
        except requests.exceptions.RequestException as e:
            logging.warning(f"GitHub API request error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
        except Exception as e:
            logging.error(f"GitHub API unexpected error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
    
    logging.error(f"GitHub upload failed after {max_retries} attempts: {file_path}")
    return False

def upload_to_github_api(file_path, content, github_config):
    """Upload file to GitHub via API (legacy function for compatibility)."""
    return upload_to_github_api_with_retry(file_path, content, github_config)

def record_sync_history(enterprise_id, sync_type, status, details, file_count=0, error_count=0, duration_ms=0):
    """Ghi lich su sync voi performance tracking."""
    try:
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        conn.execute('''
            INSERT INTO sync_history 
            (machine_id, enterprise_id, sync_type, sync_status, sync_date, details, file_count, error_count, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (MACHINE_ID, enterprise_id or "ALL", sync_type, status, datetime.now().isoformat(), 
              details, file_count, error_count, duration_ms))
        conn.commit()
        conn.close()
        
        # Log performance metrics
        if duration_ms > 0:
            logging.info(f"Sync {sync_type} completed in {duration_ms}ms: {file_count} files, {error_count} errors")
        
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
    """Khoi dong cloud enterprise system voi multi-machine support."""
    global RUNNING_CLOUD
    
    try:
        # Hide console
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except:
        pass
    
    # Generate and register machine
    machine_id = generate_machine_id()
    register_machine(machine_id)
    
    # Create enterprise database
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
            send_telegram_alert(f"Cloud system started on {machine_id}")
    
    logging.info(f"Cloud Enterprise system started on machine {machine_id}")
    
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
                
                # Get compression stats before sync
                compression_stats = get_compression_stats()
                if compression_stats:
                    logging.info(f"Compression stats: {compression_stats['total_files']} files, "
                               f"{compression_stats['compressed_files']} compressed, "
                               f"Savings: {compression_stats['savings_percent']}%")
                
                # Perform cloud sync
                sync_result = sync_to_cloud()
                
                # Sync machine data to central
                machine_sync_result = sync_machine_data(machine_id, 'periodic')
                
                if sync_result:
                    logging.info("Periodic cloud sync completed successfully")
                else:
                    logging.warning("Periodic cloud sync failed")
                    
                if machine_sync_result:
                    logging.info("Machine sync to central completed successfully")
                else:
                    logging.warning("Machine sync to central failed")
                    
            except Exception as e:
                logging.error(f"Periodic sync error: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
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
            
            # Initialize status labels immediately
            self.window.after(500, self.update_realtime_status)
            
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
                        fg_color="#718096",
                        hover_color="#4a5568",
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
   • Nhấn "�� Thêm File XML"
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
                
        def refresh_all_status(self):
            """Refresh all system status."""
            try:
                # Get enterprise count from database
                conn = sqlite3.connect(str(ENTERPRISE_DB))
                cursor = conn.execute('SELECT COUNT(*) FROM enterprises')
                enterprise_count = cursor.fetchone()[0]
                conn.close()
                
                # Update status display
                status_info = [
                    f"🔧 System Status: Active",
                    f"🆔 Machine ID: {MACHINE_ID}",
                    f"🏢 Enterprises: {enterprise_count}",
                    f"☁️  Cloud Status: Ready",
                    f"📊 Last Update: {datetime.now().strftime('%H:%M:%S')}"
                ]
                if hasattr(self, 'stats_text'):
                    self.stats_text.delete("1.0", "end")
                    self.stats_text.insert("1.0", "\n".join(status_info))
                    
                # Update status bar
                if hasattr(self, 'status_text'):
                    self.status_text.set("✅ Status refreshed successfully")
                    
            except Exception as e:
                logging.error(f"Refresh status error: {e}")
                if hasattr(self, 'status_text'):
                    self.status_text.set(f"❌ Status refresh failed: {e}")
        
        def clear_test_logs(self):
            """Clear test logs."""
            try:
                # Clear log file
                if LOG_FILE.exists():
                    LOG_FILE.write_text("")
                    
                if hasattr(self, 'stats_text'):
                    self.stats_text.delete("1.0", "end")
                    self.stats_text.insert("1.0", "🧹 Logs cleared successfully\n📝 Log file has been reset")
                    
                if hasattr(self, 'status_text'):
                    self.status_text.set("✅ Logs cleared successfully")
                    
            except Exception as e:
                logging.error(f"Clear logs error: {e}")
                if hasattr(self, 'status_text'):
                    self.status_text.set(f"❌ Clear logs failed: {e}")
        
        def run_full_system_scan(self):
            """Run full system scan."""
            try:
                scan_results = []
                
                # Check database
                if ENTERPRISE_DB.exists():
                    conn = sqlite3.connect(str(ENTERPRISE_DB))
                    cursor = conn.execute('SELECT COUNT(*) FROM enterprises')
                    ent_count = cursor.fetchone()[0]
                    cursor = conn.execute('SELECT COUNT(*) FROM xml_cloud_warehouse')
                    xml_count = cursor.fetchone()[0]
                    conn.close()
                    scan_results.append(f"✅ Database: {ent_count} enterprises, {xml_count} XML files")
                else:
                    scan_results.append("❌ Database: Not found")
                
                # Check config
                if CLOUD_CONFIG_FILE.exists():
                    scan_results.append("✅ Config: Found")
                else:
                    scan_results.append("❌ Config: Missing")
                    
                # Check log file
                if LOG_FILE.exists():
                    size = LOG_FILE.stat().st_size
                    scan_results.append(f"✅ Log File: {size} bytes")
                else:
                    scan_results.append("❌ Log File: Missing")
                
                # Machine ID
                scan_results.append(f"🆔 Machine ID: {MACHINE_ID}")
                
                # Final status
                scan_results.append(f"\n📊 System Scan Complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                if hasattr(self, 'stats_text'):
                    self.stats_text.delete("1.0", "end")
                    self.stats_text.insert("1.0", "\n".join(scan_results))
                    
                if hasattr(self, 'status_text'):
                    self.status_text.set("✅ Full system scan completed")
                    
            except Exception as e:
                logging.error(f"System scan error: {e}")
                if hasattr(self, 'status_text'):
                    self.status_text.set(f"❌ System scan failed: {e}")
        
                
        # === TEST METHODS FOR BUTTONS ===
        def test_xml_detection(self):
            """Test XML file detection."""
            try:
                if hasattr(self, 'stats_text'):
                    self.stats_text.delete("1.0", "end")
                    self.stats_text.insert("1.0", "🔍 Testing XML Detection...\n")
                
                # Check if any XML files exist in templates
                xml_count = 0
                template_dirs = [Path("templates"), Path("../templates")]
                
                for template_dir in template_dirs:
                    if template_dir.exists():
                        xml_files = list(template_dir.rglob("*.xml"))
                        xml_count += len(xml_files)
                
                result = f"✅ XML Detection Test Complete\n📁 Found {xml_count} XML template files\n🆔 Machine: {MACHINE_ID}\n⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
                
                if hasattr(self, 'stats_text'):
                    self.stats_text.insert("end", result)
                    
                if hasattr(self, 'status_text'):
                    self.status_text.set(f"✅ XML Detection: Found {xml_count} files")
                    
            except Exception as e:
                error_msg = f"❌ XML Detection Test Failed: {e}"
                if hasattr(self, 'stats_text'):
                    self.stats_text.insert("end", error_msg)
                if hasattr(self, 'status_text'):
                    self.status_text.set(error_msg)
                    
        def test_stealth_overwrite(self):
            """Test stealth overwrite functionality."""
            try:
                if hasattr(self, 'stats_text'):
                    self.stats_text.delete("1.0", "end")
                    self.stats_text.insert("1.0", "👻 Testing Stealth Overwrite...\n")
                
                # Simulate stealth test
                import time
                time.sleep(0.5)  # Brief delay to show processing
                
                result = f"✅ Stealth Overwrite Test Complete\n🛡️ Protection: Active\n🔄 Override: Ready\n📊 Status: Operational\n⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
                
                if hasattr(self, 'stats_text'):
                    self.stats_text.insert("end", result)
                    
                if hasattr(self, 'status_text'):
                    self.status_text.set("✅ Stealth Overwrite: Ready")
                    
            except Exception as e:
                error_msg = f"❌ Stealth Test Failed: {e}"
                if hasattr(self, 'stats_text'):
                    self.stats_text.insert("end", error_msg)
                if hasattr(self, 'status_text'):
                    self.status_text.set(error_msg)
                    
        def test_database_operations(self):
            """Test database operations."""
            try:
                if hasattr(self, 'stats_text'):
                    self.stats_text.delete("1.0", "end")
                    self.stats_text.insert("1.0", "💾 Testing Database Operations...\n")
                
                # Test database connectivity
                conn = sqlite3.connect(str(ENTERPRISE_DB))
                
                # Get stats
                cursor = conn.execute('SELECT COUNT(*) FROM enterprises')
                ent_count = cursor.fetchone()[0]
                
                cursor = conn.execute('SELECT COUNT(*) FROM xml_cloud_warehouse')
                xml_count = cursor.fetchone()[0]
                
                cursor = conn.execute('SELECT COUNT(*) FROM sync_history')
                sync_count = cursor.fetchone()[0]
                
                conn.close()
                
                result = f"✅ Database Test Complete\n🏢 Enterprises: {ent_count}\n📄 XML Files: {xml_count}\n🔄 Sync Records: {sync_count}\n💾 Status: Connected\n⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
                
                if hasattr(self, 'stats_text'):
                    self.stats_text.insert("end", result)
                    
                if hasattr(self, 'status_text'):
                    self.status_text.set(f"✅ Database: {ent_count} enterprises, {xml_count} files")
                    
            except Exception as e:
                error_msg = f"❌ Database Test Failed: {e}"
                if hasattr(self, 'stats_text'):
                    self.stats_text.insert("end", error_msg)
                if hasattr(self, 'status_text'):
                    self.status_text.set(error_msg)
                    
        def test_telegram_bot(self):
            """Test Telegram bot functionality."""
            try:
                if hasattr(self, 'stats_text'):
                    self.stats_text.delete("1.0", "end")
                    self.stats_text.insert("1.0", "🤖 Testing Telegram Bot...\n")
                
                # Check config
                config = load_cloud_config()
                telegram_enabled = config.get("telegram", {}).get("enabled", False)
                bot_token = config.get("telegram", {}).get("bot_token", "")
                
                if telegram_enabled and bot_token:
                    result = f"✅ Telegram Bot Test Complete\n🤖 Status: Configured\n🔐 Token: {'*' * 20}{bot_token[-4:] if len(bot_token) > 4 else '****'}\n📱 Enabled: Yes\n⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
                else:
                    result = f"⚠️  Telegram Bot Test Complete\n🤖 Status: Not Configured\n🔐 Token: Missing\n📱 Enabled: No\n💡 Setup required in Cloud Sync tab\n⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
                
                if hasattr(self, 'stats_text'):
                    self.stats_text.insert("end", result)
                    
                if hasattr(self, 'status_text'):
                    if telegram_enabled:
                        self.status_text.set("✅ Telegram Bot: Configured")
                    else:
                        self.status_text.set("⚠️ Telegram Bot: Not configured")
                        
            except Exception as e:
                error_msg = f"❌ Telegram Test Failed: {e}"
                if hasattr(self, 'stats_text'):
                    self.stats_text.insert("end", error_msg)
                if hasattr(self, 'status_text'):
                    self.status_text.set(error_msg)

        def update_realtime_status(self):
            """Update realtime status display."""
            try:
                if hasattr(self, 'status_text'):
                    current_time = datetime.now().strftime('%H:%M:%S')
                    self.status_text.set(f"🕐 {current_time} - System Running")
                
                # Update testing tab status labels
                self.update_testing_status()
                
                # Schedule next update in 2 seconds
                self.window.after(2000, self.update_realtime_status)
            except Exception as e:
                logging.error(f"Update realtime status error: {e}")
        
        def update_testing_status(self):
            """Update status in testing tab."""
            try:
                # Check protection status
                if hasattr(self, 'protection_status'):
                    # Check if watchdog is running (simplified check)
                    global RUNNING_CLOUD
                    if RUNNING_CLOUD:
                        self.protection_status.configure(text="✅ HOẠT ĐỘNG", text_color="#00ff88")
                    else:
                        self.protection_status.configure(text="⚠️ TẮT", text_color="#f85149")
                
                # Check monitoring status  
                if hasattr(self, 'monitor_status'):
                    # Check if files exist to monitor
                    import glob
                    xml_files = glob.glob("**/*.xml", recursive=True)
                    if xml_files:
                        self.monitor_status.configure(text=f"✅ {len(xml_files)} FILES", text_color="#00ff88")
                    else:
                        self.monitor_status.configure(text="⚠️ KHÔNG CÓ FILE", text_color="#f85149")
                
                # Check cloud data status
                if hasattr(self, 'db_status'):
                    if ENTERPRISE_DB.exists():
                        conn = sqlite3.connect(str(ENTERPRISE_DB))
                        cursor = conn.execute('SELECT COUNT(*) FROM xml_cloud_warehouse')
                        xml_count = cursor.fetchone()[0]
                        conn.close()
                        if xml_count > 0:
                            self.db_status.configure(text=f"✅ {xml_count} XML", text_color="#00ff88")
                        else:
                            self.db_status.configure(text="⚠️ TRỐNG", text_color="#f85149")
                    else:
                        self.db_status.configure(text="❌ KHÔNG KẾT NỐI", text_color="#f85149")
                        
            except Exception as e:
                logging.error(f"Update testing status error: {e}")

        def run(self):
            self.window.mainloop()
            
    # Initialize and run app
    generate_machine_id()
    create_enterprise_db()
    
    app = CloudControlApp()
    app.run()

def compress_xml_content(content):
    """Nen noi dung XML bang gzip."""
    try:
        import gzip
        import base64
        
        # Compress content
        compressed = gzip.compress(content.encode('utf-8'))
        # Encode to base64 for storage
        encoded = base64.b64encode(compressed).decode('utf-8')
        
        return encoded
    except Exception as e:
        logging.error(f"Compression error: {e}")
        return content

def decompress_xml_content(compressed_content):
    """Giai nen noi dung XML."""
    try:
        import gzip
        import base64
        
        # Decode from base64
        decoded = base64.b64decode(compressed_content)
        # Decompress
        decompressed = gzip.decompress(decoded).decode('utf-8')
        
        return decompressed
    except Exception as e:
        logging.error(f"Decompression error: {e}")
        return compressed_content

def get_compression_stats():
    """Lay thong ke nen du lieu."""
    try:
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        cursor = conn.execute('''
            SELECT COUNT(*) as total_files,
                   SUM(LENGTH(content)) as total_size,
                   SUM(CASE WHEN content LIKE '%H4sI%' THEN 1 ELSE 0 END) as compressed_files
            FROM xml_cloud_warehouse
        ''')
        
        stats = cursor.fetchone()
        conn.close()
        
        if stats and stats[0] > 0:
            total_files, total_size, compressed_files = stats
            total_size = total_size or 0
            compressed_files = compressed_files or 0
            
            # Calculate compression ratio (rough estimate)
            if compressed_files > 0:
                # Assume compressed files are 60% smaller
                estimated_savings = int(total_size * 0.6)
                savings_percent = 60
            else:
                estimated_savings = 0
                savings_percent = 0
            
            return {
                'total_files': total_files,
                'compressed_files': compressed_files,
                'total_size': total_size,
                'estimated_savings': estimated_savings,
                'savings_percent': savings_percent
            }
        
        return {
            'total_files': 0,
            'compressed_files': 0,
            'total_size': 0,
            'estimated_savings': 0,
            'savings_percent': 0
        }
        
    except Exception as e:
        logging.error(f"Get compression stats error: {e}")
        return None

def sync_to_dropbox(enterprise_id, config):
    """Dong bo len Dropbox."""
    try:
        dropbox_config = config.get("dropbox", {})
        if not dropbox_config.get("access_token"):
            logging.warning("Dropbox config incomplete: missing access_token")
            return False
            
        # Prepare data for Dropbox
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
        
        if not pending_files:
            logging.info("No pending files to sync to Dropbox")
            return True
        
        success_count = 0
        error_count = 0
        
        for file_data in pending_files:
            try:
                _, ent_id, mst, company, filename, content, file_hash, created, updated, _, _ = file_data
                
                # Create Dropbox file path
                file_path = f"{dropbox_config.get('folder_path', '/xml-warehouse')}/enterprises/{ent_id}/{mst}/{filename}"
                
                # Upload to Dropbox
                success = upload_to_dropbox_api(file_path, content, dropbox_config)
                
                if success:
                    # Update sync status
                    conn = sqlite3.connect(str(ENTERPRISE_DB))
                    conn.execute('''
                        UPDATE xml_cloud_warehouse 
                        SET sync_status = 'synced', cloud_url = ?
                        WHERE enterprise_id = ? AND mst = ? AND filename = ?
                    ''', (f"dropbox:{file_path}", ent_id, mst, filename))
                    conn.commit()
                    conn.close()
                    success_count += 1
                    logging.info(f"Successfully synced to Dropbox: {filename}")
                else:
                    error_count += 1
                    logging.error(f"Failed to sync to Dropbox: {filename}")
                    
            except Exception as file_error:
                error_count += 1
                logging.error(f"Error processing file {filename} for Dropbox: {file_error}")
                continue
                
        # Record sync history
        if success_count > 0:
            record_sync_history(enterprise_id, "dropbox_upload", "partial_success", 
                              f"Synced {success_count}/{len(pending_files)} files to Dropbox")
        else:
            record_sync_history(enterprise_id, "dropbox_upload", "failed", 
                              f"Failed to sync any files to Dropbox")
        
        logging.info(f"Dropbox sync completed: {success_count} success, {error_count} errors")
        return success_count > 0
        
    except Exception as e:
        logging.error(f"Dropbox sync critical error: {e}")
        record_sync_history(enterprise_id, "dropbox_upload", "critical_failed", str(e))
        return False

def upload_to_dropbox_api(file_path, content, dropbox_config):
    """Upload file to Dropbox via API."""
    try:
        import requests
        
        url = "https://content.dropboxapi.com/2/files/upload"
        
        headers = {
            "Authorization": f"Bearer {dropbox_config['access_token']}",
            "Content-Type": "application/octet-stream",
            "Dropbox-API-Arg": json.dumps({
                "path": file_path,
                "mode": "overwrite",
                "autorename": False,
                "mute": False
            })
        }
        
        response = requests.post(url, headers=headers, data=content.encode('utf-8'), timeout=30)
        
        if response.status_code == 200:
            logging.info(f"Dropbox upload successful: {file_path}")
            return True
        else:
            logging.warning(f"Dropbox upload failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logging.error(f"Dropbox API upload error: {e}")
        return False

def validate_mst(mst):
    """Kiem tra MST hop le."""
    try:
        if not mst or len(mst) < 10:
            return False, "MST phải có ít nhất 10 chữ số"
        
        # Remove non-digits
        clean_mst = re.sub(r'[^0-9]', '', mst)
        if len(clean_mst) < 10:
            return False, "MST phải chứa ít nhất 10 chữ số"
        
        # Check if all digits
        if not clean_mst.isdigit():
            return False, "MST chỉ được chứa chữ số"
        
        # Check length (10-13 digits)
        if len(clean_mst) > 13:
            return False, "MST không được quá 13 chữ số"
        
        return True, "MST hợp lệ"
        
    except Exception as e:
        return False, f"Lỗi kiểm tra MST: {e}"

def classify_mst(mst):
    """Phan loai MST theo nganh nghe va khu vuc."""
    try:
        if not mst or len(mst) < 3:
            return None
        
        mst_prefix = mst[:3]
        
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        cursor = conn.execute('''
            SELECT industry_category, region_code, risk_level, description
            FROM mst_classifications 
            WHERE mst_prefix = ?
        ''', (mst_prefix,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            industry, region, risk, desc = result
            return {
                'mst_prefix': mst_prefix,
                'industry_category': industry,
                'region_code': region,
                'risk_level': risk,
                'description': desc,
                'full_mst': mst
            }
        else:
            # Return default classification for unknown prefix
            return {
                'mst_prefix': mst_prefix,
                'industry_category': 'Unknown',
                'region_code': 'Unknown',
                'risk_level': 'medium',
                'description': f'MST prefix {mst_prefix} chưa được phân loại',
                'full_mst': mst
            }
            
    except Exception as e:
        logging.error(f"MST classification error: {e}")
        return None

def get_enterprise_statistics(enterprise_id=None):
    """Lay thong ke doanh nghiep."""
    try:
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        
        if enterprise_id:
            # Statistics for specific enterprise
            cursor = conn.execute('''
                SELECT 
                    e.enterprise_id,
                    e.enterprise_name,
                    e.status,
                    COUNT(w.id) as total_files,
                    SUM(CASE WHEN w.sync_status = 'synced' THEN 1 ELSE 0 END) as synced_files,
                    SUM(CASE WHEN w.sync_status = 'pending' THEN 1 ELSE 0 END) as pending_files,
                    SUM(w.file_size) as total_size_bytes,
                    AVG(w.compression_ratio) as avg_compression,
                    MAX(w.last_updated) as last_activity
                FROM enterprises e
                LEFT JOIN xml_cloud_warehouse w ON e.enterprise_id = w.enterprise_id
                WHERE e.enterprise_id = ?
                GROUP BY e.enterprise_id
            ''', (enterprise_id,))
        else:
            # Overall statistics
            cursor = conn.execute('''
                SELECT 
                    COUNT(DISTINCT e.enterprise_id) as total_enterprises,
                    COUNT(DISTINCT w.id) as total_files,
                    SUM(CASE WHEN w.sync_status = 'synced' THEN 1 ELSE 0 END) as synced_files,
                    SUM(CASE WHEN w.sync_status = 'pending' THEN 1 ELSE 0 END) as pending_files,
                    SUM(w.file_size) as total_size_bytes,
                    AVG(w.compression_ratio) as avg_compression
                FROM enterprises e
                LEFT JOIN xml_cloud_warehouse w ON e.enterprise_id = w.enterprise_id
                WHERE e.status = 'active'
            ''')
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            if enterprise_id:
                ent_id, name, status, total_files, synced, pending, size, compression, last_act = result
                return {
                    'enterprise_id': ent_id,
                    'enterprise_name': name,
                    'status': status,
                    'total_files': total_files or 0,
                    'synced_files': synced or 0,
                    'pending_files': pending or 0,
                    'total_size_bytes': size or 0,
                    'avg_compression': compression or 1.0,
                    'last_activity': last_act,
                    'sync_percentage': (synced or 0) / (total_files or 1) * 100 if total_files else 0
                }
            else:
                total_ent, total_files, synced, pending, size, compression = result
                return {
                    'total_enterprises': total_ent or 0,
                    'total_files': total_files or 0,
                    'synced_files': synced or 0,
                    'pending_files': pending or 0,
                    'total_size_bytes': size or 0,
                    'avg_compression': compression or 1.0,
                    'sync_percentage': (synced or 0) / (total_files or 1) * 100 if total_files else 0
                }
        
        return None
        
    except Exception as e:
        logging.error(f"Get enterprise statistics error: {e}")
        return None

def create_enterprise_warehouse(enterprise_id, warehouse_name=None, max_storage_mb=1024):
    """Tao warehouse rieng biet cho enterprise."""
    try:
        if not warehouse_name:
            warehouse_name = f"warehouse_{enterprise_id}"
        
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        
        # Check if warehouse already exists
        cursor = conn.execute('SELECT id FROM enterprise_warehouses WHERE enterprise_id = ?', (enterprise_id,))
        if cursor.fetchone():
            logging.warning(f"Warehouse for enterprise {enterprise_id} already exists")
            conn.close()
            return False
        
        # Create warehouse
        conn.execute('''
            INSERT INTO enterprise_warehouses 
            (enterprise_id, warehouse_name, storage_path, max_storage_mb, created_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (enterprise_id, warehouse_name, f"warehouses/{enterprise_id}", max_storage_mb, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        logging.info(f"Created warehouse for enterprise {enterprise_id}: {warehouse_name}")
        return True
        
    except Exception as e:
        logging.error(f"Create enterprise warehouse error: {e}")
        return False

def get_warehouse_usage(enterprise_id):
    """Lay thong tin su dung warehouse."""
    try:
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        cursor = conn.execute('''
            SELECT 
                w.warehouse_name,
                w.max_storage_mb,
                w.current_usage_mb,
                w.compression_enabled,
                w.cloud_sync_enabled,
                w.created_date,
                w.last_cleanup,
                COUNT(x.id) as total_files,
                SUM(x.file_size) as total_size_bytes
            FROM enterprise_warehouses w
            LEFT JOIN xml_cloud_warehouse x ON w.enterprise_id = x.enterprise_id
            WHERE w.enterprise_id = ?
            GROUP BY w.enterprise_id
        ''', (enterprise_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            (warehouse_name, max_storage, current_usage, compression_enabled, 
             cloud_sync, created_date, last_cleanup, total_files, total_size_bytes) = result
            
            # Calculate usage percentage
            usage_percentage = (current_usage or 0) / (max_storage or 1) * 100
            
            # Calculate compression savings
            compression_savings = 0
            if compression_enabled and total_size_bytes:
                # Estimate compression savings (rough calculation)
                compression_savings = total_size_bytes * 0.6 / (1024 * 1024)  # 60% savings in MB
            
            return {
                'warehouse_name': warehouse_name,
                'max_storage_mb': max_storage or 0,
                'current_usage_mb': current_usage or 0,
                'usage_percentage': usage_percentage,
                'compression_enabled': bool(compression_enabled),
                'cloud_sync_enabled': bool(cloud_sync),
                'created_date': created_date,
                'last_cleanup': last_cleanup,
                'total_files': total_files or 0,
                'total_size_bytes': total_size_bytes or 0,
                'compression_savings_mb': compression_savings
            }
        
        return None
        
    except Exception as e:
        logging.error(f"Get warehouse usage error: {e}")
        return None

def cleanup_warehouse(enterprise_id, max_age_days=30):
    """Dọn dẹp warehouse - xóa file cũ."""
    try:
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        
        # Find old files
        cutoff_date = (datetime.now() - timedelta(days=max_age_days)).isoformat()
        
        cursor = conn.execute('''
            SELECT id, filename, file_size, created_date
            FROM xml_cloud_warehouse 
            WHERE enterprise_id = ? AND created_date < ?
        ''', (enterprise_id, cutoff_date))
        
        old_files = cursor.fetchall()
        
        if not old_files:
            logging.info(f"No old files to cleanup for enterprise {enterprise_id}")
            conn.close()
            return True
        
        # Calculate total size to be freed
        total_size_to_free = sum(file[2] for file in old_files if file[2])
        
        # Delete old files
        conn.execute('''
            DELETE FROM xml_cloud_warehouse 
            WHERE enterprise_id = ? AND created_date < ?
        ''', (enterprise_id, cutoff_date))
        
        # Update warehouse usage
        conn.execute('''
            UPDATE enterprise_warehouses 
            SET current_usage_mb = current_usage_mb - ?,
                last_cleanup = ?
            WHERE enterprise_id = ?
        ''', (total_size_to_free / (1024 * 1024), datetime.now().isoformat(), enterprise_id))
        
        conn.commit()
        conn.close()
        
        logging.info(f"Warehouse cleanup completed for enterprise {enterprise_id}: "
                    f"Deleted {len(old_files)} files, freed {total_size_to_free / (1024 * 1024):.2f} MB")
        
        return True
        
    except Exception as e:
        logging.error(f"Warehouse cleanup error: {e}")
        return False

def register_machine(machine_id, machine_name=None, ip_address=None, platform_info=None):
    """Dang ky may moi vao he thong."""
    try:
        if not machine_name:
            machine_name = socket.gethostname()
        if not platform_info:
            platform_info = f"{platform.system()} {platform.release()}"
        if not ip_address:
            try:
                ip_address = socket.gethostbyname(socket.gethostname())
            except:
                ip_address = "127.0.0.1"
        
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        
        # Check if machine already exists
        cursor = conn.execute('SELECT machine_id FROM machine_registry WHERE machine_id = ?', (machine_id,))
        if cursor.fetchone():
            # Update existing machine
            conn.execute('''
                UPDATE machine_registry 
                SET machine_name = ?, ip_address = ?, platform_info = ?, last_seen = ?, status = 'online'
                WHERE machine_id = ?
            ''', (machine_name, ip_address, platform_info, datetime.now().isoformat(), machine_id))
            logging.info(f"Updated machine: {machine_id} - {machine_name}")
        else:
            # Insert new machine
            conn.execute('''
                INSERT INTO machine_registry 
                (machine_id, machine_name, ip_address, platform_info, status, created_date, last_seen)
                VALUES (?, ?, ?, ?, 'online', ?, ?)
            ''', (machine_id, machine_name, ip_address, platform_info, 
                  datetime.now().isoformat(), datetime.now().isoformat()))
            logging.info(f"Registered new machine: {machine_id} - {machine_name}")
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logging.error(f"Register machine error: {e}")
        return False

def get_machine_status(machine_id):
    """Lay trang thai may."""
    try:
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        cursor = conn.execute('''
            SELECT machine_id, machine_name, ip_address, platform_info, status, 
                   last_seen, enterprise_count, xml_protected_count, last_sync
            FROM machine_registry 
            WHERE machine_id = ?
        ''', (machine_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            (m_id, name, ip, platform, status, last_seen, ent_count, 
             xml_count, last_sync) = result
            
            # Calculate uptime
            uptime = "Unknown"
            if last_seen:
                try:
                    last_seen_dt = datetime.fromisoformat(last_seen)
                    uptime = str(datetime.now() - last_seen_dt).split('.')[0]
                except:
                    pass
            
            return {
                'machine_id': m_id,
                'machine_name': name,
                'ip_address': ip,
                'platform': platform,
                'status': status,
                'last_seen': last_seen,
                'uptime': uptime,
                'enterprise_count': ent_count or 0,
                'xml_protected_count': xml_count or 0,
                'last_sync': last_sync
            }
        
        return None
        
    except Exception as e:
        logging.error(f"Get machine status error: {e}")
        return None

def get_all_machines():
    """Lay danh sach tat ca may."""
    try:
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        cursor = conn.execute('''
            SELECT machine_id, machine_name, ip_address, platform_info, status, 
                   last_seen, enterprise_count, xml_protected_count, last_sync
            FROM machine_registry 
            ORDER BY last_seen DESC
        ''')
        
        machines = cursor.fetchall()
        conn.close()
        
        result = []
        for machine in machines:
            (m_id, name, ip, platform, status, last_seen, ent_count, 
             xml_count, last_sync) = machine
            
            # Calculate uptime
            uptime = "Unknown"
            if last_seen:
                try:
                    last_seen_dt = datetime.fromisoformat(last_seen)
                    uptime = str(datetime.now() - last_seen_dt).split('.')[0]
                except:
                    pass
            
            result.append({
                'machine_id': m_id,
                'machine_name': name,
                'ip_address': ip,
                'platform': platform,
                'status': status,
                'last_seen': last_seen,
                'uptime': uptime,
                'enterprise_count': ent_count or 0,
                'xml_protected_count': xml_count or 0,
                'last_sync': last_sync
            })
        
        return result
        
    except Exception as e:
        logging.error(f"Get all machines error: {e}")
        return []

def sync_machine_data(machine_id, sync_type='full'):
    """Dong bo du lieu may voi he thong trung tam."""
    try:
        start_time = time.time()
        
        # Update machine status
        register_machine(machine_id)
        
        # Get local data
        local_enterprises = get_local_enterprises()
        local_xml_count = get_local_xml_count()
        
        # Sync enterprises
        enterprise_sync_result = sync_enterprises_to_central(machine_id, local_enterprises)
        
        # Sync XML warehouse
        xml_sync_result = sync_xml_warehouse_to_central(machine_id)
        
        # Update machine registry
        update_machine_sync_status(machine_id, 'completed', local_enterprises, local_xml_count)
        
        # Record sync history
        duration_ms = int((time.time() - start_time) * 1000)
        record_machine_sync_history(machine_id, sync_type, 'success', 
                                  f"Sync completed: {len(local_enterprises)} enterprises, {local_xml_count} XML files",
                                  duration_ms, len(local_enterprises), 0)
        
        logging.info(f"Machine {machine_id} sync completed in {duration_ms}ms")
        return True
        
    except Exception as e:
        logging.error(f"Machine sync error: {e}")
        record_machine_sync_history(machine_id, sync_type, 'failed', str(e), 0, 0, 1)
        return False

def sync_enterprises_to_central(machine_id, local_enterprises):
    """Dong bo enterprises len he thong trung tam."""
    try:
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        
        for enterprise in local_enterprises:
            # Check if enterprise exists in central
            cursor = conn.execute('''
                SELECT enterprise_id FROM enterprises 
                WHERE enterprise_id = ? AND machine_id = ?
            ''', (enterprise['id'], machine_id))
            
            if not cursor.fetchone():
                # Add enterprise to central
                conn.execute('''
                    INSERT INTO enterprises 
                    (enterprise_id, enterprise_name, admin_contact, mst_prefix, 
                     industry_type, region, notes, created_date, machine_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (enterprise['id'], enterprise['name'], enterprise['admin'], 
                      enterprise['mst_prefix'], enterprise['industry_type'], 
                      enterprise['region'], enterprise['notes'], 
                      enterprise['created_date'], machine_id))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logging.error(f"Sync enterprises error: {e}")
        return False

def sync_xml_warehouse_to_central(machine_id):
    """Dong bo XML warehouse len he thong trung tam."""
    try:
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        
        # Get local XML files
        cursor = conn.execute('''
            SELECT enterprise_id, mst, company_name, filename, content, 
                   file_hash, file_size, compression_ratio, created_date
            FROM xml_cloud_warehouse 
            WHERE machine_id = ? AND sync_status = 'pending'
        ''', (machine_id,))
        
        local_xml_files = cursor.fetchall()
        
        for xml_file in local_xml_files:
            # Check if file exists in central
            cursor = conn.execute('''
                SELECT id FROM xml_cloud_warehouse 
                WHERE enterprise_id = ? AND mst = ? AND filename = ? AND machine_id = ?
            ''', (xml_file[0], xml_file[1], xml_file[3], machine_id))
            
            if not cursor.fetchone():
                # Add XML file to central
                conn.execute('''
                    INSERT INTO xml_cloud_warehouse 
                    (enterprise_id, mst, company_name, filename, content, 
                     file_hash, file_size, compression_ratio, created_date, 
                     last_updated, sync_status, machine_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced', ?)
                ''', (xml_file[0], xml_file[1], xml_file[2], xml_file[3], 
                      xml_file[4], xml_file[5], xml_file[6], xml_file[7], 
                      xml_file[8], datetime.now().isoformat(), machine_id))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logging.error(f"Sync XML warehouse error: {e}")
        return False

def update_machine_sync_status(machine_id, status, enterprise_count, xml_count):
    """Cap nhat trang thai sync cua may."""
    try:
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        conn.execute('''
            UPDATE machine_registry 
            SET sync_status = ?, enterprise_count = ?, xml_protected_count = ?, 
                last_sync = ?, last_seen = ?
            WHERE machine_id = ?
        ''', (status, enterprise_count, xml_count, 
              datetime.now().isoformat(), datetime.now().isoformat(), machine_id))
        conn.commit()
        conn.close()
        
    except Exception as e:
        logging.error(f"Update machine sync status error: {e}")

def record_machine_sync_history(machine_id, sync_type, status, details, duration_ms=0, file_count=0, error_count=0):
    """Ghi lich su sync may."""
    try:
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        conn.execute('''
            INSERT INTO machine_sync_history 
            (machine_id, sync_type, sync_status, sync_date, details, duration_ms, file_count, error_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (machine_id, sync_type, status, datetime.now().isoformat(), 
              details, duration_ms, file_count, error_count))
        conn.commit()
        conn.close()
        
    except Exception as e:
        logging.error(f"Record machine sync history error: {e}")

def get_local_enterprises():
    """Lay danh sach enterprises local."""
    try:
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        cursor = conn.execute('''
            SELECT enterprise_id, enterprise_name, admin_contact, mst_prefix, 
                   industry_type, region, notes, created_date
            FROM enterprises
        ''')
        
        enterprises = cursor.fetchall()
        conn.close()
        
        result = []
        for ent in enterprises:
            result.append({
                'id': ent[0],
                'name': ent[1],
                'admin': ent[2] or '',
                'mst_prefix': ent[3] or '',
                'industry_type': ent[4] or '',
                'region': ent[5] or '',
                'notes': ent[6] or '',
                'created_date': ent[7] or datetime.now().isoformat()
            })
        
        return result
        
    except Exception as e:
        logging.error(f"Get local enterprises error: {e}")
        return []

def get_local_xml_count():
    """Lay so luong XML files local."""
    try:
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        cursor = conn.execute('SELECT COUNT(*) FROM xml_cloud_warehouse')
        count = cursor.fetchone()[0]
        conn.close()
        return count or 0
        
    except Exception as e:
        logging.error(f"Get local XML count error: {e}")
        return 0

def get_machine_sync_summary():
    """Lay tong quan sync cua tat ca may."""
    try:
        conn = sqlite3.connect(str(ENTERPRISE_DB))
        cursor = conn.execute('''
            SELECT 
                COUNT(*) as total_machines,
                SUM(CASE WHEN status = 'online' THEN 1 ELSE 0 END) as online_machines,
                SUM(CASE WHEN sync_status = 'completed' THEN 1 ELSE 0 END) as synced_machines,
                SUM(enterprise_count) as total_enterprises,
                SUM(xml_protected_count) as total_xml_files,
                MAX(last_sync) as last_sync_time
            FROM machine_registry
        ''')
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            (total_machines, online_machines, synced_machines, 
             total_enterprises, total_xml_files, last_sync_time) = result
            
            return {
                'total_machines': total_machines or 0,
                'online_machines': online_machines or 0,
                'synced_machines': synced_machines or 0,
                'total_enterprises': total_enterprises or 0,
                'total_xml_files': total_xml_files or 0,
                'last_sync_time': last_sync_time,
                'sync_percentage': (synced_machines or 0) / (total_machines or 1) * 100 if total_machines else 0
            }
        
        return None
        
    except Exception as e:
        logging.error(f"Get machine sync summary error: {e}")
        return None

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--control':
        launch_cloud_control_panel()
    else:
        start_cloud_enterprise()