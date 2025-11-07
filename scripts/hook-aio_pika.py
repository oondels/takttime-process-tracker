"""
PyInstaller hook para aio_pika e suas dependências
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

# Coleta todos os submódulos
hiddenimports = collect_submodules('aio_pika')
hiddenimports += collect_submodules('aiormq')
hiddenimports += collect_submodules('pamqp')
hiddenimports += collect_submodules('yarl')
hiddenimports += collect_submodules('multidict')

# Coleta metadados (necessário para importlib.metadata)
datas = []
datas += copy_metadata('aio_pika')
datas += copy_metadata('aio-pika')  # Nome alternativo
datas += copy_metadata('aiormq')
datas += copy_metadata('pamqp')
datas += copy_metadata('yarl')
datas += copy_metadata('multidict')

# Coleta binários e dados
binaries = []
datas_all, binaries_all, hiddenimports_all = collect_all('aio_pika')
datas += datas_all
binaries += binaries_all
hiddenimports += hiddenimports_all
