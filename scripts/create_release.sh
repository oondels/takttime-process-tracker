#!/bin/bash

# Script para criar pacote de release do Takt-Time Tracker
# Autor: Sistema de Build Automatizado
# Data: $(date +%Y-%m-%d)

set -e  # Para em caso de erro

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funções auxiliares
print_header() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "📋 $1"
}

# Obtém o diretório do script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

print_header "Takt-Time Tracker - Release Builder"

# 1. Verifica versão
print_info "Verificando versão..."

# Tenta obter do git
if command -v git &> /dev/null && git rev-parse --git-dir > /dev/null 2>&1; then
    # Verifica se existe uma tag
    GIT_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
    
    if [ -n "$GIT_TAG" ]; then
        VERSION="$GIT_TAG"
        print_success "Versão detectada do git: $VERSION"
    else
        # Usa timestamp se não houver tag
        VERSION="v$(date +%Y%m%d-%H%M)"
        print_warning "Nenhuma tag git encontrada, usando timestamp: $VERSION"
        print_info "💡 Dica: Crie uma tag com: git tag -a v1.0.0 -m 'Release v1.0.0'"
    fi
else
    # Usa timestamp se não for repositório git
    VERSION="v$(date +%Y%m%d-%H%M)"
    print_warning "Não é um repositório git, usando timestamp: $VERSION"
fi

# Permite sobrescrever versão
if [ -n "$1" ]; then
    VERSION="$1"
    print_info "Versão manual fornecida: $VERSION"
fi

echo ""
read -p "Confirma a versão $VERSION? (s/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    read -p "Digite a versão desejada (ex: v1.0.0): " VERSION
    if [ -z "$VERSION" ]; then
        print_error "Versão não pode ser vazia!"
        exit 1
    fi
fi

print_success "Versão confirmada: $VERSION"

# 2. Verifica se o build já foi feito
print_info "Verificando se o executável existe..."

if [ ! -f "dist/takttime-tracker/takttime-tracker" ]; then
    print_warning "Executável não encontrado!"
    echo ""
    read -p "Deseja compilar agora? (S/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        print_error "Não é possível criar o release sem o executável!"
        exit 1
    fi
    
    print_info "Iniciando build..."
    ./build.sh
    
    if [ $? -ne 0 ]; then
        print_error "Falha no build!"
        exit 1
    fi
else
    print_success "Executável encontrado"
fi

# 3. Cria diretório de release
print_header "Criando Pacote de Release"

RELEASE_NAME="takttime-tracker-$VERSION-linux-x64"
RELEASE_DIR="dist/$RELEASE_NAME"

print_info "Criando diretório: $RELEASE_DIR"

rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

# 4. Copia arquivos do executável
print_info "Copiando executável e dependências..."
cp -r dist/takttime-tracker/* "$RELEASE_DIR/"

# 5. Copia arquivos adicionais
print_info "Copiando documentação..."

# README
if [ -f "README.md" ]; then
    cp README.md "$RELEASE_DIR/"
    print_success "README.md copiado"
fi

# Tutorial de build (se existir)
if [ -f "TUTORIAL_BUILD.md" ]; then
    cp TUTORIAL_BUILD.md "$RELEASE_DIR/"
    print_success "TUTORIAL_BUILD.md copiado"
fi

# Requirements (referência)
if [ -f "requirements.txt" ]; then
    cp requirements.txt "$RELEASE_DIR/"
    print_success "requirements.txt copiado"
fi

# 6. Cria script de instalação
print_info "Criando script de instalação..."

cat > "$RELEASE_DIR/install.sh" << 'EOF'
#!/bin/bash

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Instalador Takt-Time Process Tracker${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Diretório de instalação
INSTALL_DIR="$HOME/.local/share/takttime-tracker"

echo -e "📂 Instalando em: ${GREEN}$INSTALL_DIR${NC}"
echo ""

# Cria diretório
mkdir -p "$INSTALL_DIR"

# Copia arquivos
echo "📋 Copiando arquivos..."
cp -r ./* "$INSTALL_DIR/" 2>/dev/null || {
    echo -e "${RED}❌ Erro ao copiar arquivos!${NC}"
    exit 1
}

# Torna executável
chmod +x "$INSTALL_DIR/takttime-tracker"

echo -e "${GREEN}✅ Arquivos copiados com sucesso${NC}"
echo ""

# Verifica dependências
echo "🔍 Verificando dependências do sistema..."
DEPS_MISSING=0

# Tesseract
if ! command -v tesseract &> /dev/null; then
    echo -e "${RED}❌ Tesseract OCR não encontrado${NC}"
    echo "   Instale com: sudo apt install tesseract-ocr tesseract-ocr-por"
    DEPS_MISSING=1
else
    TESS_VERSION=$(tesseract --version 2>&1 | head -1)
    echo -e "${GREEN}✅ Tesseract: $TESS_VERSION${NC}"
fi

# Qt5
if ! ldconfig -p | grep -q libQt5Core; then
    echo -e "${RED}❌ Qt5 não encontrado${NC}"
    echo "   Instale com: sudo apt install libqt5core5a libqt5gui5 libqt5widgets5"
    DEPS_MISSING=1
else
    echo -e "${GREEN}✅ Qt5 instalado${NC}"
fi

# Python (opcional, só para referência)
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✅ $PYTHON_VERSION (referência)${NC}"
fi

echo ""

if [ $DEPS_MISSING -eq 1 ]; then
    echo -e "${YELLOW}⚠️  Algumas dependências estão faltando!${NC}"
    echo ""
    echo "Execute os comandos de instalação acima antes de usar o aplicativo."
    echo ""
else
    echo -e "${GREEN}✅ Todas as dependências estão instaladas!${NC}"
    echo ""
fi

# Cria atalho no menu
echo "🖼️  Criando atalho no menu de aplicativos..."
mkdir -p "$HOME/.local/share/applications"

cat > "$HOME/.local/share/applications/takttime-tracker.desktop" << EOFDESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=Takt-Time Tracker
Comment=Sistema de Monitoramento de Takt-Time
Exec=$INSTALL_DIR/takttime-tracker
Path=$INSTALL_DIR
Icon=$INSTALL_DIR/icon.png
Terminal=false
Categories=Utility;Development;
EOFDESKTOP

chmod +x "$HOME/.local/share/applications/takttime-tracker.desktop"

echo -e "${GREEN}✅ Atalho criado${NC}"
echo ""

# Cria link simbólico opcional
read -p "Deseja criar um comando 'takttime' no terminal? (S/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    mkdir -p "$HOME/.local/bin"
    ln -sf "$INSTALL_DIR/takttime-tracker" "$HOME/.local/bin/takttime"
    
    # Adiciona ao PATH se necessário
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo ""
        echo -e "${YELLOW}⚠️  Adicione ao seu PATH:${NC}"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
        echo "Comando adicionado ao .bashrc"
        echo "Execute: source ~/.bashrc"
    fi
    
    echo -e "${GREEN}✅ Comando 'takttime' criado${NC}"
fi

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}✅ Instalação concluída com sucesso!${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo "🚀 Para executar:"
echo "   1. Procure 'Takt-Time Tracker' no menu de aplicativos"
echo "   2. Ou execute: $INSTALL_DIR/takttime-tracker"
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo "   3. Ou digite: takttime (após adicionar ao PATH)"
fi
echo ""
echo "📖 Consulte README.md para configuração e uso"
echo ""
EOF

chmod +x "$RELEASE_DIR/install.sh"
print_success "Script de instalação criado"

# 7. Cria script de desinstalação
print_info "Criando script de desinstalação..."

cat > "$RELEASE_DIR/uninstall.sh" << 'EOF'
#!/bin/bash

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}============================================${NC}"
echo -e "${YELLOW}  Desinstalador Takt-Time Process Tracker${NC}"
echo -e "${YELLOW}============================================${NC}"
echo ""

INSTALL_DIR="$HOME/.local/share/takttime-tracker"

if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${RED}❌ Takt-Time Tracker não está instalado${NC}"
    exit 1
fi

echo "📂 Instalação encontrada em: $INSTALL_DIR"
echo ""
read -p "Tem certeza que deseja desinstalar? (s/N): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    echo "Desinstalação cancelada."
    exit 0
fi

echo ""
echo "🗑️  Removendo arquivos..."

# Remove diretório
rm -rf "$INSTALL_DIR"
echo -e "${GREEN}✅ Arquivos removidos${NC}"

# Remove atalho
if [ -f "$HOME/.local/share/applications/takttime-tracker.desktop" ]; then
    rm "$HOME/.local/share/applications/takttime-tracker.desktop"
    echo -e "${GREEN}✅ Atalho removido${NC}"
fi

# Remove link simbólico
if [ -L "$HOME/.local/bin/takttime" ]; then
    rm "$HOME/.local/bin/takttime"
    echo -e "${GREEN}✅ Comando 'takttime' removido${NC}"
fi

echo ""
echo -e "${GREEN}✅ Desinstalação concluída!${NC}"
echo ""
EOF

chmod +x "$RELEASE_DIR/uninstall.sh"
print_success "Script de desinstalação criado"

# 8. Cria README específico do release
print_info "Criando README_INSTALL.txt..."

cat > "$RELEASE_DIR/README_INSTALL.txt" << EOF
===========================================
 Takt-Time Process Tracker - $VERSION
===========================================

📦 INSTALAÇÃO RÁPIDA
--------------------
./install.sh


📋 PRÉ-REQUISITOS DO SISTEMA
-----------------------------
1. Ubuntu 20.04+ ou Debian 11+
2. Tesseract OCR:
   sudo apt install tesseract-ocr tesseract-ocr-por
3. Qt5:
   sudo apt install libqt5core5a libqt5gui5 libqt5widgets5


🚀 EXECUTAR APLICATIVO
-----------------------
Após instalação:
1. Menu de aplicativos → "Takt-Time Tracker"
2. Ou execute: ~/.local/share/takttime-tracker/takttime-tracker


⚙️ PRIMEIRA CONFIGURAÇÃO
-------------------------
1. Execute o aplicativo
2. Clique em "⚙️ Configurar"
3. Preencha dados do dispositivo:
   - Número da Célula
   - Fábrica
   - Líder da Célula
4. Configure WiFi (opcional)
5. Configurações técnicas (desbloqueio):
   - Usuário: admin
   - Senha: dass@2025


📁 ESTRUTURA DE ARQUIVOS
-------------------------
takttime-tracker          → Executável principal
train_2025.pt             → Modelo YOLO (obrigatório)
config/config.json        → Configurações
logs/                     → Logs do sistema
README.md                 → Documentação completa
install.sh                → Script de instalação
uninstall.sh              → Script de desinstalação


📝 LOGS E DEBUG
----------------
Logs ficam em:
- logs/app_debug.log      → Interface gráfica
- logs/main_debug.log     → Detecção de takt

Para ver erros:
./takttime-tracker


🔧 DESINSTALAÇÃO
-----------------
./uninstall.sh


❓ PROBLEMAS COMUNS
-------------------
Q: "Permission denied" ao executar
A: chmod +x takttime-tracker

Q: Erro ao carregar modelo YOLO
A: Verifique se train_2025.pt está no mesmo diretório

Q: Erro MQTT ao iniciar
A: Normal se não houver broker configurado

Q: Interface não abre
A: Verifique se Qt5 está instalado


📧 SUPORTE
-----------
GitHub: https://github.com/oondels/takttime-process-tracker
Issues: https://github.com/oondels/takttime-process-tracker/issues


📜 LICENÇA
-----------
Consulte LICENSE no repositório.


📦 Versão: $VERSION
📅 Data: $(date +%Y-%m-%d)
EOF

print_success "README_INSTALL.txt criado"

# 9. Cria o tarball
print_header "Criando Arquivo .tar.gz"

TARBALL="$RELEASE_NAME.tar.gz"

print_info "Compactando: $TARBALL"

cd dist/
tar -czf "$TARBALL" "$RELEASE_NAME/"

if [ $? -eq 0 ]; then
    print_success "Tarball criado com sucesso!"
    
    # Informações do arquivo
    FILE_SIZE=$(du -h "$TARBALL" | cut -f1)
    print_info "Tamanho: $FILE_SIZE"
    
    # Calcula hash
    if command -v sha256sum &> /dev/null; then
        HASH=$(sha256sum "$TARBALL" | cut -d' ' -f1)
        echo "$HASH  $TARBALL" > "$TARBALL.sha256"
        print_success "Hash SHA256: $HASH"
        print_info "Hash salvo em: $TARBALL.sha256"
    fi
else
    print_error "Falha ao criar tarball!"
    exit 1
fi

cd "$PROJECT_ROOT"

# 10. Testa a extração
print_header "Testando Extração"

TEST_DIR="dist/test-extraction-$$"
mkdir -p "$TEST_DIR"

print_info "Extraindo em diretório temporário..."
tar -xzf "dist/$TARBALL" -C "$TEST_DIR"

if [ -f "$TEST_DIR/$RELEASE_NAME/takttime-tracker" ]; then
    print_success "Extração OK"
    
    # Verifica permissões
    if [ -x "$TEST_DIR/$RELEASE_NAME/takttime-tracker" ]; then
        print_success "Permissões de execução OK"
    else
        print_warning "Executável sem permissão de execução"
    fi
    
    # Verifica arquivos críticos
    if [ -f "$TEST_DIR/$RELEASE_NAME/train_2025.pt" ]; then
        print_success "Modelo YOLO encontrado"
    else
        print_error "Modelo YOLO NÃO encontrado!"
    fi
    
    if [ -f "$TEST_DIR/$RELEASE_NAME/install.sh" ]; then
        print_success "Script de instalação encontrado"
    fi
else
    print_error "Falha na extração!"
fi

# Limpa teste
rm -rf "$TEST_DIR"

# 11. Resumo final
print_header "Resumo do Release"

echo -e "${GREEN}✅ Release criado com sucesso!${NC}"
echo ""
echo -e "${BLUE}📦 Versão:${NC} $VERSION"
echo -e "${BLUE}📁 Arquivo:${NC} dist/$TARBALL"
echo -e "${BLUE}📊 Tamanho:${NC} $FILE_SIZE"
if [ -n "$HASH" ]; then
    echo -e "${BLUE}🔒 SHA256:${NC} $HASH"
fi
echo ""
echo -e "${YELLOW}📋 Próximos Passos:${NC}"
echo ""
echo "1️⃣  Teste o pacote:"
echo "   cd /tmp"
echo "   tar -xzf $PROJECT_ROOT/dist/$TARBALL"
echo "   cd $RELEASE_NAME"
echo "   ./install.sh"
echo ""
echo "2️⃣  Publique no GitHub:"
echo "   gh release create $VERSION dist/$TARBALL \\"
echo "     --title \"Takt-Time Tracker $VERSION\" \\"
echo "     --notes \"Veja CHANGELOG.md para detalhes\""
echo ""
echo "3️⃣  Ou crie release manualmente:"
echo "   - Vá para https://github.com/oondels/takttime-process-tracker/releases/new"
echo "   - Tag version: $VERSION"
echo "   - Faça upload de: dist/$TARBALL"
echo ""
echo "4️⃣  Distribua o link:"
echo "   https://github.com/oondels/takttime-process-tracker/releases/download/$VERSION/$TARBALL"
echo ""

print_success "Build de release concluído! 🎉"
