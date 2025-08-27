# 🛡️ TAX FORTRESS - XML Protection System

## 📋 Mô tả dự án

Hệ thống bảo vệ file XML thuế (ETAX) tự động, ghi đè file bị thay đổi bằng template gốc để duy trì tính toàn vẹn dữ liệu thuế.

## 🚀 Tính năng chính

### 🔒 **Bảo vệ tự động**
- Giám sát tất cả ổ đĩa Windows
- Phát hiện file XML mới/tạo/sửa
- Ghi đè tức thì bằng template gốc
- Response time <0.1 giây

### ☁️ **Cloud Enterprise**
- Hỗ trợ đa doanh nghiệp
- Đồng bộ cloud (GitHub, Google Drive, Dropbox)
- Telegram Bot điều khiển từ xa
- Machine ID tracking

### 🕵️ **Stealth Mode**
- Hoàn toàn vô hình
- Process ngụy trang
- Auto-startup Windows
- Fortress cache bảo mật

### 📊 **XML Warehouse**
- Database SQLite chuyên nghiệp
- Trích xuất MST (Mã số thuế)
- So sánh cấu trúc XML (70% similarity)
- Control Panel quản lý

## 🏗️ Cấu trúc dự án

```
tax-fortress/
├── cloud_enterprise.py      # Multi-enterprise + Cloud + Telegram
├── xml_warehouse.py         # XML Warehouse + Database
├── invisible_guard.py       # Invisible + Fortress Cache
├── stealth_final.py         # Stealth + Control Panel
├── instant_guard.py         # Lightning Speed <0.1s
├── control_panel.py         # Control Panel Launcher
├── warehouse_panel.py       # Warehouse Control Panel
├── templates/               # XML Templates
│   ├── Cty Bình Nguyễn Derco/
│   └── Cty Tiến Bình Yến/
└── *.spec                   # PyInstaller Build Files
```

## 🎯 Các phiên bản

### 1. **CLOUD ENTERPRISE** (Khuyến nghị)
- **File**: `cloud_enterprise.py`
- **Tính năng**: Multi-enterprise + Cloud + Telegram Bot
- **Phù hợp**: Doanh nghiệp lớn, cần quản lý tập trung

### 2. **INSTANT GUARD**
- **File**: `instant_guard.py`
- **Tính năng**: Tốc độ tối đa <0.1 giây
- **Phù hợp**: Cần tốc độ phản ứng nhanh

### 3. **INVISIBLE GUARD**
- **File**: `invisible_guard.py`
- **Tính năng**: Hoàn toàn vô hình + Fortress
- **Phù hợp**: Cần bảo mật tối đa

### 4. **XML WAREHOUSE**
- **File**: `xml_warehouse.py`
- **Tính năng**: Kho lưu trữ XML chuyên nghiệp
- **Phù hợp**: Quản lý template XML

## 🚀 Cài đặt và sử dụng

### Yêu cầu hệ thống
- Windows 10/11
- Python 3.7+
- PyInstaller (để build EXE)

### Cài đặt
```bash
# Clone repository
git clone https://github.com/your-username/tax-fortress.git
cd tax-fortress

# Cài đặt dependencies
pip install -r requirements.txt

# Build EXE (tùy chọn)
pyinstaller --onefile --windowed cloud_enterprise.py
```

### Sử dụng
```bash
# Chạy Cloud Enterprise (khuyến nghị)
python cloud_enterprise.py

# Chạy với Control Panel
python cloud_enterprise.py --control

# Chạy Instant Guard
python instant_guard.py

# Chạy Invisible Guard
python invisible_guard.py --control
```

## 🔧 Cấu hình

### Cloud Enterprise
```python
# Cấu hình trong cloud_config.json
{
    "cloud_provider": "github",
    "sync_enabled": true,
    "telegram": {
        "enabled": true,
        "bot_token": "YOUR_BOT_TOKEN",
        "authorized_users": ["CHAT_ID"]
    }
}
```

### Telegram Bot
- Tạo bot qua @BotFather
- Thêm bot token vào config
- Thêm chat ID được phép điều khiển

## 📱 Control Panel

### Truy cập
- Chạy với flag `--control`
- Nhập access code được tạo tự động
- Quản lý hệ thống qua GUI

### Tính năng Control Panel
- Bật/tắt bảo vệ
- Xem logs hoạt động
- Quản lý warehouse
- Thống kê hệ thống
- Tạo access code mới

## 🛡️ Bảo mật

### Tính năng bảo mật
- Ẩn hoàn toàn khỏi Task Manager
- Process ngụy trang
- Database mã hóa
- Access key bảo vệ
- Auto-startup ẩn

### Lưu trữ
- Dữ liệu lưu trong `%APPDATA%`
- Database SQLite bảo mật
- Cache RAM tối ưu

## 📊 Hiệu suất

### Tốc độ
- **Response time**: <0.1 giây
- **Memory usage**: Tối ưu
- **CPU usage**: Thấp
- **Disk I/O**: Tối thiểu

### Monitoring
- Giám sát tất cả ổ đĩa
- Phát hiện file XML real-time
- Logging chi tiết
- Alert qua email/Telegram

## 🔄 Cập nhật

### Auto-update
- Kiểm tra cập nhật tự động
- Cloud sync định kỳ
- Backup dữ liệu

### Version control
- Git repository
- Release tags
- Changelog

## 📞 Hỗ trợ

### Liên hệ
- **Email**: support@taxfortress.com
- **Telegram**: @TaxFortressBot
- **GitHub**: Issues & Discussions

### Tài liệu
- [User Guide](docs/user-guide.md)
- [API Reference](docs/api.md)
- [Troubleshooting](docs/troubleshooting.md)

## 📄 License

MIT License - Xem file [LICENSE](LICENSE) để biết thêm chi tiết.

## 🙏 Đóng góp

Mọi đóng góp đều được chào đón! Vui lòng:
1. Fork repository
2. Tạo feature branch
3. Commit changes
4. Push to branch
5. Tạo Pull Request

---

**TAX FORTRESS** - Bảo vệ dữ liệu thuế, bảo mật tối đa! 🛡️✨
