# 💻 HƯỚNG DẪN SETUP MÁY CON (SLAVE)

## 🎯 **MÁY CON LÀM GÌ?**
- Nhận dữ liệu từ máy chủ
- Bảo vệ file XML cục bộ
- Đồng bộ tự động với GitHub
- Gửi cảnh báo về máy chủ

## 🚀 **SETUP NHANH (2 PHÚT)**

### **Bước 1: Chuẩn bị**
- ✅ Cài đặt Python 3.7+
- ✅ Kết nối internet
- ✅ File `cloud_enterprise.py` từ máy chủ

### **Bước 2: Chạy setup**
```bash
# Chạy file này
setup_slave.bat
```

### **Bước 3: Nhập thông tin**
- GitHub Personal Access Token (từ máy chủ)
- Repository URL (từ máy chủ)
- Machine ID (tự động tạo)

### **Bước 4: Hoàn thành**
Hệ thống sẽ tự động:
- Tạo Machine ID duy nhất
- Cài đặt thư viện cần thiết
- Đăng ký với máy chủ
- Bắt đầu bảo vệ file

## 📋 **CHI TIẾT TỪNG BƯỚC**

### **1. Copy file từ máy chủ**
```
1. Copy thư mục SLAVE_SETUP
2. Copy file cloud_enterprise.py
3. Copy file config từ máy chủ
```

### **2. Chạy Setup Script**
```
1. Chạy setup_slave.bat
2. Nhập GitHub Token
3. Nhập Repository URL
4. Chờ cài đặt hoàn thành
```

### **3. Kiểm tra đăng ký**
```
1. Mở Telegram Bot
2. Gửi lệnh /status
3. Kiểm tra Machine ID
4. Xác nhận kết nối
```

## ⚙️ **CẤU HÌNH SAU KHI SETUP**

### **File cấu hình:**
```json
{
  "system": {
    "mode": "slave",
    "auto_sync_interval": 300,
    "machine_id": "auto_generated"
  },
  "github": {
    "enabled": true,
    "token": "from_master",
    "repository": "from_master"
  },
  "telegram": {
    "enabled": true,
    "bot_token": "from_master"
  }
}
```

### **Thư mục được tạo:**
```
🏗️ TAX_FORTRESS_ULTIMATE/
├── 📁 config/           # Cấu hình từ máy chủ
├── 📁 logs/            # Log hoạt động
├── 📁 enterprises/     # Dữ liệu nhận từ máy chủ
├── 📁 xml_templates/   # Template từ GitHub
└── 📁 local_protection/ # File bảo vệ cục bộ
```

## ✅ **KIỂM TRA SAU KHI SETUP**

### **1. Test kết nối GitHub:**
```bash
python -c "import cloud_enterprise; print('GitHub OK')"
```

### **2. Test Machine ID:**
```bash
python -c "import cloud_enterprise; print('Machine ID OK')"
```

### **3. Test bảo vệ file:**
```bash
# Tạo file XML test
echo "<test>data</test>" > test.xml
# Kiểm tra xem có bị bảo vệ không
```

## 🤖 **SỬ DỤNG TELEGRAM BOT**

### **Các lệnh có sẵn:**
- `/start` - Khởi động bot
- `/status` - Kiểm tra trạng thái máy con
- `/sync` - Đồng bộ thủ công
- `/logs` - Xem log hoạt động

### **Thông báo tự động:**
- Khi file XML bị sửa đổi
- Khi đồng bộ thành công/thất bại
- Khi có lỗi xảy ra

## 🔧 **XỬ LÝ LỖI THƯỜNG GẶP**

### **Lỗi không kết nối máy chủ:**
```
Giải pháp: Kiểm tra internet và GitHub token
```

### **Lỗi Machine ID:**
```
Giải pháp: Xóa file config và chạy lại setup
```

### **Lỗi bảo vệ file:**
```
Giải pháp: Kiểm tra quyền ghi file
```

### **Lỗi đồng bộ:**
```
Giải pháp: Kiểm tra GitHub repository
```

## 🔄 **HOẠT ĐỘNG TỰ ĐỘNG**

### **Bảo vệ file XML:**
```
1. Phát hiện file XML bị sửa đổi
2. So sánh với template gốc
3. Thay thế file giả bằng file gốc
4. Gửi cảnh báo về máy chủ
```

### **Đồng bộ với GitHub:**
```
1. Kiểm tra thay đổi mỗi 5 phút
2. Tải template mới từ GitHub
3. Cập nhật database cục bộ
4. Ghi log hoạt động
```

## 📊 **THEO DÕI HOẠT ĐỘNG**

### **Log file:**
```
📁 logs/
├── protection.log      # Log bảo vệ file
├── sync.log          # Log đồng bộ
├── error.log         # Log lỗi
└── machine.log       # Log máy con
```

### **Thống kê:**
- Số file được bảo vệ
- Số lần đồng bộ
- Thời gian hoạt động
- Lỗi xảy ra

## 📞 **HỖ TRỢ**
- Xem file `TROUBLESHOOTING.md`
- Kiểm tra log trong thư mục `logs/`
- Liên hệ admin qua Telegram Bot

---
**Máy con đã sẵn sàng bảo vệ file!** 🛡️
