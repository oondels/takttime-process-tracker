#!/bin/bash

# Obtém o diretório do script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Diretório raiz do projeto (um nível acima de scripts)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Muda para o diretório raiz do projeto
cd "$PROJECT_ROOT"

# Escolhe interpretador Python de forma determinística
if [ -n "${PYTHON_BIN:-}" ] && [ -x "${PYTHON_BIN}" ]; then
    PYTHON_EXEC="${PYTHON_BIN}"
elif [ -n "${VIRTUAL_ENV:-}" ] && [ -x "${VIRTUAL_ENV}/bin/python" ]; then
    PYTHON_EXEC="${VIRTUAL_ENV}/bin/python"
elif [ -x "${PROJECT_ROOT}/.venv/bin/python" ]; then
    PYTHON_EXEC="${PROJECT_ROOT}/.venv/bin/python"
elif command -v python3 &> /dev/null; then
    PYTHON_EXEC="$(command -v python3)"
elif command -v python &> /dev/null; then
    PYTHON_EXEC="$(command -v python)"
else
    echo "❌ Python não encontrado no sistema!"
    exit 1
fi

echo "============================================"
echo "  Takt-Time Process Tracker - Build Script"
echo "============================================"
echo ""
echo "📂 Diretório do projeto: $PROJECT_ROOT"
echo "🐍 Python selecionado: $PYTHON_EXEC"
echo ""

# Evita criar artefatos com dono root sem necessidade
if [ "$EUID" -eq 0 ] && [ "${ALLOW_ROOT_BUILD:-0}" != "1" ]; then
    echo "❌ Não execute este build com sudo/root."
    echo "   Isso pode quebrar permissões de build/ e dist/."
    echo "   Rode novamente como usuário normal:"
    echo "   ./build.sh"
    echo ""
    echo "   Se precisar forçar root, use:"
    echo "   ALLOW_ROOT_BUILD=1 ./build.sh"
    exit 1
fi

# Verifica se diretórios de artefatos estão graváveis pelo usuário atual
check_artifact_permissions() {
    local target="$1"
    [ -e "$target" ] || return 0

    if [ ! -w "$target" ] || find "$target" ! -writable -print -quit | grep -q .; then
        echo "❌ Sem permissão para alterar/remover: $target"
        echo "   Corrija o dono/permissões e rode novamente sem sudo:"
        echo "   sudo chown -R $(id -un):$(id -gn) \"$PROJECT_ROOT/$target\""
        return 1
    fi
    return 0
}

# Verifica se PyInstaller está instalado no Python selecionado
if ! "$PYTHON_EXEC" -m PyInstaller --version &> /dev/null; then
    echo "❌ PyInstaller não encontrado!"
    echo "📦 Instalando PyInstaller no ambiente de build..."
    "$PYTHON_EXEC" -m pip install pyinstaller
    if [ $? -ne 0 ]; then
        echo "❌ Erro ao instalar PyInstaller"
        exit 1
    fi
    echo "✅ PyInstaller instalado com sucesso!"
    echo ""
fi

# Verifica dependências Python essenciais no mesmo interpretador do build
missing_modules="$(
"$PYTHON_EXEC" -c "
import importlib.util
modules = [
    'PyQt5',
    'paho.mqtt.client',
    'cv2',
    'pytesseract',
    'numpy',
    'torch',
    'torchvision',
    'aio_pika',
    'aiormq',
    'pamqp',
    'yarl',
    'multidict',
    'ultralytics',
    'dotenv',
]
missing = [m for m in modules if importlib.util.find_spec(m) is None]
print('\n'.join(missing))
"
)"

if [ -n "$missing_modules" ]; then
    echo "❌ Dependências ausentes no Python selecionado:"
    while IFS= read -r module_name; do
        if [ -n "$module_name" ]; then
            echo "   - $module_name"
        fi
    done <<< "$missing_modules"
    echo ""
    echo "Instale no mesmo ambiente do build:"
    echo "   $PYTHON_EXEC -m pip install -r requirements.txt"
    echo ""
    echo "Dica: execute sem sudo ou use a .venv do projeto para evitar misturar ambientes."
    exit 1
fi

# Limpa builds anteriores
echo "🧹 Limpando builds anteriores..."
check_artifact_permissions "build" || exit 1
check_artifact_permissions "dist" || exit 1
rm -rf build/ dist/

# Verifica se o modelo existe
if [ ! -f "assets/train_2025.pt" ]; then
    echo "⚠️  Aviso: Modelo train_2025.pt não encontrado em assets/!"
    echo "   Certifique-se de ter o modelo antes de executar o aplicativo."
fi

# Verifica se tesseract está instalado
if ! command -v tesseract &> /dev/null
then
    echo "⚠️  Aviso: Tesseract OCR não encontrado!"
    echo "   Instale com: sudo apt install tesseract-ocr"
fi

# Executa PyInstaller
echo ""
echo "🔨 Compilando aplicativo..."
"$PYTHON_EXEC" -m PyInstaller scripts/takttime-tracker.spec --clean

# Verifica se a compilação foi bem-sucedida
if [ $? -eq 0 ]; then
    echo ""
    echo "============================================"
    echo "✅ Compilação concluída com sucesso!"
    echo "============================================"
    echo ""
    echo "Executável criado em: dist/takttime-tracker/"
    echo "Para executar:"
    echo "   cd dist/takttime-tracker"
    echo "   chmod +x takttime-tracker"
    echo "   ./takttime-tracker"
    echo ""
    
    # Cria arquivo README no diretório de distribuição
    cat > dist/takttime-tracker/README.txt << 'EOF'
===========================================
 Takt-Time Process Tracker
===========================================

PRÉ-REQUISITOS:
------------------
1. Tesseract OCR instalado no sistema
   Ubuntu/Debian: sudo apt install tesseract-ocr
   
2. Modelo YOLO (train_2025.pt) no mesmo diretório

3. Arquivo config/config.json com as configurações


COMO EXECUTAR:
------------------
./takttime-tracker


CONFIGURAÇÃO:
-----------------
1. Execute o aplicativo
2. Clique em "⚙️ Configurar"
3. Preencha os dados do dispositivo (obrigatório):
   - Número da Célula
   - Fábrica
   - Líder da Célula
4. Configure a rede WiFi (opcional)
5. Desbloqueie e configure dados técnicos (opcional):
   - Usuário: TECH_CONFIG_USER (padrão: admin)
   - Senha: TECH_CONFIG_PASS


LOGS:
---------
Os logs são salvos em:
- logs/app_debug.log (interface gráfica)
- logs/main_debug.log (detecção de takt)


PROBLEMAS:
-------------
- Erro no modelo: Verifique se train_2025.pt existe
- Erro MQTT: Verifique configurações técnicas e conexão de rede
- Erro OCR: Instale tesseract-ocr
- Erro ao iniciar: Execute no terminal para ver mensagens de erro


📧 SUPORTE:
-----------
Para problemas ou dúvidas, contate o suporte técnico.

EOF
    
    echo "README criado em: dist/takttime-tracker/README.txt"
    echo ""
    
    # Copia o ícone para o diretório de distribuição
    echo "Copiando ícone..."
    if [ -f "assets/icon.png" ]; then
        cp assets/icon.png dist/takttime-tracker/
    else
        echo "⚠️  Ícone assets/icon.png não encontrado."
    fi
    echo "Copiando modelo YOLO..."
    if [ -f "assets/train_2025.pt" ]; then
        cp assets/train_2025.pt dist/takttime-tracker/
    else
        echo "⚠️  Modelo assets/train_2025.pt não encontrado."
    fi
    
    # Cria arquivo .desktop para integração com o Linux
    cat > dist/takttime-tracker/takttime-tracker.desktop << 'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Takt-Time Process Tracker
Comment=Sistema de Monitoramento de Takt-Time
Exec=/opt/dass_apps/takttime-process-tracker/dist/takttime-tracker/takttime-tracker
Path=/opt/dass_apps/takttime-process-tracker/dist/takttime-tracker
Icon=/opt/dass_apps/takttime-process-tracker/dist/takttime-tracker/icon.png
Terminal=false
Categories=Utility;Development;
EOF

echo "Configurando diretórios e arquivos de configuração..."
    
    # Criar pastas essenciais no build final
    mkdir -p dist/takttime-tracker/config
    mkdir -p dist/takttime-tracker/logs
    
    # Copiar arquivo de configuração base (como exemplo ou arquivo pronto para uso)
    if [ -f "config/config.example.json" ]; then
        cp config/config.example.json dist/takttime-tracker/config/config.json
        echo "✅ config.json adicionado à distribuição"
    else
        echo "⚠️ config.example.json não encontrado"
    fi
    
    # Copiar arquivo de variáveis de ambiente base
    if [ -f ".env.example" ]; then
        cp .env.example dist/takttime-tracker/.env
        echo "✅ .env adicionado à distribuição"
    else
        echo "⚠️ .env.example não encontrado"
    fi
    
    echo "Ícone e arquivo .desktop criados"
    echo ""
    echo "Para adicionar ao menu de aplicativos do Linux:"
    echo "   1. Copie takttime-tracker.desktop para ~/.local/share/applications/ (se necessário)"
    echo "   2. Edite o campo Exec= com o caminho absoluto do executável (se necessário)"
    echo "   3. Edite o campo Icon= com o caminho absoluto do ícone (se necessário)"
    echo "   4. Rode chmod +x ~/.local/share/applications/takttime-tracker.desktop"
    echo "   5. Copie o arquivo train_2025.pt para o mesmo diretório do executável"
    echo ""

    DESKTOP_HOME="$HOME"
    if [ "$EUID" -eq 0 ] && [ -n "${SUDO_USER:-}" ] && [ "${SUDO_USER}" != "root" ]; then
        DESKTOP_HOME="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
    fi

    DESKTOP_APPS_DIR="$DESKTOP_HOME/.local/share/applications"
    mkdir -p "$DESKTOP_APPS_DIR"
    cp dist/takttime-tracker/takttime-tracker.desktop "$DESKTOP_APPS_DIR/"
    echo "Arquivo .desktop copiado para: $DESKTOP_APPS_DIR/"
else
    echo ""
    echo "============================================"
    echo "❌ Erro durante a compilação!"
    echo "============================================"
    echo ""
    echo "Verifique os erros acima e tente novamente."
    exit 1
fi
