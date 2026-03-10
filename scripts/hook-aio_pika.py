"""
PyInstaller hook para aio_pika e suas dependências
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

def _safe_collect_submodules(module_name):
    try:
        return collect_submodules(module_name)
    except Exception:
        return []


def _safe_copy_metadata(dist_name):
    try:
        return copy_metadata(dist_name)
    except Exception:
        return []


def _safe_collect_all(module_name):
    try:
        return collect_all(module_name)
    except Exception:
        return [], [], []


# Coleta todos os submódulos
hiddenimports = _safe_collect_submodules('aio_pika')
hiddenimports += _safe_collect_submodules('aiormq')
hiddenimports += _safe_collect_submodules('pamqp')
hiddenimports += _safe_collect_submodules('yarl')
hiddenimports += _safe_collect_submodules('multidict')

# Coleta metadados (necessário para importlib.metadata)
datas = []
datas += _safe_copy_metadata('aio-pika')
datas += _safe_copy_metadata('aio_pika')
datas += _safe_copy_metadata('aiormq')
datas += _safe_copy_metadata('pamqp')
datas += _safe_copy_metadata('yarl')
datas += _safe_copy_metadata('multidict')

# Coleta binários e dados
binaries = []
datas_all, binaries_all, hiddenimports_all = _safe_collect_all('aio_pika')
datas += datas_all
binaries += binaries_all
hiddenimports += hiddenimports_all
