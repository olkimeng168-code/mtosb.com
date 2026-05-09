# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['local_bridge.py'],
    pathex=[],
    binaries=[],
    datas=[],
    # 🌟 ចំណុចសំខាន់បំផុត៖ បញ្ចូល Library ទាំងអស់ដែលពាក់ព័ន្ធនៅទីនេះ (Hidden Imports)
    hiddenimports=[
        'flask',
        'flask_cors',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'tkinter',
        'win32com.client',
        'pythoncom'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='local_bridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # 🌟 លាក់ផ្ទាំងខ្មៅ (CMD) ពេលចុចបើក (ដើរស្ងាត់ៗពីក្រោយ)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# សម្រាប់ Mac (បង្កើតជា .app)
app = BUNDLE(
    exe,
    name='local_bridge.app',
    icon=None,
    bundle_identifier=None,
)