@echo off
echo ========================================
echo    TAX FORTRESS ULTIMATE - MASTER SETUP
echo ========================================
echo.

echo [1/5] Kiem tra Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python chua duoc cai dat!
    echo Hay cai dat Python 3.7+ truoc
    pause
    exit /b 1
)
echo ✓ Python da san sang

echo.
echo [2/5] Kiem tra thu muc src...
if not exist "src\cloud_enterprise.py" (
    echo ERROR: Khong tim thay file cloud_enterprise.py!
    echo Hay chay script nay trong thu muc goc cua du an
    pause
    exit /b 1
)
echo ✓ File cloud_enterprise.py da san sang

echo.
echo [3/5] Cai dat cac thu vien can thiet...
pip install requests google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client dropbox

echo.
echo [4/5] Tao thu muc config...
if not exist "config" mkdir config
if not exist "logs" mkdir logs

echo.
echo [5/5] Khoi tao he thong...
cd src
python -c "import cloud_enterprise; print('✓ He thong da san sang!')"

echo.
echo ========================================
echo    SETUP MASTER HOAN THANH!
echo ========================================
echo.
echo Buoc tiep theo:
echo 1. Chay cloud_enterprise.py
echo 2. Nhap GitHub token trong config
echo 3. Nhap Telegram Bot token
echo 4. Them doanh nghiep dau tien
echo.
pause
