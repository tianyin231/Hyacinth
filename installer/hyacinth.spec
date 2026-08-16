# -*- mode: python ; coding: utf-8 -*-
"""风信子 PyInstaller 构建配置（onedir，无控制台）。

用法（仓库根目录）：
    uv run pyinstaller --noconfirm --clean installer/hyacinth.spec
或使用一键脚本（自动读版本并编译安装包）：
    powershell -NoProfile -ExecutionPolicy Bypass -File installer/build_installer.ps1

版本号唯一来源是 pyproject.toml 的 [project].version；exe 的版本资源文件
installer/exe-version-info.txt 在每次构建时自动重新生成，无需手工维护。
"""

import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).resolve().parent

_version_match = re.search(
    r'(?m)^version\s*=\s*"([^"]+)"',
    (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
)
if _version_match is None:
    raise SystemExit("pyproject.toml 中未找到 [project].version")
APP_VERSION = _version_match.group(1)
_version_parts = [int(part) for part in APP_VERSION.split(".")]
FILE_VERSION = tuple(_version_parts + [0] * (4 - len(_version_parts)))

_version_info = ROOT / "installer" / "exe-version-info.txt"
_version_info.write_text(
    f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={FILE_VERSION!r},
    prodvers={FILE_VERSION!r},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', 'Hyacinth Project'),
            StringStruct('FileDescription', 'Hyacinth - Excel editing and version management workspace'),
            StringStruct('FileVersion', '{APP_VERSION}'),
            StringStruct('InternalName', 'Hyacinth'),
            StringStruct('OriginalFilename', 'Hyacinth.exe'),
            StringStruct('ProductName', 'Hyacinth'),
            StringStruct('ProductVersion', '{APP_VERSION}')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""",
    encoding="utf-8",
)

a = Analysis(
    [str(ROOT / "src" / "hyacinth" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    # 收集包内非 Python 资产（assets/app-icon.* 等，importlib.resources 读取）。
    datas=collect_data_files("hyacinth"),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "_pytest", "mypy", "ruff"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Hyacinth",
    debug=False,
    bootloader_args=None,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "src" / "hyacinth" / "assets" / "app-icon.ico"),
    version=str(_version_info),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Hyacinth",
)
