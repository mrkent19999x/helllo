# 🔧 TROUBLESHOOTING - XỬ LÝ LỖI

## 🚨 **LỖI THƯỜNG GẶP VÀ CÁCH KHẮC PHỤC**

### **1. LỖI PYTHON**

#### **Python không tìm thấy:**
```
Lỗi: 'python' is not recognized
Giải pháp: Cài đặt Python và thêm vào PATH
```

#### **Phiên bản Python quá cũ:**
```
Lỗi: Python version < 3.7
Giải pháp: Cập nhật lên Python 3.7+
```

### **2. LỖI THƯ VIỆN**

#### **Module không tìm thấy:**
```
Lỗi: ModuleNotFoundError: No module named 'requests'
Giải pháp: pip install requests
```

#### **Phiên bản thư viện không tương thích:**
```
Lỗi: Version conflict
Giải pháp: pip install --upgrade package_name
```

### **3. LỖI GITHUB API**

#### **Token không hợp lệ:**
```
Lỗi: 401 Unauthorized
Giải pháp: Tạo lại Personal Access Token
```

#### **Repository không tồn tại:**
```
Lỗi: 404 Not Found
Giải pháp: Kiểm tra tên repository
```

#### **Quyền truy cập:**
```
Lỗi: 403 Forbidden
Giải pháp: Kiểm tra quyền của token
```

### **4. LỖI TELEGRAM BOT**

#### **Bot token sai:**
```
Lỗi: Invalid token
Giải pháp: Kiểm tra token từ @BotFather
```

#### **Bot chưa được start:**
```
Lỗi: Bot not started
Giải pháp: Gửi /start cho bot
```

#### **Chat ID không được phép:**
```
Lỗi: Unauthorized chat
Giải pháp: Thêm Chat ID vào authorized_chat_ids
```

### **5. LỖI DATABASE**

#### **Quyền ghi file:**
```
Lỗi: Permission denied
Giải pháp: Chạy với quyền admin
```

#### **Database bị khóa:**
```
Lỗi: Database is locked
Giải pháp: Đóng tất cả ứng dụng đang mở
```

#### **File database bị hỏng:**
```
Lỗi: Database corrupted
Giải pháp: Xóa file .db và chạy lại
```

### **6. LỖI CLOUD SYNC**

#### **Google Drive:**
```
Lỗi: OAuth2 authentication failed
Giải pháp: Kiểm tra credentials.json
```

#### **Dropbox:**
```
Lỗi: Invalid access token
Giải pháp: Tạo lại access token
```

### **7. LỖI FILE PROTECTION**

#### **File không thể ghi:**
```
Lỗi: Access denied
Giải pháp: Kiểm tra quyền file
```

#### **Template không tìm thấy:**
```
Lỗi: Template not found
Giải pháp: Kiểm tra GitHub repository
```

### **8. LỖI MACHINE ID**

#### **Machine ID trùng lặp:**
```
Lỗi: Duplicate Machine ID
Giải pháp: Xóa config và chạy lại setup
```

#### **Machine ID không hợp lệ:**
```
Lỗi: Invalid Machine ID
Giải pháp: Kiểm tra định dạng
```

## 🔍 **CÁCH KIỂM TRA LỖI**

### **1. Kiểm tra log:**
```
📁 logs/
├── error.log          # Lỗi hệ thống
├── sync.log          # Log đồng bộ
├── protection.log    # Log bảo vệ
└── machine.log       # Log máy
```

### **2. Test từng thành phần:**
```bash
# Test Python
python --version

# Test thư viện
python -c "import requests; print('OK')"

# Test GitHub
python -c "import cloud_enterprise; print('GitHub OK')"

# Test Telegram
python -c "import telegram_dashboard_bot; print('Telegram OK')"
```

### **3. Kiểm tra kết nối:**
```bash
# Test internet
ping google.com

# Test GitHub
curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user

# Test Telegram
curl https://api.telegram.org/botYOUR_BOT_TOKEN/getMe
```

## 🛠️ **CÔNG CỤ SỬA LỖI**

### **1. Reset toàn bộ:**
```bash
# Xóa tất cả config
rm -rf config/
rm -rf logs/
rm *.db

# Chạy lại setup
setup_master.bat  # hoặc setup_slave.bat
```

### **2. Repair database:**
```bash
# Sửa database
python -c "import cloud_enterprise; cloud_enterprise.repair_database()"
```

### **3. Test connection:**
```bash
# Test kết nối
python -c "import cloud_enterprise; cloud_enterprise.test_all_connections()"
```

## 📞 **LIÊN HỆ HỖ TRỢ**

### **Thông tin cần cung cấp:**
1. Loại máy (Master/Slave)
2. Phiên bản Python
3. Lỗi cụ thể (copy error message)
4. Log file liên quan
5. Các bước đã thử

### **Kênh hỗ trợ:**
- Telegram Bot: Gửi lệnh /help
- Email: admin@taxfortress.com
- Documentation: Xem file README

---
**Hầu hết lỗi có thể khắc phục bằng cách làm theo hướng dẫn trên!** ✅
