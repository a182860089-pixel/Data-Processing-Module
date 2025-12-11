@echo off
cd /d "D:\Data Processing Module\data_to_md-main"
echo 启动后端API服务...
python -m uvicorn app.main:app --reload --port 8000 --host 0.0.0.0
pause
