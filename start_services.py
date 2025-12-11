#!/usr/bin/env python3
import subprocess
import time
import os

print("=" * 50)
print("  视频转换系统 - 前后端启动脚本")
print("=" * 50)
print()

# 后端路径和命令
backend_path = r"D:\Data Processing Module\data_to_md-main"
backend_cmd = [
    "python",
    "-m",
    "uvicorn",
    "app.main:app",
    "--reload",
    "--port",
    "8000",
    "--host",
    "0.0.0.0"
]

# 前端路径和命令
frontend_path = r"D:\Data Processing Module\proc_image\smallimg"
frontend_cmd = ["npm", "run", "dev"]

print("启动后端 API 服务...")
print(f"位置: {backend_path}")
try:
    backend_process = subprocess.Popen(
        backend_cmd,
        cwd=backend_path,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    print("✓ 后端已启动")
except Exception as e:
    print(f"✗ 后端启动失败: {e}")

# 等待 3 秒
time.sleep(3)

print()
print("启动前端开发服务器...")
print(f"位置: {frontend_path}")
try:
    frontend_process = subprocess.Popen(
        frontend_cmd,
        cwd=frontend_path,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    print("✓ 前端已启动")
except Exception as e:
    print(f"✗ 前端启动失败: {e}")

print()
print("=" * 50)
print("启动完成！")
print("=" * 50)
print()
print("📌 后端地址: http://localhost:8000")
print("📌 前端地址: http://localhost:5173")
print("📌 API文档: http://localhost:8000/docs")
print()
print("按 Ctrl+C 可关闭此脚本（其他窗口继续运行）")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n脚本已关闭")
