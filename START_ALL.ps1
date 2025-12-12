# 启动脚本 - 同时启动后端和前端项目

# 尽量避免 Windows PowerShell 5 中文乱码
try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
} catch {}

Write-Host "=====================================" -ForegroundColor Green
Write-Host "  视频转换系统 - 前后端启动脚本" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""

# 后端项目路径
$backendPath = "D:\Data Processing Module\data_to_md-main"
# 前端项目路径
$frontendPath = "D:\Data Processing Module\proc_image\smallimg"

# 固定使用短路径 venv 的 python，避免全局/Store Python 缺依赖
$pythonExe = "D:\venvs\data_to_md\Scripts\python.exe"

# 启动后端
Write-Host "启动后端API服务..." -ForegroundColor Cyan
Write-Host "位置: $backendPath" -ForegroundColor Yellow
Start-Process -FilePath $pythonExe -WorkingDirectory $backendPath -ArgumentList @(
    "-m", "uvicorn", "app.main:app",
    "--reload", "--port", "8000", "--host", "0.0.0.0"
) -WindowStyle Normal

# 等待3秒后启动前端
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "启动前端开发服务器..." -ForegroundColor Cyan
Write-Host "位置: $frontendPath" -ForegroundColor Yellow
Start-Process -FilePath "npm" -WorkingDirectory $frontendPath -ArgumentList @("run", "dev") -WindowStyle Normal

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "启动完成！" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "后端地址: http://localhost:8000" -ForegroundColor Cyan
Write-Host "前端地址: http://localhost:5173" -ForegroundColor Cyan
Write-Host "API文档: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "功能说明:" -ForegroundColor Cyan
Write-Host "  • 支持视频转Markdown/PDF" -ForegroundColor White
Write-Host "  • 支持500MB以内的视频文件" -ForegroundColor White
Write-Host "  • 实时转换选项配置" -ForegroundColor White
Write-Host "  • 支持拖放上传" -ForegroundColor White
Write-Host "  • 新增：微信公众号文章爬虫" -ForegroundColor White
Write-Host ""
Write-Host "按 Ctrl+C 可关闭任何窗口" -ForegroundColor Yellow
