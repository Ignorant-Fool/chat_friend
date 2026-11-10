# 启动聊天伙伴后端（使用项目内虚拟环境）
# 用法：右击运行，或在 PowerShell 中执行  .\run.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvpy = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $venvpy)) {
    Write-Host "未找到虚拟环境 .venv，请先安装依赖：python -m venv .venv && pip install -r requirements.txt" -ForegroundColor Red
    exit 1
}

# 确保 .env 存在
if (-not (Test-Path (Join-Path $root ".env"))) {
    Copy-Item (Join-Path $root ".env.example") (Join-Path $root ".env")
    Write-Host "已从 .env.example 生成 .env，请填入你的 API Key" -ForegroundColor Yellow
}

$env:PYTHONIOENCODING = "utf-8"
Set-Location $root
& $venvpy -m uvicorn app.main:app --host 127.0.0.1 --port 8000
