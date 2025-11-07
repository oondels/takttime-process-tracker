# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import copy_metadata

block_cipher = None

# Coleta metadados dos pacotes que precisam (com tratamento de erro)
datas_metadata = []
packages_with_metadata = [
    'aio_pika',
    'aiormq', 
    'pamqp',
    'ultralytics',
    'python-dotenv',
]

for pkg in packages_with_metadata:
    try:
        datas_metadata += copy_metadata(pkg)
    except Exception as e:
        print(f"Warning: Could not copy metadata for {pkg}: {e}")

# Analisa as dependências do aplicativo
a = Analysis(
    ['../app.py'],
    pathex=['..'],
    binaries=[],
    datas=[
        ('../assets/train_2025.pt', '.'),  # Inclui o modelo YOLO
        ('../config', 'config'),     # Inclui o diretório de configuração
    ] + datas_metadata,  # Adiciona os metadados coletados
    hiddenimports=[
        'paho.mqtt.client',
        'ultralytics',
        'cv2',
        'PIL',
        'pytesseract',
        'numpy',
        'torch',
        'torchvision',
        'mqtt_manager',
        'main',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'aio_pika',
        'aio_pika.abc',
        'aio_pika.channel',
        'aio_pika.connection',
        'aio_pika.exchange',
        'aio_pika.message',
        'aio_pika.queue',
        'aio_pika.robust_channel',
        'aio_pika.robust_connection',
        'aio_pika.robust_exchange',
        'aio_pika.robust_queue',
        'aiormq',
        'aiormq.abc',
        'aiormq.auth',
        'aiormq.base',
        'aiormq.channel',
        'aiormq.connection',
        'aiormq.exceptions',
        'pamqp',
        'pamqp.base',
        'pamqp.body',
        'pamqp.commands',
        'pamqp.constants',
        'pamqp.decode',
        'pamqp.encode',
        'pamqp.exceptions',
        'pamqp.frame',
        'pamqp.header',
        'pamqp.heartbeat',
        'asyncio',
        'asyncio.events',
        'asyncio.streams',
        'asyncio.subprocess',
        'yarl',
        'multidict',
        'PIL.Image',
        'PIL.ImageGrab',
        'dotenv',
    ],
    hookspath=['../scripts'],  # Diretório de scripts para hooks personalizados
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='takttime-tracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Manter console para ver logs
    icon='../assets/icon.ico',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='takttime-tracker',
)
