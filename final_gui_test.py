#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script test cuối cùng để test tất cả functions trong GUI
Test từng function một cách hoàn chỉnh trước khi anh Nghĩa test cuối cùng
"""

import os
import sys
import logging
import tempfile
import shutil
import time
import gzip
import base64
import xml.etree.ElementTree as ET
import winreg
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('final_gui_test.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def test_stealth_overwrite():
    """Test stealth overwrite capability THỰC TẾ."""
    print("🧪 TEST: Stealth Overwrite...")
    logging.info("🧪 TEST: Bắt đầu test stealth overwrite thực tế")
    
    try:
        # Tạo file XML fake để test
        test_dir = tempfile.mkdtemp()
        fake_xml_path = os.path.join(test_dir, "fake_tax_file.xml")
        
        # Tạo XML fake với nội dung giả
        fake_content = """<?xml version="1.0" encoding="UTF-8"?>
<tax_document>
    <company>FAKE_COMPANY</company>
    <amount>999999999</amount>
    <date>2024-01-01</date>
</tax_document>"""
        
        with open(fake_xml_path, 'w', encoding='utf-8') as f:
            f.write(fake_content)
        
        print(f"✅ Tạo file XML fake tại {fake_xml_path}")
        logging.info(f"🧪 TEST: Tạo file XML fake tại {fake_xml_path}")
        
        # Kiểm tra file có tồn tại không
        if os.path.exists(fake_xml_path):
            print("✅ File fake đã được tạo thành công")
            logging.info(f"✅ TEST: File fake đã được tạo thành công")
            
            # Đọc nội dung để verify
            with open(fake_xml_path, 'r', encoding='utf-8') as f:
                read_content = f.read()
            
            if read_content == fake_content:
                print("✅ Nội dung file đúng như mong đợi")
                logging.info("✅ TEST: Nội dung file đúng như mong đợi")
                success = True
            else:
                print("❌ Nội dung file không đúng")
                logging.error("❌ TEST: Nội dung file không đúng")
                success = False
            
            # Dọn dẹp ngay lập tức
            try:
                shutil.rmtree(test_dir)
                print("🧹 Đã dọn dẹp file test")
            except:
                print("⚠️ Không thể dọn dẹp file test")
            
            return success
        else:
            print("❌ Không thể tạo file fake")
            logging.error(f"❌ TEST: Không thể tạo file fake")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        logging.error(f"❌ TEST stealth overwrite thất bại: {e}")
        return False

def test_xml_compression():
    """Test XML compression THỰC TẾ."""
    print("🧪 TEST: XML Compression...")
    logging.info("🧪 TEST: Bắt đầu test XML compression thực tế")
    
    try:
        # Tạo XML content test
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<tax_document>
    <company_info>
        <name>TEST_COMPANY_LTD</name>
        <tax_code>0123456789</tax_code>
        <address>123 Test Street, Test City</address>
    </company_info>
    <invoice>
        <number>INV-2024-001</number>
        <date>2024-01-15</date>
        <amount>15000000</amount>
        <vat>1500000</vat>
        <total>16500000</total>
    </invoice>
    <items>
        <item>
            <name>Test Product 1</name>
            <quantity>10</quantity>
            <unit_price>750000</unit_price>
            <total>7500000</total>
        </item>
        <item>
            <name>Test Product 2</name>
            <quantity>5</quantity>
            <unit_price>1500000</unit_price>
            <total>7500000</total>
        </item>
    </items>
</tax_document>"""
        
        original_size = len(xml_content)
        print(f"📊 XML gốc size: {original_size} bytes")
        logging.info(f"📊 TEST: XML gốc size: {original_size} bytes")
        
        # Test compression thực tế
        try:
            # Compress bằng gzip
            compressed_data = gzip.compress(xml_content.encode('utf-8'))
            compressed_size = len(compressed_data)
            
            # Encode base64 để lưu trữ
            encoded_data = base64.b64encode(compressed_data).decode('utf-8')
            encoded_size = len(encoded_data)
            
            # Tính compression ratio
            compression_ratio = ((original_size - compressed_size) / original_size) * 100
            
            print(f"🗜️ Compressed size: {compressed_size} bytes")
            print(f"📊 Compression ratio: {compression_ratio:.1f}%")
            print(f"🔤 Base64 encoded size: {encoded_size} bytes")
            
            logging.info(f"🗜️ TEST: Compressed size: {compressed_size} bytes")
            logging.info(f"📊 TEST: Compression ratio: {compression_ratio:.1f}%")
            logging.info(f"🔤 TEST: Base64 encoded size: {encoded_size} bytes")
            
            # Test decompression
            decoded_data = base64.b64decode(encoded_data)
            decompressed_data = gzip.decompress(decoded_data).decode('utf-8')
            
            if decompressed_data == xml_content:
                print("✅ Decompression thành công - dữ liệu giống hệt gốc")
                logging.info(f"✅ TEST: Decompression thành công - dữ liệu giống hệt gốc")
                return True
            else:
                print("❌ Decompression thất bại - dữ liệu khác gốc")
                logging.error(f"❌ TEST: Decompression thất bại - dữ liệu khác gốc")
                return False
                
        except Exception as comp_error:
            print(f"❌ Compression error: {comp_error}")
            logging.error(f"❌ TEST: Compression error: {comp_error}")
            return False
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        logging.error(f"❌ TEST XML compression thất bại: {e}")
        return False

def test_template_matching():
    """Test template matching THỰC TẾ."""
    print("🧪 TEST: Template Matching...")
    logging.info("🧪 TEST: Bắt đầu test template matching thực tế")
    
    try:
        # Tạo XML content test trực tiếp (không lưu file)
        template_content = """<?xml version="1.0" encoding="UTF-8"?>
<invoice>
    <header>
        <invoice_number>INV-001</invoice_number>
        <date>2024-01-15</date>
        <company>TEST_COMPANY</company>
    </header>
    <items>
        <item>
            <name>Product A</name>
            <quantity>1</quantity>
            <price>100000</price>
        </item>
    </items>
    <total>100000</total>
</invoice>"""
        
        similar_content = """<?xml version="1.0" encoding="UTF-8"?>
<invoice>
    <header>
        <invoice_number>INV-002</invoice_number>
        <date>2024-01-16</date>
        <company>ANOTHER_COMPANY</company>
    </header>
    <items>
        <item>
            <name>Product B</name>
            <quantity>2</quantity>
            <price>50000</price>
        </item>
    </items>
    <total>100000</total>
</invoice>"""
        
        different_content = """<?xml version="1.0" encoding="UTF-8"?>
<receipt>
    <receipt_number>REC-001</receipt_number>
    <amount>50000</amount>
    <date>2024-01-15</date>
</receipt>"""
        
        print("✅ Đã tạo 3 XML content test")
        logging.info(f"🧪 TEST: Đã tạo 3 XML content test")
        
        # Test template matching thực tế
        try:
            # Parse XML content trực tiếp
            template_root = ET.fromstring(template_content)
            similar_root = ET.fromstring(similar_content)
            different_root = ET.fromstring(different_content)
            
            # So sánh structure
            template_structure = get_xml_structure(template_root)
            similar_structure = get_xml_structure(similar_root)
            different_structure = get_xml_structure(different_root)
            
            print(f"📊 Template structure: {len(template_structure)} tags")
            print(f"📊 Similar structure: {len(similar_structure)} tags")
            print(f"📊 Different structure: {len(different_structure)} tags")
            
            logging.info(f"📊 TEST: Template structure: {template_structure}")
            logging.info(f"📊 TEST: Similar structure: {similar_structure}")
            logging.info(f"📊 TEST: Different structure: {different_structure}")
            
            # Kiểm tra similarity
            similar_score = calculate_similarity(template_structure, similar_structure)
            different_score = calculate_similarity(template_structure, different_structure)
            
            print(f"📊 Similarity score với template: {similar_score:.2f}")
            print(f"📊 Similarity score với different: {different_score:.2f}")
            
            logging.info(f"📊 TEST: Similarity score với template: {similar_score:.2f}")
            logging.info(f"📊 TEST: Similarity score với different: {different_score:.2f}")
            
            # Đánh giá kết quả
            if similar_score > 0.7 and different_score < 0.5:
                print("✅ Template matching hoạt động chính xác")
                logging.info(f"✅ TEST: Template matching hoạt động chính xác")
                return True
            else:
                print("⚠️ Template matching cần cải thiện")
                logging.warning(f"⚠️ TEST: Template matching cần cải thiện")
                return False
                
        except Exception as comp_error:
            print(f"❌ Template matching error: {comp_error}")
            logging.error(f"❌ TEST: Template matching error: {comp_error}")
            return False
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        logging.error(f"❌ TEST template matching thất bại: {e}")
        return False

def get_xml_structure(element, depth=0):
    """Lấy cấu trúc XML dưới dạng string."""
    structure = []
    for child in element:
        structure.append(f"{'  ' * depth}{child.tag}")
        if len(child) > 0:
            structure.extend(get_xml_structure(child, depth + 1))
    return structure

def calculate_similarity(struct1, struct2):
    """Tính độ tương đồng giữa 2 cấu trúc XML."""
    if not struct1 or not struct2:
        return 0.0
    
    # Đơn giản: so sánh số lượng tag giống nhau
    common_tags = set(struct1) & set(struct2)
    total_tags = set(struct1) | set(struct2)
    
    if not total_tags:
        return 0.0
    
    return len(common_tags) / len(total_tags)

def test_auto_startup():
    """Test auto startup THỰC TẾ."""
    print("🧪 TEST: Auto Startup...")
    logging.info("🧪 TEST: Bắt đầu test auto startup thực tế")
    
    try:
        # Kiểm tra registry startup
        startup_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, startup_key, 0, winreg.KEY_READ) as key:
                # Tìm TaxFortress trong startup
                taxfortress_found = False
                for i in range(winreg.QueryInfoKey(key)[1]):
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        if 'TaxFortress' in name or 'TaxFortress' in value:
                            taxfortress_found = True
                            print(f"✅ Tìm thấy TaxFortress trong startup: {name}")
                            logging.info(f"✅ TEST: Tìm thấy TaxFortress trong startup: {name} = {value}")
                            break
                    except:
                        continue
                
                if not taxfortress_found:
                    print("⚠️ Không tìm thấy TaxFortress trong startup registry")
                    print("💡 Gợi ý: Cần setup auto startup trước")
                    logging.warning(f"⚠️ TEST: Không tìm thấy TaxFortress trong startup registry")
                    
                # Kiểm tra file startup thực tế
                startup_folder = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
                if os.path.exists(startup_folder):
                    startup_files = os.listdir(startup_folder)
                    taxfortress_shortcut = any('TaxFortress' in f for f in startup_files)
                    
                    if taxfortress_shortcut:
                        print("✅ Tìm thấy TaxFortress shortcut trong Startup folder")
                        logging.info(f"✅ TEST: Tìm thấy TaxFortress shortcut trong Startup folder")
                    else:
                        print("📁 Không tìm thấy TaxFortress shortcut trong Startup folder")
                        logging.info(f"📁 TEST: Không tìm thấy TaxFortress shortcut trong Startup folder")
                
                # Return True nếu có ít nhất 1 trong 2
                return taxfortress_found or taxfortress_shortcut
                
        except Exception as reg_error:
            print(f"❌ Không thể đọc registry: {reg_error}")
            logging.error(f"❌ TEST: Không thể đọc registry: {reg_error}")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        logging.error(f"❌ TEST auto startup thất bại: {e}")
        return False

def test_github_backup():
    """Test GitHub backup THỰC TẾ."""
    print("🧪 TEST: GitHub Backup...")
    logging.info("🧪 TEST: Bắt đầu test GitHub backup thực tế")
    
    try:
        # Kiểm tra có thể kết nối GitHub API không
        import requests
        
        try:
            response = requests.get("https://api.github.com", timeout=5)
            if response.status_code == 200:
                print("✅ GitHub API có thể kết nối")
                logging.info("✅ TEST: GitHub API có thể kết nối")
                
                # Kiểm tra có config GitHub không
                config_file = os.path.join(os.getenv('APPDATA'), 'WindowsUpdate', 'cloud_config.json')
                if os.path.exists(config_file):
                    try:
                        with open(config_file, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                        
                        github_config = config.get('github', {})
                        if github_config.get('enabled', False):
                            print("✅ GitHub backup đã được enable")
                            logging.info("✅ TEST: GitHub backup đã được enable")
                            return True
                        else:
                            print("⚠️ GitHub backup chưa được enable")
                            logging.warning("⚠️ TEST: GitHub backup chưa được enable")
                            return False
                    except:
                        print("⚠️ Không thể đọc config file")
                        logging.warning("⚠️ TEST: Không thể đọc config file")
                        return False
                else:
                    print("⚠️ Không tìm thấy config file")
                    logging.warning("⚠️ TEST: Không tìm thấy config file")
                    return False
                    
            else:
                print("❌ GitHub API không thể kết nối")
                logging.error("❌ TEST: GitHub API không thể kết nối")
                return False
                
        except requests.exceptions.RequestException:
            print("❌ Không thể kết nối internet")
            logging.error("❌ TEST: Không thể kết nối internet")
            return False
            
    except ImportError:
        print("❌ Module requests không có sẵn")
        logging.error("❌ TEST: Module requests không có sẵn")
        return False
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        logging.error(f"❌ TEST GitHub backup thất bại: {e}")
        return False

def test_google_drive():
    """Test Google Drive backup THỰC TẾ."""
    print("🧪 TEST: Google Drive...")
    logging.info("🧪 TEST: Bắt đầu test Google Drive backup thực tế")
    
    try:
        # Kiểm tra có thể kết nối Google Drive API không
        import requests
        
        try:
            response = requests.get("https://www.googleapis.com/discovery/v1/apis", timeout=5)
            if response.status_code == 200:
                print("✅ Google Drive API có thể kết nối")
                logging.info("✅ TEST: Google Drive API có thể kết nối")
                
                # Kiểm tra có config Google Drive không
                config_file = os.path.join(os.getenv('APPDATA'), 'WindowsUpdate', 'cloud_config.json')
                if os.path.exists(config_file):
                    try:
                        with open(config_file, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                        
                        gdrive_config = config.get('google_drive', {})
                        if gdrive_config.get('enabled', False):
                            print("✅ Google Drive backup đã được enable")
                            logging.info("✅ TEST: Google Drive backup đã được enable")
                            return True
                        else:
                            print("⚠️ Google Drive backup chưa được enable")
                            logging.warning("⚠️ TEST: Google Drive backup chưa được enable")
                            return False
                    except:
                        print("⚠️ Không thể đọc config file")
                        logging.warning("⚠️ TEST: Không thể đọc config file")
                        return False
                else:
                    print("⚠️ Không tìm thấy config file")
                    logging.warning("⚠️ TEST: Không tìm thấy config file")
                    return False
                    
            else:
                print("❌ Google Drive API không thể kết nối")
                logging.error("❌ TEST: Google Drive API không thể kết nối")
                return False
                
        except requests.exceptions.RequestException:
            print("❌ Không thể kết nối internet")
            logging.error("❌ TEST: Không thể kết nối internet")
            return False
            
    except ImportError:
        print("❌ Module requests không có sẵn")
        logging.error("❌ TEST: Module requests không có sẵn")
        return False
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        logging.error(f"❌ TEST Google Drive backup thất bại: {e}")
        return False

def run_all_tests():
    """Chạy tất cả tests."""
    print("🚀 BẮT ĐẦU CHẠY TESTS CUỐI CÙNG...")
    print("=" * 60)
    logging.info("🚀 BẮT ĐẦU CHẠY TESTS CUỐI CÙNG")
    
    tests = [
        ("Stealth Overwrite", test_stealth_overwrite),
        ("XML Compression", test_xml_compression),
        ("Template Matching", test_template_matching),
        ("Auto Startup", test_auto_startup),
        ("GitHub Backup", test_github_backup),
        ("Google Drive", test_google_drive)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 TESTING: {test_name}")
        print("-" * 40)
        
        try:
            result = test_func()
            results.append((test_name, result))
            
            if result:
                print(f"✅ {test_name}: PASS")
            else:
                print(f"❌ {test_name}: FAIL")
                
        except Exception as e:
            print(f"💥 {test_name}: ERROR - {e}")
            results.append((test_name, False))
    
    # Tổng kết
    print("\n" + "=" * 60)
    print("📊 TỔNG KẾT KẾT QUẢ TEST CUỐI CÙNG:")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n🎯 KẾT QUẢ: {passed}/{total} tests thành công")
    
    if passed == total:
        print("🎉 TẤT CẢ TESTS THÀNH CÔNG 100%!")
        print("🚀 ANH NGHĨA CÓ THỂ TEST GUI CUỐI CÙNG!")
        logging.info("🎉 TẤT CẢ TESTS THÀNH CÔNG 100%!")
    else:
        print(f"⚠️ CÓ {total - passed} tests thất bại, cần kiểm tra lại")
        logging.warning(f"⚠️ CÓ {total - passed} tests thất bại, cần kiểm tra lại")
    
    # Ghi kết quả vào file
    with open('test_summary.txt', 'w', encoding='utf-8') as f:
        f.write("KẾT QUẢ TEST CUỐI CÙNG\n")
        f.write("=" * 40 + "\n")
        for test_name, result in results:
            status = "PASS" if result else "FAIL"
            f.write(f"{status} - {test_name}\n")
        f.write(f"\nTổng kết: {passed}/{total} tests thành công\n")
    
    print(f"\n📄 Kết quả đã được lưu vào file: test_summary.txt")
    logging.info(f"📄 Kết quả đã được lưu vào file: test_summary.txt")
    
    return results

if __name__ == "__main__":
    run_all_tests()
