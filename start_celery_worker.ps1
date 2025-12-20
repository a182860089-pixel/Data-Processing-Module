# 启动 Celery Worker（Windows 兼容：使用 threads 池 + venv Python）
try {
  [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
} catch {}

$backendPath = "D:\Data Processing Module\data_to_md-main"
$pythonExe  = "D:\venvs\data_to_md\Scripts\python.exe"

Write-Host "启动 Celery Worker..." -ForegroundColor Cyan
Write-Host "工作目录: $backendPath" -ForegroundColor Yellow
Write-Host "Python: $pythonExe" -ForegroundColor Yellow

# 使用线程池，避免 Windows 下 prefork/spawn 的兼容性问题
Start-Process -FilePath $pythonExe -WorkingDirectory $backendPath -ArgumentList @(
  "-m", "celery", "-A", "celery_worker.celery_app", "worker",
  "-P", "threads", "-c", "4", "-l", "info"
) -WindowStyle Normal

Write-Host "已启动 Celery Worker（threads 池，4 并发）" -ForegroundColor Green
