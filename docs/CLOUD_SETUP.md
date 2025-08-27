# XML WAREHOUSE CLOUD - SETUP GUIDE

## 🌐 HỆ THỐNG BẢO VỆ THUẾ MULTI-ENTERPRISE VỚI CLOUD SYNC

### 📋 TỔNG QUAN HỆ THỐNG

**XML Warehouse Cloud** là phiên bản nâng cao của hệ thống bảo vệ tài liệu thuế với các tính năng:

- ☁️ **Cloud Synchronization**: Đồng bộ tự động với GitHub/Google Drive
- 🏢 **Multi-Enterprise Support**: Quản lý nhiều doanh nghiệp cùng lúc  
- 🤖 **Telegram Bot Control**: Điều khiển và giám sát từ xa
- 💻 **Multi-Machine Deployment**: Triển khai trên nhiều máy tính
- 🔒 **Advanced Security**: MST-based classification & protection
- ⚡ **Instant Protection**: Bảo vệ tức thời <0.1 giây

---

## 📁 CẤU TRÚC FILE

```
XMLWarehouse_Cloud.exe          # Main protection service (ẩn)
XMLWarehouse_CloudControl.exe   # Control panel GUI
```

---

## 🚀 HƯỚNG DẪN CÀI ĐẶT

### Bước 1: Cài Đặt Hệ Thống

1. **Copy 2 file exe** vào thư mục mong muốn
2. **Chạy XMLWarehouse_Cloud.exe** lần đầu để khởi tạo hệ thống
3. **Chạy XMLWarehouse_CloudControl.exe** để mở Control Panel

### Bước 2: Setup Cloud Sync (GitHub)

1. **Mở Control Panel** → Tab "Cloud Sync"  
2. **Tạo GitHub Repository**:
   - Tạo repo private: `xml-warehouse-backup`
   - Tạo Personal Access Token với quyền `repo`
3. **Cấu hình**:
   - Provider: `github`
   - GitHub Token: `[paste token]`
   - Repository: `[username]/xml-warehouse-backup`
4. **Save Config**

### Bước 3: Setup Telegram Bot

1. **Tạo Bot**:
   - Chat với @BotFather trên Telegram
   - `/newbot` → Đặt tên bot
   - Lưu Bot Token
2. **Lấy Chat ID**:
   - Chat với @userinfobot 
   - Lưu Chat ID của mình
3. **Cấu hình trong Control Panel**:
   - Tab "Telegram Bot"
   - Bot Token: `[paste token]`  
   - Chat IDs: `[paste chat id]`
   - **Setup Bot**

### Bước 4: Thêm Enterprises

1. **Control Panel** → Tab "Enterprises"
2. **Add Enterprise**:
   - Enterprise ID: `VN001` (mã doanh nghiệp)
   - Enterprise Name: `Công ty ABC`
   - Admin Contact: `admin@company.com`
3. **Add XML Files** vào Warehouse cho từng Enterprise

---

## 🎮 ĐIỀU KHIỂN QUA TELEGRAM

Sau khi setup xong, có thể điều khiển toàn bộ hệ thống qua Telegram:

```
/status          - Trạng thái hệ thống
/stats           - Thống kê chi tiết  
/enterprises     - Danh sách doanh nghiệp
/sync            - Đồng bộ thủ công
/logs            - Xem log hoạt động
/machine_info    - Thông tin máy tính
/add_enterprise  - Thêm doanh nghiệp mới
/alerts on       - Bật cảnh báo
/help            - Danh sách lệnh
```

---

## 💻 TRIỂN KHAI NHIỀU MÁY

### Master Machine (Máy chính)
1. Setup đầy đủ như trên
2. Tạo và quản lý tất cả Enterprises
3. Setup GitHub + Telegram Bot

### Slave Machines (Máy phụ)  
1. Copy 2 file exe
2. Chạy XMLWarehouse_Cloud.exe để tạo Machine ID
3. Config cùng GitHub repository (read-only)
4. Thêm Chat ID vào Telegram Bot để nhận alerts

---

## 🛡️ CÁCH HOẠT ĐỘNG

1. **File Monitoring**: Theo dõi toàn bộ ổ cứng tìm file XML thuế
2. **Content Analysis**: Phân tích nội dung, extract MST
3. **Warehouse Matching**: So sánh với XML gốc trong kho
4. **Instant Protection**: Thay thế file giả bằng file gốc <0.1s
5. **Cloud Sync**: Tự động đồng bộ với cloud mỗi 5 phút
6. **Telegram Alert**: Gửi cảnh báo real-time khi có tấn công

---

## 📊 DATABASE LOCATIONS

- **Config**: `%APPDATA%\WindowsUpdate\cloud_config.json`
- **Database**: `%APPDATA%\WindowsUpdate\enterprises.db`  
- **Logs**: `%APPDATA%\WindowsUpdate\cloud_log.dat`
- **Machine ID**: `%APPDATA%\WindowsUpdate\machine.id`

---

## 🔧 TROUBLESHOOTING

### Vấn đề thường gặp:

**1. Telegram Bot không hoạt động:**
- Kiểm tra Bot Token
- Kiểm tra Chat ID
- Kiểm tra kết nối internet

**2. Cloud Sync thất bại:**
- Kiểm tra GitHub Token
- Kiểm tra Repository permissions
- Kiểm tra kết nối internet

**3. File không được bảo vệ:**
- Kiểm tra XML files đã add vào Warehouse chưa
- Kiểm tra MST extraction
- Kiểm tra log file

**4. Nhiều máy không sync:**
- Đảm bảo cùng GitHub repository  
- Kiểm tra Machine ID unique
- Kiểm tra internet connection

---

## ⚠️ LƯU Ý BẢO MẬT

- 🔐 **Luôn dùng Private Repository** cho GitHub
- 🔑 **Bảo vệ Bot Token** và GitHub Token
- 👥 **Chỉ thêm Chat ID tin cậy** vào Telegram Bot
- 💾 **Định kỳ backup** database và config
- 🔄 **Kiểm tra sync status** thường xuyên

---

## 📞 SUPPORT

Nếu cần hỗ trợ, kiểm tra:
1. **Logs** trong Control Panel
2. **Database** integrity
3. **Network connectivity**
4. **Telegram Bot** status

---

**✅ SYSTEM READY - BẢO VỆ HOÀN TOÀN VỚI CLOUD SYNC!**