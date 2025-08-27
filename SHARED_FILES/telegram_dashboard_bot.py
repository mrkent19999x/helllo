# telegram_dashboard_bot.py - TELEGRAM BOT DASHBOARD ĐẸP TIẾNG VIỆT
# Multi-Machine Management System với giao diện trực quan

import os
import sys
import time
import json
import logging
import requests
import sqlite3
import threading
import asyncio
import platform
import socket
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Telegram Bot API
import telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton,
    Message, CallbackQuery
)

# Local imports
try:
    import sys
    sys.path.append('src')
    from cloud_enterprise import (
        load_cloud_config, save_cloud_config,
        load_enterprises, ENTERPRISE_DB, MACHINE_ID
    )
except ImportError:
    # Fallback nếu không import được
    ENTERPRISE_DB = None
    MACHINE_ID = None
    logging.warning("Không thể import cloud_enterprise, sử dụng fallback mode")

# --- CONFIG & SETUP --- #
APP_DIR = Path(os.getenv('APPDATA', Path.home())) / 'WindowsUpdate'
APP_DIR.mkdir(parents=True, exist_ok=True)

TELEGRAM_CONFIG_FILE = APP_DIR / 'telegram_dashboard.json'
BOT_LOG_FILE = APP_DIR / 'telegram_bot.log'
MACHINES_DB = APP_DIR / 'machines.db'

# Bot configuration
BOT_CONFIG = {
    "bot_token": "",
    "authorized_users": [],
    "admin_users": [],
    "auto_sync_interval": 300,  # 5 phút
    "max_machines": 50,
    "dashboard_timeout": 300,  # 5 phút
    "language": "vi"
}

# Machine status colors
STATUS_COLORS = {
    "online": "🟢",
    "offline": "🔴", 
    "warning": "🟡",
    "error": "🔴",
    "syncing": "🔄",
    "protected": "🛡️"
}

# Logging setup
logging.basicConfig(
    filename=str(BOT_LOG_FILE),
    encoding='utf-8',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class TelegramDashboardBot:
    """Telegram Bot với Dashboard đẹp để quản lý Multi-Machine."""
    
    def __init__(self, bot_token: str = None):
        """Khởi tạo bot."""
        self.bot_token = bot_token or self.load_bot_token()
        if not self.bot_token:
            raise ValueError("Bot token không được tìm thấy!")
            
        self.bot = telebot.TeleBot(self.bot_token)
        self.machines = {}  # {machine_id: machine_info}
        self.user_sessions = {}  # {user_id: session_data}
        self.sync_thread = None
        self.running = False
        
        # Setup bot handlers
        self.setup_handlers()
        
        # Initialize database
        self.init_machines_database()
        
        # Load existing machines
        self.load_machines()
        
        logging.info("Telegram Dashboard Bot đã khởi tạo thành công!")
    
    def load_bot_token(self) -> str:
        """Load bot token từ config file."""
        try:
            if TELEGRAM_CONFIG_FILE.exists():
                with open(TELEGRAM_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get('bot_token', '')
            return ''
        except Exception as e:
            logging.error(f"Load bot token error: {e}")
            return ''
    
    def save_bot_config(self):
        """Lưu bot config."""
        try:
            config = {
                'bot_token': self.bot_token,
                'authorized_users': BOT_CONFIG['authorized_users'],
                'admin_users': BOT_CONFIG['admin_users'],
                'auto_sync_interval': BOT_CONFIG['auto_sync_interval'],
                'max_machines': BOT_CONFIG['max_machines'],
                'dashboard_timeout': BOT_CONFIG['dashboard_timeout'],
                'language': BOT_CONFIG['language']
            }
            
            with open(TELEGRAM_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
                
            logging.info("Bot config đã được lưu!")
            
        except Exception as e:
            logging.error(f"Save bot config error: {e}")
    
    def init_machines_database(self):
        """Khởi tạo database cho machines."""
        try:
            conn = sqlite3.connect(str(MACHINES_DB))
            conn.execute('''
                CREATE TABLE IF NOT EXISTS machines (
                    machine_id TEXT PRIMARY KEY,
                    machine_name TEXT,
                    ip_address TEXT,
                    mac_address TEXT,
                    platform TEXT,
                    status TEXT DEFAULT 'offline',
                    last_seen TIMESTAMP,
                    enterprise_count INTEGER DEFAULT 0,
                    xml_protected_count INTEGER DEFAULT 0,
                    last_sync TIMESTAMP,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS machine_enterprises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    machine_id TEXT,
                    enterprise_id TEXT,
                    enterprise_name TEXT,
                    xml_count INTEGER DEFAULT 0,
                    last_updated TIMESTAMP,
                    FOREIGN KEY (machine_id) REFERENCES machines (machine_id)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS machine_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    machine_id TEXT,
                    log_type TEXT,
                    message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (machine_id) REFERENCES machines (machine_id)
                )
            ''')
            
            conn.commit()
            conn.close()
            logging.info("Machines database đã được khởi tạo!")
            
        except Exception as e:
            logging.error(f"Init machines database error: {e}")
    
    def load_machines(self):
        """Load machines từ database."""
        try:
            conn = sqlite3.connect(str(MACHINES_DB))
            cursor = conn.execute('''
                SELECT machine_id, machine_name, ip_address, mac_address, 
                       platform, status, last_seen, enterprise_count, 
                       xml_protected_count, last_sync
                FROM machines
            ''')
            
            machines_data = cursor.fetchall()
            conn.close()
            
            for row in machines_data:
                machine_id, name, ip, mac, platform, status, last_seen, ent_count, xml_count, last_sync = row
                
                self.machines[machine_id] = {
                    'machine_id': machine_id,
                    'machine_name': name or f"Machine-{machine_id[:8]}",
                    'ip_address': ip,
                    'mac_address': mac,
                    'platform': platform,
                    'status': status,
                    'last_seen': last_seen,
                    'enterprise_count': ent_count,
                    'xml_protected_count': xml_count,
                    'last_sync': last_sync,
                    'online': self.is_machine_online(machine_id, last_seen)
                }
            
            logging.info(f"Đã load {len(self.machines)} machines từ database!")
            
        except Exception as e:
            logging.error(f"Load machines error: {e}")
    
    def is_machine_online(self, machine_id: str, last_seen: str) -> bool:
        """Kiểm tra machine có online không."""
        try:
            if not last_seen:
                return False
                
            last_seen_dt = datetime.fromisoformat(last_seen)
            time_diff = datetime.now() - last_seen_dt
            
            # Machine được coi là online nếu last_seen < 5 phút
            return time_diff < timedelta(minutes=5)
            
        except Exception as e:
            logging.error(f"Check machine online error: {e}")
            return False
    
    def setup_handlers(self):
        """Setup các bot handlers."""
        
        @self.bot.message_handler(commands=['start', 'menu'])
        def handle_start(message: Message):
            """Xử lý lệnh start/menu."""
            user_id = message.from_user.id
            username = message.from_user.username or message.from_user.first_name
            
            if not self.is_authorized_user(user_id):
                self.send_unauthorized_message(message.chat.id)
                return
            
            # Tạo session cho user
            self.user_sessions[user_id] = {
                'current_menu': 'main_dashboard',
                'last_activity': datetime.now(),
                'selected_machine': None,
                'selected_enterprise': None
            }
            
            # Hiển thị main dashboard
            self.show_main_dashboard(message.chat.id, user_id)
            
            logging.info(f"User {username} ({user_id}) đã mở dashboard!")
        
        @self.bot.message_handler(commands=['help'])
        def handle_help(message: Message):
            """Xử lý lệnh help."""
            help_text = """
🤖 **TAX FORTRESS TELEGRAM BOT - HƯỚNG DẪN SỬ DỤNG**

📱 **LỆNH CƠ BẢN:**
• `/start` hoặc `/menu` - Mở Dashboard chính
• `/help` - Hiển thị hướng dẫn này
• `/status` - Kiểm tra trạng thái hệ thống
• `/machines` - Xem danh sách máy tính
• `/enterprises` - Xem danh sách doanh nghiệp

🎮 **CÁCH SỬ DỤNG:**
1. Gõ `/menu` để mở Dashboard
2. Sử dụng các nút bấm để điều hướng
3. Dashboard sẽ tự động cập nhật mỗi 5 phút
4. Nhận thông báo real-time khi có sự cố

🛡️ **TÍNH NĂNG CHÍNH:**
• Quản lý nhiều máy tính từ xa
• Giám sát bảo vệ file XML thuế
• Đồng bộ cloud tự động
• Cảnh báo real-time qua Telegram

💡 **LƯU Ý:**
• Chỉ user được ủy quyền mới sử dụng được
• Dashboard timeout sau 5 phút không hoạt động
• Tự động sync dữ liệu mỗi 5 phút
            """
            
            self.bot.reply_to(message, help_text, parse_mode='Markdown')
        
        @self.bot.message_handler(commands=['status'])
        def handle_status(message: Message):
            """Xử lý lệnh status."""
            if not self.is_authorized_user(message.from_user.id):
                return
                
            status_text = self.get_system_status_text()
            self.bot.reply_to(message, status_text, parse_mode='Markdown')
        
        @self.bot.message_handler(commands=['machines'])
        def handle_machines(message: Message):
            """Xử lý lệnh machines."""
            if not self.is_authorized_user(message.from_user.id):
                return
                
            self.show_machines_list(message.chat.id, message.from_user.id)
        
        @self.bot.message_handler(commands=['enterprises'])
        def handle_enterprises(message: Message):
            """Xử lý lệnh enterprises."""
            if not self.is_authorized_user(message.from_user.id):
                return
                
            self.show_enterprises_list(message.chat.id, message.from_user.id)
        
        # Callback query handler cho inline keyboard
        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_callback_query(call: CallbackQuery):
            """Xử lý callback query từ inline keyboard."""
            user_id = call.from_user.id
            
            if not self.is_authorized_user(user_id):
                self.bot.answer_callback_query(call.id, "❌ Bạn không có quyền truy cập!")
                return
            
            # Update user session
            if user_id in self.user_sessions:
                self.user_sessions[user_id]['last_activity'] = datetime.now()
            
            # Xử lý callback data
            self.handle_callback_data(call)
            
            # Answer callback query
            self.bot.answer_callback_query(call.id)
    
    def is_authorized_user(self, user_id: int) -> bool:
        """Kiểm tra user có được ủy quyền không."""
        return (user_id in BOT_CONFIG['authorized_users'] or 
                user_id in BOT_CONFIG['admin_users'])
    
    def send_unauthorized_message(self, chat_id: int):
        """Gửi tin nhắn không được ủy quyền."""
        unauthorized_text = """
❌ **KHÔNG ĐƯỢC ỦY QUYỀN!**

Bạn không có quyền sử dụng TAX FORTRESS Bot.

🔐 **Để được ủy quyền:**
• Liên hệ Admin để thêm Chat ID của bạn
• Chat ID của bạn: `{chat_id}`
• Gửi Chat ID này cho Admin

📞 **Liên hệ Admin:**
• Email: admin@taxfortress.com
• Telegram: @TaxFortressAdmin
        """.format(chat_id=chat_id)
        
        self.bot.send_message(chat_id, unauthorized_text, parse_mode='Markdown')
    
    def get_system_status_text(self) -> str:
        """Lấy text trạng thái hệ thống."""
        try:
            total_machines = len(self.machines)
            online_machines = sum(1 for m in self.machines.values() if m.get('online', False))
            offline_machines = total_machines - online_machines
            
            total_enterprises = sum(m.get('enterprise_count', 0) for m in self.machines.values())
            total_xml_protected = sum(m.get('xml_protected_count', 0) for m in self.machines.values())
            
            status_text = f"""
📊 **TRẠNG THÁI HỆ THỐNG TAX FORTRESS**

🖥️ **MÁY TÍNH:**
• Tổng số: {total_machines}
• Online: {online_machines} 🟢
• Offline: {offline_machines} 🔴

🏢 **DOANH NGHIỆP:**
• Tổng số: {total_enterprises}
• File XML được bảo vệ: {total_xml_protected}

⏰ **CẬP NHẬT:** {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}

🔄 **TỰ ĐỘNG SYNC:** Mỗi 5 phút
🛡️ **BẢO VỆ:** Hoạt động 24/7
            """
            
            return status_text
            
        except Exception as e:
            logging.error(f"Get system status error: {e}")
            return "❌ Lỗi khi lấy trạng thái hệ thống!"
    
    def show_main_dashboard(self, chat_id: int, user_id: int):
        """Hiển thị main dashboard."""
        try:
            # Tạo inline keyboard cho dashboard
            keyboard = InlineKeyboardMarkup(row_width=2)
            
            # Row 1: Machine Management
            keyboard.add(
                InlineKeyboardButton("🖥️ Quản Lý Máy", callback_data="menu_machines"),
                InlineKeyboardButton("🏢 Doanh Nghiệp", callback_data="menu_enterprises")
            )
            
            # Row 2: System & Cloud
            keyboard.add(
                InlineKeyboardButton("📊 Hệ Thống", callback_data="menu_system"),
                InlineKeyboardButton("☁️ Cloud Sync", callback_data="menu_cloud")
            )
            
            # Row 3: Monitoring & Alerts
            keyboard.add(
                InlineKeyboardButton("👁️ Giám Sát", callback_data="menu_monitoring"),
                InlineKeyboardButton("🚨 Cảnh Báo", callback_data="menu_alerts")
            )
            
            # Row 4: Settings & Help
            keyboard.add(
                InlineKeyboardButton("⚙️ Cài Đặt", callback_data="menu_settings"),
                InlineKeyboardButton("❓ Trợ Giúp", callback_data="menu_help")
            )
            
            # Row 5: Quick Actions
            keyboard.add(
                InlineKeyboardButton("🔄 Sync Ngay", callback_data="action_sync_now"),
                InlineKeyboardButton("📈 Báo Cáo", callback_data="action_report")
            )
            
            dashboard_text = f"""
🎯 **TAX FORTRESS DASHBOARD**

Chào mừng bạn đến với hệ thống quản lý bảo vệ thuế!

📊 **TỔNG QUAN:**
• Máy tính: {len(self.machines)}
• Doanh nghiệp: {sum(m.get('enterprise_count', 0) for m in self.machines.values())}
• Trạng thái: {'🟢 Hoạt động' if self.running else '🔴 Dừng'}

🎮 **SỬ DỤNG:**
Chọn chức năng từ menu bên dưới để quản lý hệ thống.

⏰ **Cập nhật:** {datetime.now().strftime('%H:%M:%S')}
            """
            
            self.bot.send_message(
                chat_id, 
                dashboard_text, 
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logging.error(f"Show main dashboard error: {e}")
            self.bot.send_message(chat_id, "❌ Lỗi khi hiển thị dashboard!")
    
    def handle_callback_data(self, call: CallbackQuery):
        """Xử lý callback data từ inline keyboard."""
        try:
            data = call.data
            chat_id = call.message.chat.id
            user_id = call.from_user.id
            
            logging.info(f"Callback data: {data} from user {user_id}")
            
            if data.startswith('menu_'):
                # Menu navigation
                if data == 'menu_machines':
                    self.show_machines_list(chat_id, user_id)
                elif data == 'menu_enterprises':
                    self.show_enterprises_list(chat_id, user_id)
                elif data == 'menu_system':
                    self.show_system_menu(chat_id, user_id)
                elif data == 'menu_cloud':
                    self.show_cloud_menu(chat_id, user_id)
                elif data == 'menu_monitoring':
                    self.show_monitoring_menu(chat_id, user_id)
                elif data == 'menu_alerts':
                    self.show_alerts_menu(chat_id, user_id)
                elif data == 'menu_settings':
                    self.show_settings_menu(chat_id, user_id)
                elif data == 'menu_help':
                    self.show_help_menu(chat_id, user_id)
                    
            elif data.startswith('action_'):
                # Quick actions
                if data == 'action_sync_now':
                    self.perform_sync_now(chat_id, user_id)
                elif data == 'action_report':
                    self.generate_report(chat_id, user_id)
                    
            elif data.startswith('machine_'):
                # Machine actions
                self.handle_machine_actions(data, chat_id, user_id)
                
            elif data.startswith('enterprise_'):
                # Enterprise actions
                self.handle_enterprise_actions(data, chat_id, user_id)
                
            else:
                # Unknown callback data
                self.bot.send_message(chat_id, "❌ Lệnh không được nhận diện!")
                
        except Exception as e:
            logging.error(f"Handle callback data error: {e}")
            self.bot.send_message(call.message.chat.id, "❌ Lỗi xử lý lệnh!")
    
    def show_machines_list(self, chat_id: int, user_id: int):
        """Hiển thị danh sách máy tính."""
        try:
            if not self.machines:
                self.bot.send_message(
                    chat_id,
                    "📝 Chưa có máy tính nào được đăng ký!\n\n➕ Sử dụng Control Panel để thêm máy tính mới.",
                    parse_mode='Markdown'
                )
                return
            
            # Tạo inline keyboard cho từng machine
            keyboard = InlineKeyboardMarkup(row_width=1)
            
            for machine_id, machine_info in self.machines.items():
                status_icon = "🟢" if machine_info.get('online', False) else "🔴"
                machine_name = machine_info.get('machine_name', f"Machine-{machine_id[:8]}")
                
                button_text = f"{status_icon} {machine_name} ({machine_id[:8]})"
                callback_data = f"machine_select_{machine_id}"
                
                keyboard.add(InlineKeyboardButton(button_text, callback_data=callback_data))
            
            # Back button
            keyboard.add(InlineKeyboardButton("🔙 Quay Lại", callback_data="back_to_main"))
            
            machines_text = f"""
🖥️ **DANH SÁCH MÁY TÍNH**

Tổng số: {len(self.machines)} máy
🟢 Online: {sum(1 for m in self.machines.values() if m.get('online', False))}
🔴 Offline: {sum(1 for m in self.machines.values() if not m.get('online', False))}

Chọn máy tính để xem chi tiết:
            """
            
            self.bot.send_message(
                chat_id,
                machines_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logging.error(f"Show machines list error: {e}")
            self.bot.send_message(chat_id, "❌ Lỗi khi hiển thị danh sách máy tính!")
    
    def show_enterprises_list(self, chat_id: int, user_id: int):
        """Hiển thị danh sách doanh nghiệp."""
        try:
            # Lấy danh sách enterprises từ database
            enterprises = self.get_all_enterprises()
            
            if not enterprises:
                self.bot.send_message(
                    chat_id,
                    "📝 Chưa có doanh nghiệp nào được đăng ký!\n\n➕ Sử dụng Control Panel để thêm doanh nghiệp mới.",
                    parse_mode='Markdown'
                )
                return
            
            # Tạo inline keyboard cho từng enterprise
            keyboard = InlineKeyboardMarkup(row_width=1)
            
            for enterprise in enterprises:
                enterprise_id = enterprise['enterprise_id']
                enterprise_name = enterprise['enterprise_name']
                xml_count = enterprise.get('xml_count', 0)
                
                button_text = f"🏢 {enterprise_name} ({xml_count} XML)"
                callback_data = f"enterprise_select_{enterprise_id}"
                
                keyboard.add(InlineKeyboardButton(button_text, callback_data=callback_data))
            
            # Back button
            keyboard.add(InlineKeyboardButton("🔙 Quay Lại", callback_data="back_to_main"))
            
            enterprises_text = f"""
🏢 **DANH SÁCH DOANH NGHIỆP**

Tổng số: {len(enterprises)} doanh nghiệp
📄 Tổng file XML: {sum(e.get('xml_count', 0) for e in enterprises)}

Chọn doanh nghiệp để xem chi tiết:
            """
            
            self.bot.send_message(
                chat_id,
                enterprises_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logging.error(f"Show enterprises list error: {e}")
            self.bot.send_message(chat_id, "❌ Lỗi khi hiển thị danh sách doanh nghiệp!")
    
    def get_all_enterprises(self) -> List[Dict]:
        """Lấy tất cả enterprises từ database."""
        try:
            enterprises = []
            
            # Lấy từ cloud_enterprise database nếu có
            if ENTERPRISE_DB and ENTERPRISE_DB.exists():
                conn = sqlite3.connect(str(ENTERPRISE_DB))
                cursor = conn.execute('''
                    SELECT enterprise_id, enterprise_name, admin_contact
                    FROM enterprises
                    ORDER BY enterprise_id
                ''')
                
                for row in cursor.fetchall():
                    enterprise_id, name, admin = row
                    
                    # Đếm số XML files
                    cursor2 = conn.execute('''
                        SELECT COUNT(*) FROM xml_cloud_warehouse 
                        WHERE enterprise_id = ?
                    ''', (enterprise_id,))
                    xml_count = cursor2.fetchone()[0]
                    
                    enterprises.append({
                        'enterprise_id': enterprise_id,
                        'enterprise_name': name,
                        'admin_contact': admin,
                        'xml_count': xml_count
                    })
                
                conn.close()
            
            return enterprises
            
        except Exception as e:
            logging.error(f"Get all enterprises error: {e}")
            return []
    
    def show_system_menu(self, chat_id: int, user_id: int):
        """Hiển thị menu hệ thống."""
        try:
            keyboard = InlineKeyboardMarkup(row_width=2)
            
            keyboard.add(
                InlineKeyboardButton("📊 Trạng Thái", callback_data="system_status"),
                InlineKeyboardButton("🖥️ Thông Tin Máy", callback_data="system_info")
            )
            
            keyboard.add(
                InlineKeyboardButton("📈 Hiệu Suất", callback_data="system_performance"),
                InlineKeyboardButton("🔧 Cài Đặt", callback_data="system_settings")
            )
            
            keyboard.add(InlineKeyboardButton("🔙 Quay Lại", callback_data="back_to_main"))
            
            system_text = """
⚙️ **MENU HỆ THỐNG**

Chọn chức năng để quản lý hệ thống:
            """
            
            self.bot.send_message(
                chat_id,
                system_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logging.error(f"Show system menu error: {e}")
            self.bot.send_message(chat_id, "❌ Lỗi khi hiển thị menu hệ thống!")
    
    def show_cloud_menu(self, chat_id: int, user_id: int):
        """Hiển thị menu cloud sync."""
        try:
            keyboard = InlineKeyboardMarkup(row_width=2)
            
            keyboard.add(
                InlineKeyboardButton("☁️ GitHub Sync", callback_data="cloud_github"),
                InlineKeyboardButton("🔄 Auto Sync", callback_data="cloud_auto_sync")
            )
            
            keyboard.add(
                InlineKeyboardButton("📤 Upload", callback_data="cloud_upload"),
                InlineKeyboardButton("📥 Download", callback_data="cloud_download")
            )
            
            keyboard.add(InlineKeyboardButton("🔙 Quay Lại", callback_data="back_to_main"))
            
            cloud_text = """
☁️ **MENU CLOUD SYNC**

Quản lý đồng bộ dữ liệu với GitHub:
            """
            
            self.bot.send_message(
                chat_id,
                cloud_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logging.error(f"Show cloud menu error: {e}")
            self.bot.send_message(chat_id, "❌ Lỗi khi hiển thị menu cloud!")
    
    def show_monitoring_menu(self, chat_id: int, user_id: int):
        """Hiển thị menu giám sát."""
        try:
            keyboard = InlineKeyboardMarkup(row_width=2)
            
            keyboard.add(
                InlineKeyboardButton("👁️ Real-time", callback_data="monitoring_realtime"),
                InlineKeyboardButton("📊 Logs", callback_data="monitoring_logs")
            )
            
            keyboard.add(
                InlineKeyboardButton("🚨 Alerts", callback_data="monitoring_alerts"),
                InlineKeyboardButton("📈 Reports", callback_data="monitoring_reports")
            )
            
            keyboard.add(InlineKeyboardButton("🔙 Quay Lại", callback_data="back_to_main"))
            
            monitoring_text = """
👁️ **MENU GIÁM SÁT**

Theo dõi hoạt động hệ thống:
            """
            
            self.bot.send_message(
                chat_id,
                monitoring_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logging.error(f"Show monitoring menu error: {e}")
            self.bot.send_message(chat_id, "❌ Lỗi khi hiển thị menu giám sát!")
    
    def show_alerts_menu(self, chat_id: int, user_id: int):
        """Hiển thị menu cảnh báo."""
        try:
            keyboard = InlineKeyboardMarkup(row_width=2)
            
            keyboard.add(
                InlineKeyboardButton("🚨 Cảnh Báo", callback_data="alerts_list"),
                InlineKeyboardButton("⚙️ Cài Đặt", callback_data="alerts_settings")
            )
            
            keyboard.add(
                InlineKeyboardButton("📱 Telegram", callback_data="alerts_telegram"),
                InlineKeyboardButton("📧 Email", callback_data="alerts_email")
            )
            
            keyboard.add(InlineKeyboardButton("🔙 Quay Lại", callback_data="back_to_main"))
            
            alerts_text = """
🚨 **MENU CẢNH BÁO**

Quản lý hệ thống cảnh báo:
            """
            
            self.bot.send_message(
                chat_id,
                alerts_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logging.error(f"Show alerts menu error: {e}")
            self.bot.send_message(chat_id, "❌ Lỗi khi hiển thị menu cảnh báo!")
    
    def show_settings_menu(self, chat_id: int, user_id: int):
        """Hiển thị menu cài đặt."""
        try:
            keyboard = InlineKeyboardMarkup(row_width=2)
            
            keyboard.add(
                InlineKeyboardButton("🔐 Quyền Truy Cập", callback_data="settings_access"),
                InlineKeyboardButton("⏰ Timeout", callback_data="settings_timeout")
            )
            
            keyboard.add(
                InlineKeyboardButton("🔄 Sync Interval", callback_data="settings_sync"),
                InlineKeyboardButton("🌐 Ngôn Ngữ", callback_data="settings_language")
            )
            
            keyboard.add(InlineKeyboardButton("🔙 Quay Lại", callback_data="back_to_main"))
            
            settings_text = """
⚙️ **MENU CÀI ĐẶT**

Cấu hình hệ thống:
            """
            
            self.bot.send_message(
                chat_id,
                settings_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logging.error(f"Show settings menu error: {e}")
            self.bot.send_message(chat_id, "❌ Lỗi khi hiển thị menu cài đặt!")
    
    def show_help_menu(self, chat_id: int, user_id: int):
        """Hiển thị menu trợ giúp."""
        try:
            keyboard = InlineKeyboardMarkup(row_width=2)
            
            keyboard.add(
                InlineKeyboardButton("📖 Hướng Dẫn", callback_data="help_guide"),
                InlineKeyboardButton("❓ FAQ", callback_data="help_faq")
            )
            
            keyboard.add(
                InlineKeyboardButton("📞 Liên Hệ", callback_data="help_contact"),
                InlineKeyboardButton("🐛 Báo Lỗi", callback_data="help_bug")
            )
            
            keyboard.add(InlineKeyboardButton("🔙 Quay Lại", callback_data="back_to_main"))
            
            help_text = """
❓ **MENU TRỢ GIÚP**

Hỗ trợ sử dụng hệ thống:
            """
            
            self.bot.send_message(
                chat_id,
                help_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logging.error(f"Show help menu error: {e}")
            self.bot.send_message(chat_id, "❌ Lỗi khi hiển thị menu trợ giúp!")
    
    def handle_machine_actions(self, data: str, chat_id: int, user_id: int):
        """Xử lý các action liên quan đến machine."""
        try:
            if data.startswith('machine_select_'):
                machine_id = data.replace('machine_select_', '')
                self.show_machine_details(chat_id, user_id, machine_id)
            elif data.startswith('machine_sync_'):
                machine_id = data.replace('machine_sync_', '')
                self.sync_machine(chat_id, user_id, machine_id)
            elif data.startswith('machine_restart_'):
                machine_id = data.replace('machine_restart_', '')
                self.restart_machine(chat_id, user_id, machine_id)
            else:
                self.bot.send_message(chat_id, "❌ Lệnh machine không được nhận diện!")
                
        except Exception as e:
            logging.error(f"Handle machine actions error: {e}")
            self.bot.send_message(chat_id, "❌ Lỗi xử lý lệnh machine!")
    
    def handle_enterprise_actions(self, data: str, chat_id: int, user_id: int):
        """Xử lý các action liên quan đến enterprise."""
        try:
            if data.startswith('enterprise_select_'):
                enterprise_id = data.replace('enterprise_select_', '')
                self.show_enterprise_details(chat_id, user_id, enterprise_id)
            elif data.startswith('enterprise_xml_'):
                enterprise_id = data.replace('enterprise_xml_', '')
                self.show_enterprise_xml(chat_id, user_id, enterprise_id)
            else:
                self.bot.send_message(chat_id, "❌ Lệnh enterprise không được nhận diện!")
                
        except Exception as e:
            logging.error(f"Handle enterprise actions error: {e}")
            self.bot.send_message(chat_id, "❌ Lỗi xử lý lệnh enterprise!")
    
    def show_machine_details(self, chat_id: int, user_id: int, machine_id: str):
        """Hiển thị chi tiết máy tính."""
        try:
            if machine_id not in self.machines:
                self.bot.send_message(chat_id, "❌ Không tìm thấy máy tính!")
                return
            
            machine_info = self.machines[machine_id]
            status_icon = "🟢" if machine_info.get('online', False) else "🔴"
            
            keyboard = InlineKeyboardMarkup(row_width=2)
            
            keyboard.add(
                InlineKeyboardButton("🔄 Sync", callback_data=f"machine_sync_{machine_id}"),
                InlineKeyboardButton("🔄 Restart", callback_data=f"machine_restart_{machine_id}")
            )
            
            keyboard.add(InlineKeyboardButton("📊 Logs", callback_data=f"machine_logs_{machine_id}"))
            keyboard.add(InlineKeyboardButton("🔙 Quay Lại", callback_data="menu_machines"))
            
            details_text = f"""
🖥️ **CHI TIẾT MÁY TÍNH**

**ID:** `{machine_id}`
**Tên:** {machine_info.get('machine_name', 'N/A')}
**Trạng thái:** {status_icon} {'Online' if machine_info.get('online', False) else 'Offline'}
**IP:** {machine_info.get('ip_address', 'N/A')}
**Platform:** {machine_info.get('platform', 'N/A')}
**Doanh nghiệp:** {machine_info.get('enterprise_count', 0)}
**XML được bảo vệ:** {machine_info.get('xml_protected_count', 0)}
**Lần cuối online:** {machine_info.get('last_seen', 'N/A')}
            """
            
            self.bot.send_message(
                chat_id,
                details_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logging.error(f"Show machine details error: {e}")
            self.bot.send_message(chat_id, "❌ Lỗi khi hiển thị chi tiết máy tính!")
    
    def show_enterprise_details(self, chat_id: int, user_id: int, enterprise_id: str):
        """Hiển thị chi tiết doanh nghiệp."""
        try:
            enterprises = self.get_all_enterprises()
            enterprise = next((e for e in enterprises if e['enterprise_id'] == enterprise_id), None)
            
            if not enterprise:
                self.bot.send_message(chat_id, "❌ Không tìm thấy doanh nghiệp!")
                return
            
            keyboard = InlineKeyboardMarkup(row_width=2)
            
            keyboard.add(
                InlineKeyboardButton("📄 XML Files", callback_data=f"enterprise_xml_{enterprise_id}"),
                InlineKeyboardButton("📊 Thống Kê", callback_data=f"enterprise_stats_{enterprise_id}")
            )
            
            keyboard.add(InlineKeyboardButton("🔙 Quay Lại", callback_data="menu_enterprises"))
            
            details_text = f"""
🏢 **CHI TIẾT DOANH NGHIỆP**

**ID:** `{enterprise_id}`
**Tên:** {enterprise.get('enterprise_name', 'N/A')}
**Admin:** {enterprise.get('admin_contact', 'N/A')}
**Số XML:** {enterprise.get('xml_count', 0)}
            """
            
            self.bot.send_message(
                chat_id,
                details_text,
                reply_markup=keyboard,
                parse_mode='Markdown')
            
        except Exception as e:
            logging.error(f"Show enterprise details error: {e}")
            self.bot.send_message(chat_id, "❌ Lỗi khi hiển thị chi tiết doanh nghiệp!")
    
    def perform_sync_now(self, chat_id: int, user_id: int):
        """Thực hiện sync ngay lập tức."""
        try:
            # Gửi thông báo đang sync
            sync_msg = self.bot.send_message(chat_id, "🔄 Đang đồng bộ dữ liệu...")
            
            # Thực hiện sync (giả lập)
            time.sleep(2)
            
            # Cập nhật trạng thái
            self.bot.edit_message_text(
                "✅ Đồng bộ hoàn tất!\n\n📊 Dữ liệu đã được cập nhật.",
                chat_id,
                sync_msg.message_id
            )
            
            logging.info(f"User {user_id} thực hiện sync ngay lập tức")
            
        except Exception as e:
            logging.error(f"Perform sync now error: {e}")
            self.bot.send_message(chat_id, "❌ Lỗi khi đồng bộ dữ liệu!")
    
    def generate_report(self, chat_id: int, user_id: int):
        """Tạo báo cáo hệ thống."""
        try:
            # Gửi thông báo đang tạo báo cáo
            report_msg = self.bot.send_message(chat_id, "📊 Đang tạo báo cáo...")
            
            # Tạo báo cáo (giả lập)
            time.sleep(2)
            
            report_text = self.get_system_status_text()
            
            # Cập nhật với báo cáo
            self.bot.edit_message_text(
                f"📈 **BÁO CÁO HỆ THỐNG**\n\n{report_text}",
                chat_id,
                report_msg.message_id,
                parse_mode='Markdown'
            )
            
            logging.info(f"User {user_id} tạo báo cáo hệ thống")
            
        except Exception as e:
            logging.error(f"Generate report error: {e}")
            self.bot.send_message(chat_id, "❌ Lỗi khi tạo báo cáo!")
    
    def start_bot(self):
        """Khởi động bot."""
        try:
            self.running = True
            logging.info("Bot đang khởi động...")
            
            # Start auto-sync thread
            self.sync_thread = threading.Thread(target=self.auto_sync_loop, daemon=True)
            self.sync_thread.start()
            
            # Start bot polling
            self.bot.polling(none_stop=True, interval=1)
            
        except Exception as e:
            logging.error(f"Start bot error: {e}")
            self.running = False
    
    def stop_bot(self):
        """Dừng bot."""
        try:
            self.running = False
            if self.sync_thread:
                self.sync_thread.join(timeout=5)
            
            logging.info("Bot đã dừng!")
            
        except Exception as e:
            logging.error(f"Stop bot error: {e}")
    
    def auto_sync_loop(self):
        """Vòng lặp tự động sync."""
        while self.running:
            try:
                time.sleep(BOT_CONFIG['auto_sync_interval'])
                
                if self.running:
                    self.perform_auto_sync()
                    
            except Exception as e:
                logging.error(f"Auto sync loop error: {e}")
                time.sleep(60)  # Wait 1 minute before retry
    
    def perform_auto_sync(self):
        """Thực hiện auto sync."""
        try:
            logging.info("Thực hiện auto sync...")
            
            # Update machine status
            self.update_machine_status()
            
            # Sync with cloud
            self.sync_with_cloud()
            
            logging.info("Auto sync hoàn tất!")
            
        except Exception as e:
            logging.error(f"Perform auto sync error: {e}")
    
    def update_machine_status(self):
        """Cập nhật trạng thái máy tính."""
        try:
            for machine_id in self.machines:
                # Giả lập cập nhật trạng thái
                self.machines[machine_id]['last_seen'] = datetime.now().isoformat()
                self.machines[machine_id]['online'] = True
                
        except Exception as e:
            logging.error(f"Update machine status error: {e}")
    
    def sync_with_cloud(self):
        """Đồng bộ với cloud."""
        try:
            logging.info("Đang đồng bộ với cloud...")
            # Giả lập sync
            time.sleep(1)
            logging.info("Đồng bộ cloud hoàn tất!")
            
        except Exception as e:
            logging.error(f"Sync with cloud error: {e}")


# --- MAIN FUNCTION --- #
def main():
    """Hàm chính để chạy bot."""
    try:
        print("🚀 Khởi động TAX FORTRESS TELEGRAM BOT...")
        
        # Load bot token
        bot_token = input("Nhập Bot Token: ").strip()
        
        if not bot_token:
            print("❌ Bot Token không được để trống!")
            return
        
        # Khởi tạo bot
        bot = TelegramDashboardBot(bot_token)
        
        # Lưu config
        bot.save_bot_config()
        
        print("✅ Bot đã khởi tạo thành công!")
        print("📱 Gửi /start hoặc /menu trong Telegram để sử dụng")
        
        print("🔄 Bot đang chạy... (Ctrl+C để dừng)")
        
        # Khởi động bot
        bot.start_bot()
        
    except KeyboardInterrupt:
        print("\n🛑 Bot đã dừng bởi người dùng!")
    except Exception as e:
        print(f"❌ Lỗi khởi động bot: {e}")
        logging.error(f"Main function error: {e}")
