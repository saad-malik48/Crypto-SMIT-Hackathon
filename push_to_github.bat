@echo off
echo ╔══════════════════════════════════════════════════════════╗
echo ║   Pushing CRYPTEX to GitHub                              ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

REM Check if git is available
git --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Git is not found in PATH. Please:
    echo    1. Close this terminal
    echo    2. Open a NEW terminal window
    echo    3. Run this script again
    echo.
    echo Or manually run these commands in a new terminal:
    echo.
    echo git init
    echo git add .
    echo git commit -m "Initial commit: CRYPTEX Real-Time Crypto Analytics Platform"
    echo git remote add origin https://github.com/saad-malik48/Crypto-SMIT-Hackathon.git
    echo git branch -M main
    echo git push -u origin main
    echo.
    pause
    exit /b 1
)

echo ✅ Git is installed
echo.

REM Configure Git (you can change these)
echo 📝 Configuring Git...
git config --global user.name "saad-malik48"
echo Enter your GitHub email:
set /p email="Email: "
git config --global user.email "%email%"
echo.

REM Initialize Git repository
echo 🔧 Initializing Git repository...
git init
if errorlevel 1 (
    echo ⚠️  Repository might already be initialized
)
echo.

REM Add all files
echo 📦 Adding all files...
git add .
echo.

REM Create initial commit
echo 💾 Creating initial commit...
git commit -m "Initial commit: CRYPTEX Real-Time Crypto Analytics Platform"
if errorlevel 1 (
    echo ⚠️  Commit might already exist or no changes to commit
)
echo.

REM Add remote origin
echo 🔗 Connecting to GitHub repository...
git remote add origin https://github.com/saad-malik48/Crypto-SMIT-Hackathon.git 2>nul
if errorlevel 1 (
    echo ⚠️  Remote already exists, updating URL...
    git remote set-url origin https://github.com/saad-malik48/Crypto-SMIT-Hackathon.git
)
echo.

REM Rename branch to main
echo 🔄 Setting branch to main...
git branch -M main
echo.

REM Push to GitHub
echo 🚀 Pushing to GitHub...
echo.
echo ⚠️  You will be asked for authentication:
echo    Username: saad-malik48
echo    Password: Use your Personal Access Token (NOT your GitHub password)
echo.
echo    Get token from: https://github.com/settings/tokens
echo.
git push -u origin main

if errorlevel 1 (
    echo.
    echo ❌ Push failed. Common issues:
    echo    1. Authentication failed - Use Personal Access Token
    echo    2. Repository doesn't exist - Create it on GitHub first
    echo    3. Network issues - Check your internet connection
    echo.
    echo 📚 See PUSH_TO_GITHUB.txt for detailed troubleshooting
    pause
    exit /b 1
)

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║   ✅ SUCCESS! Your project is on GitHub!                ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
echo 🌐 View your repository:
echo    https://github.com/saad-malik48/Crypto-SMIT-Hackathon
echo.
echo 📋 Next Steps:
echo    1. Visit your repository and add a description
echo    2. Add topics: python, streamlit, etl, cryptocurrency
echo    3. Deploy to Streamlit Cloud (see QUICK_START.md)
echo    4. Share on LinkedIn (see GITHUB_SETUP.md)
echo.
pause
