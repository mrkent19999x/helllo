# 🖥️ HƯỚNG DẪN SETUP MÁY CHỦ (MASTER)

## 🎯 **MÁY CHỦ LÀM GÌ?**
- Quản lý tất cả doanh nghiệp
- Điều khiển toàn bộ hệ thống
- Đồng bộ với cloud services
- Nhận cảnh báo từ Telegram Bot

## 🚀 **SETUP NHANH (5 PHÚT)**

### **Bước 1: Chuẩn bị**
- ✅ Cài đặt Python 3.7+
- ✅ Kết nối internet
- ✅ Quyền admin

### **Bước 2: Chạy setup**
```bash
# Chạy file này
setup_master.bat
```

### **Bước 3: Nhập thông tin**
- GitHub Personal Access Token
- Telegram Bot Token
- Tên repository GitHub

### **Bước 4: Hoàn thành**
Hệ thống sẽ tự động:
- Cài đặt thư viện cần thiết
- Tạo cấu trúc thư mục
- Khởi tạo database
- Cấu hình cloud sync

## 📋 **CHI TIẾT TỪNG BƯỚC**

### **1. Tạo GitHub Repository**
```
1. Vào GitHub.com
2. Tạo repository mới (private)
3. Copy repository URL
4. Tạo Personal Access Token
```

### **2. Tạo Telegram Bot**
```
1. Chat với @BotFather
2. Gửi lệnh /newbot
3. Đặt tên bot
4. Copy Bot Token
```

### **3. Chạy Setup Script**
```
1. Chạy setup_master.bat
2. Nhập GitHub Token
3. Nhập Bot Token
4. Nhập Repository URL
5. Chờ cài đặt hoàn thành
```

## ⚙️ **CẤU HÌNH SAU KHI SETUP**

### **File cấu hình:**
```json
{
  "system": {
    "mode": "master",
    "auto_sync_interval": 300
  },
  "github": {
    "enabled": true,
    "token": "your_token_here",
    "repository": "username/repo"
  },
  "telegram": {
    "enabled": true,
    "bot_token": "your_bot_token"
  }
}
```

### **Thư mục được tạo:**
```
🏗️ TAX_FORTRESS_ULTIMATE/
├── 📁 config/           # Cấu hình hệ thống
├── 📁 logs/            # Log hoạt động
├── 📁 enterprises/     # Dữ liệu doanh nghiệp
├── 📁 xml_templates/   # Template XML gốc
└── 📁 backups/         # Backup dữ liệu
```

## ✅ **KIỂM TRA SAU KHI SETUP**

### **1. Test kết nối GitHub:**
```bash
python -c "import cloud_enterprise; print('GitHub OK')"
```

### **2. Test Telegram Bot:**
```bash
python -c "import telegram_dashboard_bot; print('Telegram OK')"
```

### **3. Test database:**
```bash
python -c "import cloud_enterprise; print('Database OK')"
```

## 🤖 **SỬ DỤNG TELEGRAM BOT**

### **Các lệnh có sẵn:**
- `/start` - Khởi động bot
- `/status` - Kiểm tra trạng thái
- `/sync` - Đồng bộ thủ công
- `/logs` - Xem log hoạt động
- `/add_enterprise` - Thêm doanh nghiệp

### **Thêm Chat ID:**
```
1. Chat với bot
2. Gửi lệnh /start
3. Copy Chat ID từ log
4. Thêm vào authorized_chat_ids
```

## 🔧 **XỬ LÝ LỖI THƯỜNG GẶP**

### **Lỗi Python không tìm thấy:**
```
Giải pháp: Cài đặt Python và thêm vào PATH
```

### **Lỗi thư viện:**
```
Giải pháp: Chạy pip install -r requirements.txt
```

### **Lỗi GitHub API:**
```
Giải pháp: Kiểm tra token và repository URL
```

### **Lỗi Telegram Bot:**
```
Giải pháp: Kiểm tra bot token và internet
```

## 📞 **HỖ TRỢ**
- Xem file `TROUBLESHOOTING.md`
- Kiểm tra log trong thư mục `logs/`
- Liên hệ admin hệ thống

---
**Máy chủ đã sẵn sàng điều khiển hệ thống!** 🎯
