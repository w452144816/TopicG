# 一键部署（Windows PowerShell）
#   .\setup.ps1          # 按 requirements.txt 安装
#   .\setup.ps1 -Lock    # 按 requirements.lock.txt 完整锁定版本安装
param([switch]$Lock)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) { $python = "py"; $pyArgs = @("-3") } else { $python = "python"; $pyArgs = @() }

if (-not (Test-Path ".venv")) {
    Write-Host "创建虚拟环境 .venv ..."
    & $python @pyArgs -m venv .venv
}

$req = if ($Lock) { "requirements.lock.txt" } else { "requirements.txt" }
Write-Host "安装依赖（$req）..."
& .\.venv\Scripts\python -m pip install --upgrade pip
& .\.venv\Scripts\python -m pip install -r $req

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "已生成 .env，请填入 API Key 和代理设置" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "完成。启动：  .\.venv\Scripts\python app.py" -ForegroundColor Green
Write-Host "连通测试：    .\.venv\Scripts\python scripts\smoke_test.py"
