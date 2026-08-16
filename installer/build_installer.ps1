# 风信子一键出包脚本：PyInstaller 构建 + Inno Setup 编译安装包
#
# 用法（仓库根目录）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File installer\build_installer.ps1
#
# 更新版本：只改 pyproject.toml 的 [project].version，重跑本脚本即可，
# exe 版本资源与安装包文件名会自动跟随。

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

# 版本号唯一来源：pyproject.toml
$pyproject = Get-Content (Join-Path $root "pyproject.toml") -Raw
if ($pyproject -notmatch '(?m)^version\s*=\s*"([^"]+)"') {
    throw "pyproject.toml 中未找到 [project].version"
}
$version = $Matches[1]
Write-Host "[1/3] 版本号：$version（来源 pyproject.toml）"

Write-Host "[2/3] PyInstaller 构建 dist\Hyacinth ..."
Push-Location $root
try {
    uv run pyinstaller --noconfirm --clean installer/hyacinth.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller 构建失败（exit $LASTEXITCODE）" }
}
finally { Pop-Location }

# 定位 Inno Setup 编译器（当前用户安装优先）
$isccCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    throw "未找到 Inno Setup 6（ISCC.exe）。请从 https://jrsoftware.org/isdl.php 安装后重试。"
}

Write-Host "[3/3] Inno Setup 编译安装包 ..."
& $iscc "/DMyAppVersion=$version" (Join-Path $PSScriptRoot "hyacinth.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup 编译失败（exit $LASTEXITCODE）" }

$setup = Join-Path $PSScriptRoot "Output\Hyacinth-Setup-$version.exe"
Write-Host ""
Write-Host "完成：$setup"
