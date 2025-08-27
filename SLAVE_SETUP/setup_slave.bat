@echo off
echo ========================================
echo    TAX FORTRESS ULTIMATE - SLAVE SETUP
echo ========================================
echo.

echo [1/4] Kiem tra Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python chua duoc cai dat!
    echo Hay cai dat Python 3.7+ truoc
    pause
    exit /b 1
)
echo ✓ Python da san sang

echo.
echo [2/4] Kiem tra file cloud_enterprise.py...
if not exist "cloud_enterprise.py" (
    echo ERROR: Khong tim thay file cloud_enterprise.py!
    echo Hay copy file nay tu may chu
    pause
    exit /b 1
)
echo ✓ File cloud_enterprise.py da san sang

echo.
echo [3/4] Cai dat cac thu vien can thiet...
pip install requests google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client dropbox

echo.
echo [4/4] Khoi tao may con...
python -c "import cloud_enterprise; print('✓ May con da san sang!')"

echo.
echo ========================================
echo    SETUP SLAVE HOAN THANH!
echo ========================================
echo.
echo Buoc tiep theo:
echo 1. Chay cloud_enterprise.py
echo 2. May se tu dong tao Machine ID
echo 3. Dang ky voi may chu qua Telegram
echo 4. Nhan du lieu tu GitHub
echo.
pause
