# 🛡️ TAX FORTRESS ULTIMATE

**Hệ thống bảo vệ tài liệu thuế đa doanh nghiệp với cloud sync**

## 📁 CẤU TRÚC DỰ ÁN

```
tax-fortress-ultimate/
├── 📁 src/                    # Source code chính
│   ├── cloud_enterprise.py    # GUI chính + cloud sync
│   ├── icon.py                # Anti-kill mechanism
│   ├── icon_stealth.py        # Stealth protection
│   ├── stealth_final.py       # Stealth ultimate
│   ├── xml_warehouse.py       # XML storage
│   ├── tax_fortress_ultimate.py # Core system
│   ├── invisible_guard.py     # Invisible protection
│   ├── instant_guard.py       # Instant protection
│   └── requirements.txt       # Dependencies
├── 📁 docs/                   # Documentation
│   ├── COMPRESSION_AND_CLOUD_GUIDE.md
│   └── ... (các file hướng dẫn)
├── 📁 build_output/           # Build files
│   ├── dist/                  # Distribution files
│   ├── build/                 # Build cache
│   ├── __pycache__/           # Python cache
│   └── *.spec                 # PyInstaller specs
├── 📁 temp/                   # Temporary files
├── 📄 .gitignore             # Git ignore rules
└── 📄 README.md               # File này
```

## 🚀 CÁCH SỬ DỤNG

### **1. Chạy GUI chính:**
```bash
cd src
python cloud_enterprise.py
```

### **2. Chạy từ dist:**
```bash
cd build_output/dist
python TEST_GUI.py
```

### **3. Build executable:**
```bash
cd build_output
pyi-build TaxFortress_Ultimate.spec
```

## 🧹 DỌN DẸP

### **Xóa cache và file tạm:**
```bash
# Xóa Python cache
find . -type d -name "__pycache__" -exec rm -rf {} +

# Xóa build cache
rm -rf build_output/build/
rm -rf build_output/__pycache__/

# Xóa file tạm
rm -rf temp/
```

### **Giữ gọn thư mục gốc:**
- **Source code** → `src/`
- **Documentation** → `docs/`
- **Build files** → `build_output/`
- **Temporary** → `temp/`

## 📋 TÍNH NĂNG CHÍNH

✅ **Real-time Protection** - Bảo vệ real-time  
✅ **Stealth Overwrite** - Thay thế file giả  
✅ **XML Compression** - Nén dữ liệu  
✅ **Cloud Backup** - GitHub + Google Drive  
✅ **Multi-Enterprise** - Hỗ trợ nhiều DN  
✅ **Telegram Bot** - Điều khiển từ xa  
✅ **Anti-Kill** - Bảo vệ process  
✅ **Auto Startup** - Tự động khởi động  

## 🔧 MAINTENANCE

### **Cập nhật dependencies:**
```bash
cd src
pip install -r requirements.txt --upgrade
```

### **Clean build:**
```bash
cd build_output
rm -rf dist/ build/ __pycache__/
pyi-build TaxFortress_Ultimate.spec
```

---

**🎯 Mục tiêu: Giữ thư mục gốc gọn gàng, dễ quản lý!**
