# Feishu Agent auto-start script
$Root = "D:\generic-agent"
$SchedulerLog = "$Root\logs\fsapp_scheduler.log"
$FsappLog = "$Root\logs\fsapp.log"
$Python = "C:\Users\wangx\AppData\Local\Programs\Python\Python312\python.exe"

$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $SchedulerLog -Value "$ts [INFO] Task triggered, checking fsapp state..."

$existing = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*python*fsapp.py*" }
if ($existing) {
    Add-Content -Path $SchedulerLog -Value "$ts [INFO] fsapp already running (PID $($existing.ProcessId)), skip"
    exit 0
}

Add-Content -Path $SchedulerLog -Value "$ts [INFO] fsapp not found, starting..."
cd $Root
# 使用cmd /c重定向（stdout+stderr→单文件），-NoExit移除，无控制台输出泄露
$proc = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "cd /d $Root && $Python -u frontends\fsapp.py > `"$FsappLog`" 2>&1" `
    -WindowStyle Hidden `
    -PassThru

Add-Content -Path $SchedulerLog -Value "$ts [INFO] fsapp started PID: $($proc.Id)"
