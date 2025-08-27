# 🏗️ TAX FORTRESS ULTIMATE - HƯỚNG DẪN SETUP

## 🎯 **TỔNG QUAN HỆ THỐNG**
TAX FORTRESS ULTIMATE là hệ thống bảo vệ file XML đa doanh nghiệp với khả năng đồng bộ đám mây và điều khiển từ xa qua Telegram Bot.

## 🚀 **HƯỚNG DẪN SETUP NHANH**

### **1️⃣ SETUP MÁY CHỦ (Master)**
```
📁 MASTER_SETUP/
├── 🖥️ Chạy: setup_master.bat
├── 📖 Hướng dẫn: README_MASTER.md
└── ⚙️ Cấu hình: config_template.json
```

**Thời gian:** 5 phút
**Độ khó:** Dễ (2/10)

### **2️⃣ SETUP MÁY CON (Slave)**
```
📁 SLAVE_SETUP/
├── 🚀 Chạy: setup_slave.bat
├── 📋 Hướng dẫn: README_SLAVE.md
└── ⚙️ Cấu hình: config_template.json
```

**Thời gian:** 2 phút
**Độ khó:** Rất dễ (1/10)

## 🏗️ **CẤU TRÚC THƯ MỤC**

```
🏗️ TAX_FORTRESS_ULTIMATE/
├── 📁 MASTER_SETUP/          # Setup máy chủ
│   ├── 🖥️ setup_master.bat
│   ├── 📖 README_MASTER.md
│   ├── ⚙️ config_template.json
│   └── 📁 scripts/
├── 📁 SLAVE_SETUP/           # Setup máy con
│   ├── 🚀 setup_slave.bat
│   ├── 📋 README_SLAVE.md
│   ├── ⚙️ config_template.json
│   └── 📁 scripts/
├── 📁 SHARED_FILES/          # File chung
│   ├── 🐍 cloud_enterprise.py
│   ├── 🤖 telegram_dashboard_bot.py
│   └── 📦 requirements.txt
├── 📁 DOCS/                  # Tài liệu
│   ├── 📖 README.md
│   ├── 🔧 TROUBLESHOOTING.md
│   └── 🏗️ KIẾN_TRÚC_HỆ_THỐNG.md
└── 📁 src/                   # Source code
    └── 🐍 cloud_enterprise.py
```

## ⚡ **SETUP NHANH NHẤT**

### **Máy chủ:**
1. Copy thư mục `MASTER_SETUP` về máy
2. Chạy `setup_master.bat`
3. Nhập thông tin cơ bản
4. Hoàn thành!

### **Máy con:**
1. Copy thư mục `SLAVE_SETUP` về máy
2. Chạy `setup_slave.bat`
3. Nhập thông tin từ máy chủ
4. Hoàn thành!

## 🎯 **YÊU CẦU HỆ THỐNG**
- **Python 3.7+**
- **Windows 10/11**
- **Kết nối internet**
- **Quyền admin** (để cài đặt thư viện)

## 🔧 **HỖ TRỢ**
Nếu gặp vấn đề, xem file `TROUBLESHOOTING.md` trong thư mục `DOCS/`

---
**TAX FORTRESS ULTIMATE** - Hệ thống bảo vệ file XML thông minh! 🛡️
