# 开发模式：改任何 .py 文件保存后，页面自动重载，不用重启
#   .\dev.ps1
#   .\dev.ps1 -Port 8000
# 仅用于开发调试；正式使用仍用  .\.venv\Scripts\python app.py
# 注意：.env 只在进程启动时读取一次，改 Key / 代理仍需重启。
param([int]$Port = 7860)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:GRADIO_SERVER_PORT = "$Port"
& .\.venv\Scripts\gradio app.py --watch-dirs .
