@echo off
cd /d "C:\Path\To\Your\Project"
echo Avvio script: %date% %time% >> "C:\Path\To\Your\run_log.txt"
"C:\Path\To\Python\python.exe" main_user_sync.py >> "C:\Path\To\Your\run_log.txt" 2>&1
