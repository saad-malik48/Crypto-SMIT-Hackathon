@echo off
REM CRYPTEX GitHub Setup Script for Windows
REM This script helps you quickly set up and push your project to GitHub

echo ╔══════════════════════════════════════════════════════════╗
echo ║   CRYPTEX - GitHub Setup Script                         ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

REM Check if git is installed
git --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Git is not installed. Please install Git first.
    echo    Download from: https://git-scm.com/download/win
    pause
    exit /b 1
)

echo ✅ Git is installed
echo.

REM Get user input
set /p github_username="Enter your GitHub username: "
set /p repo_name="Enter repository name (default: crypto-analytics): "
if "%repo_name%"=="" set repo_name=crypto-analytics

echo.
echo 📝 Configuration:
echo    GitHub Username: %github_username%
echo    Repository Name: %repo_name%
echo.

REM Initialize git if not already initialized
if not exist .git (
    echo 🔧 Initializing Git repository...
    git init
    echo ✅ Git initialized
) else (
    echo ✅ Git already initialized
)

REM Add all files
echo 📦 Adding files to Git...
git add .

REM Create initial commit
echo 💾 Creating initial commit...
git commit -m "Initial commit: CRYPTEX Real-Time Crypto Analytics Platform"

REM Rename branch to main
echo 🔄 Renaming branch to main...
git branch -M main

REM Add remote origin
echo 🔗 Adding remote origin...
git remote add origin https://github.com/%github_username%/%repo_name%.git 2>nul
if errorlevel 1 (
    git remote set-url origin https://github.com/%github_username%/%repo_name%.git
)

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║   Next Steps:                                            ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
echo 1. Create a new repository on GitHub:
echo    👉 https://github.com/new
echo    - Name: %repo_name%
echo    - Description: Real-time cryptocurrency analytics platform
echo    - Public repository
echo    - Don't initialize with README
echo.
echo 2. Push your code:
echo    git push -u origin main
echo.
echo 3. Deploy to Streamlit Cloud:
echo    👉 https://share.streamlit.io/
echo    - Sign in with GitHub
echo    - New app → Select your repo → dashboard.py
echo.
echo 4. Share on LinkedIn using the template in GITHUB_SETUP.md
echo.
echo 📚 For detailed instructions, see:
echo    - QUICK_START.md
echo    - GITHUB_SETUP.md
echo    - SHARING_CHECKLIST.md
echo.
echo 🚀 Good luck with your project!
echo.
pause
