# 一键打包（PyInstaller onedir）
# 用法：powershell -ExecutionPolicy Bypass -File build.ps1
# 产物：dist\DesktopPet\DesktopPet.exe（约 1.2GB，含 torch/funasr）

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "[1/3] 检查依赖…" -ForegroundColor Cyan
python -c "import PyInstaller, torch, funasr" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "缺依赖，请先： pip install -r requirements.txt pyinstaller" -ForegroundColor Yellow
    exit 1
}

Write-Host "[2/3] 打包（约 5-8 分钟）…" -ForegroundColor Cyan
python -m PyInstaller --noconfirm --distpath "$PSScriptRoot\dist" --workpath "$PSScriptRoot\build" DesktopPet.spec
if ($LASTEXITCODE -ne 0) { Write-Host "打包失败" -ForegroundColor Red; exit 1 }

Write-Host "[3/3] 完成：$PSScriptRoot\dist\DesktopPet\DesktopPet.exe" -ForegroundColor Green
Write-Host "首次运行会自动下载 funasr 模型到 D:\pet-funasr-models（约 1GB）" -ForegroundColor DarkGray
