# 📦 Tutorial Completo: Build e Distribuição do Takt-Time Tracker

## 📋 Índice
1. [Pré-requisitos](#pré-requisitos)
2. [Preparação do Ambiente](#preparação-do-ambiente)
3. [Processo de Build](#processo-de-build)
4. [Criação do Pacote .tar.gz](#criação-do-pacote-targz)
5. [Disponibilização via GitHub Releases](#disponibilização-via-github-releases)
6. [Instalação pelo Usuário Final](#instalação-pelo-usuário-final)
7. [Troubleshooting](#troubleshooting)

---

## 🛠️ Pré-requisitos

### No Sistema de Build (seu PC)

```bash
# 1. Python 3.8 ou superior
python3 --version

# 2. Git
git --version

# 3. Tesseract OCR
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-por

# 4. Dependências Qt5
sudo apt install -y libqt5core5a libqt5gui5 libqt5widgets5

# 5. PyInstaller
pip install pyinstaller
```

### Estrutura do Projeto

Certifique-se de que seu projeto tem:
```
takttime-process-tracker/
├── app.py                    # Aplicativo principal
├── main.py                   # Detecção de takt
├── mqtt_manager.py           # Gerenciador MQTT
├── requirements.txt          # Dependências Python
├── assets/
│   ├── train_2025.pt        # Modelo YOLO (OBRIGATÓRIO)
│   ├── icon.png             # Ícone do app
│   └── icon.ico             # Ícone Windows
├── config/
│   └── config.json          # Configuração padrão
└── scripts/
    ├── build.sh             # Script de build
    └── takttime-tracker.spec # Configuração PyInstaller
```

---

## 🔧 Preparação do Ambiente

### 1. Clone e Configure o Projeto

```bash
# Se ainda não clonou
git clone https://github.com/oondels/takttime-process-tracker.git
cd takttime-process-tracker

# Crie e ative ambiente virtual
python3 -m venv venv
source venv/bin/activate

# Instale todas as dependências
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
```

### 2. Teste o Aplicativo

Antes de fazer o build, teste se tudo funciona:

```bash
python app.py
```

✅ **Checklist de testes:**
- [ ] Interface abre sem erros
- [ ] Configurações são salvas corretamente
- [ ] Detecção de takt funciona (se tiver câmera)
- [ ] Logs são criados em `logs/`

---

## 🏗️ Processo de Build

### Método 1: Script Automático (Recomendado)

```bash
# Execute o script de build
chmod +x build.sh
./build.sh
```

O script irá:
1. ✅ Verificar se PyInstaller está instalado
2. 🧹 Limpar builds anteriores
3. 🔨 Compilar o aplicativo
4. 📄 Criar README.txt
5. 🎨 Copiar ícones
6. 📋 Criar arquivo .desktop

**Output esperado:**
```
✅ Compilação concluída com sucesso!
📁 Executável criado em: dist/takttime-tracker/
```

### Método 2: Manual

```bash
# Entre no ambiente virtual
source venv/bin/activate

# Execute PyInstaller
pyinstaller scripts/takttime-tracker.spec --clean

# Verifique a saída
ls -lh dist/takttime-tracker/
```

### 3. Teste o Executável

```bash
cd dist/takttime-tracker
./takttime-tracker
```

⚠️ **Problemas comuns:**
- **Erro de modelo**: Verifique se `train_2025.pt` foi incluído
- **Erro de permissão**: Execute `chmod +x takttime-tracker`
- **Erro de biblioteca**: Verifique se Qt5 está instalado no sistema

---

## 📦 Criação do Pacote .tar.gz

### 1. Prepare o Diretório de Distribuição

```bash
cd dist/

# Crie estrutura completa
mkdir -p takttime-tracker-release/{logs,config}

# Copie o executável e arquivos
cp -r takttime-tracker/* takttime-tracker-release/

# Adicione arquivos extras
cp ../README.md takttime-tracker-release/
cp ../requirements.txt takttime-tracker-release/
```

### 2. Crie um Script de Instalação

Crie `dist/takttime-tracker-release/install.sh`:

```bash
#!/bin/bash

echo "============================================"
echo "  Instalador Takt-Time Process Tracker"
echo "============================================"
echo ""

# Detecta diretório de instalação
INSTALL_DIR="$HOME/.local/share/takttime-tracker"

echo "📂 Instalando em: $INSTALL_DIR"
echo ""

# Cria diretório
mkdir -p "$INSTALL_DIR"

# Copia arquivos
echo "📋 Copiando arquivos..."
cp -r ./* "$INSTALL_DIR/"

# Torna executável
chmod +x "$INSTALL_DIR/takttime-tracker"

# Verifica dependências
echo ""
echo "🔍 Verificando dependências..."

if ! command -v tesseract &> /dev/null; then
    echo "❌ Tesseract OCR não encontrado"
    echo "   Instale com: sudo apt install tesseract-ocr tesseract-ocr-por"
    DEPS_MISSING=1
fi

if ! ldconfig -p | grep -q libQt5Core; then
    echo "❌ Qt5 não encontrado"
    echo "   Instale com: sudo apt install libqt5core5a libqt5gui5 libqt5widgets5"
    DEPS_MISSING=1
fi

if [ -z "$DEPS_MISSING" ]; then
    echo "✅ Todas as dependências estão instaladas"
fi

# Cria atalho no menu
echo ""
echo "🖼️  Criando atalho no menu..."
mkdir -p "$HOME/.local/share/applications"

cat > "$HOME/.local/share/applications/takttime-tracker.desktop" << EOF
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
EOF

chmod +x "$HOME/.local/share/applications/takttime-tracker.desktop"

echo ""
echo "============================================"
echo "✅ Instalação concluída!"
echo "============================================"
echo ""
echo "🚀 Para executar:"
echo "   1. Procure 'Takt-Time Tracker' no menu de aplicativos"
echo "   2. Ou execute: $INSTALL_DIR/takttime-tracker"
echo ""
echo "📖 Consulte README.md para mais informações"
```

Torne-o executável:
```bash
chmod +x dist/takttime-tracker-release/install.sh
```

### 3. Crie o Arquivo .tar.gz

```bash
cd dist/

# Opção 1: Versão com timestamp
VERSION=$(date +%Y%m%d-%H%M)
tar -czf takttime-tracker-v$VERSION-linux-x64.tar.gz takttime-tracker-release/

# Opção 2: Versão com git tag
VERSION=$(git describe --tags --abbrev=0 2>/dev/null || echo "1.0.0")
tar -czf takttime-tracker-$VERSION-linux-x64.tar.gz takttime-tracker-release/

# Opção 3: Versão manual
tar -czf takttime-tracker-v1.0.0-linux-x64.tar.gz takttime-tracker-release/
```

### 4. Verifique o Pacote

```bash
# Veja o tamanho
ls -lh takttime-tracker-*.tar.gz

# Liste o conteúdo
tar -tzf takttime-tracker-*.tar.gz | head -20

# Teste a extração
mkdir test-install
cd test-install
tar -xzf ../takttime-tracker-*.tar.gz
cd takttime-tracker-release
./install.sh
```

---

## 🚀 Disponibilização via GitHub Releases

### Método 1: Interface Web do GitHub

1. **Vá para seu repositório no GitHub**
   ```
   https://github.com/oondels/takttime-process-tracker
   ```

2. **Clique em "Releases"** (lado direito)

3. **Clique em "Create a new release"**

4. **Preencha os campos:**
   - **Tag version**: `v1.0.0` (siga o padrão [semver](https://semver.org/))
   - **Release title**: `Takt-Time Tracker v1.0.0`
   - **Description**:
     ```markdown
     ## 🎉 Primeira Release Oficial
     
     ### ✨ Funcionalidades
     - ✅ Detecção automática de takt-time
     - ✅ Interface gráfica intuitiva
     - ✅ Integração MQTT
     - ✅ Logs detalhados
     
     ### 📦 Instalação
     
     #### Linux (Ubuntu/Debian)
     ```bash
     # 1. Baixar
     wget https://github.com/oondels/takttime-process-tracker/releases/download/v1.0.0/takttime-tracker-v1.0.0-linux-x64.tar.gz
     
     # 2. Extrair
     tar -xzf takttime-tracker-v1.0.0-linux-x64.tar.gz
     cd takttime-tracker-release/
     
     # 3. Instalar
     ./install.sh
     ```
     
     ### 📋 Requisitos do Sistema
     - Ubuntu 20.04+ ou Debian 11+
     - Tesseract OCR
     - Qt5
     
     ### 📝 Notas
     - Primeira versão estável
     - Modelo YOLO incluído
     - Suporte a português
     
     ### 🐛 Problemas Conhecidos
     - Nenhum relatado
     ```

5. **Faça upload do arquivo .tar.gz**
   - Arraste o arquivo `takttime-tracker-v1.0.0-linux-x64.tar.gz` para a área de anexos

6. **Clique em "Publish release"**

### Método 2: Linha de Comando (GitHub CLI)

```bash
# Instale o GitHub CLI (se não tiver)
sudo apt install gh

# Faça login
gh auth login

# Crie a release
gh release create v1.0.0 \
  dist/takttime-tracker-v1.0.0-linux-x64.tar.gz \
  --title "Takt-Time Tracker v1.0.0" \
  --notes "Primeira release oficial. Veja README para instruções de instalação."

# Verifique
gh release view v1.0.0
```

### 3. Automatize com GitHub Actions

Crie `.github/workflows/release.yml`:

```yaml
name: Build and Release

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: ubuntu-22.04
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v3
    
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Install system dependencies
      run: |
        sudo apt update
        sudo apt install -y tesseract-ocr libqt5core5a libqt5gui5 libqt5widgets5
    
    - name: Install Python dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pyinstaller
    
    - name: Build executable
      run: |
        chmod +x build.sh
        ./build.sh
    
    - name: Create release package
      run: |
        cd dist/
        mkdir -p takttime-tracker-release
        cp -r takttime-tracker/* takttime-tracker-release/
        cp ../README.md takttime-tracker-release/
        
        # Cria install.sh (copie o conteúdo acima)
        cat > takttime-tracker-release/install.sh << 'EOF'
        # (Cole o script de instalação aqui)
        EOF
        chmod +x takttime-tracker-release/install.sh
        
        # Cria tarball
        VERSION=${GITHUB_REF#refs/tags/}
        tar -czf takttime-tracker-${VERSION}-linux-x64.tar.gz takttime-tracker-release/
    
    - name: Create GitHub Release
      uses: softprops/action-gh-release@v1
      with:
        files: dist/takttime-tracker-*.tar.gz
        body: |
          ## 🎉 Release Automática
          
          Executável compilado automaticamente via GitHub Actions.
          
          ### 📥 Instalação
          ```bash
          wget https://github.com/${{ github.repository }}/releases/download/${{ github.ref_name }}/takttime-tracker-${{ github.ref_name }}-linux-x64.tar.gz
          tar -xzf takttime-tracker-${{ github.ref_name }}-linux-x64.tar.gz
          cd takttime-tracker-release/
          ./install.sh
          ```
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Para disparar o build automático:**

```bash
# Crie uma tag
git tag -a v1.0.0 -m "Release v1.0.0"

# Envie para o GitHub
git push origin v1.0.0

# O GitHub Actions irá automaticamente:
# 1. Compilar o executável
# 2. Criar o .tar.gz
# 3. Criar a release
# 4. Fazer upload do arquivo
```

---

## 👤 Instalação pelo Usuário Final

### Passo a Passo Simples

```bash
# 1. Baixar (substitua URL pela sua release)
wget https://github.com/oondels/takttime-process-tracker/releases/download/v1.0.0/takttime-tracker-v1.0.0-linux-x64.tar.gz

# 2. Extrair
tar -xzf takttime-tracker-v1.0.0-linux-x64.tar.gz

# 3. Entrar no diretório
cd takttime-tracker-release/

# 4. Executar instalador
chmod +x install.sh
./install.sh

# 5. Executar aplicativo
# Opção A: Via menu de aplicativos
# Procure por "Takt-Time Tracker"

# Opção B: Via terminal
~/.local/share/takttime-tracker/takttime-tracker
```

---

## 🔍 Troubleshooting

### Problema: "No module named 'X'" ao executar

**Solução:**
```bash
# Adicione o módulo ao hiddenimports em takttime-tracker.spec
hiddenimports=[
    # ... outros módulos
    'X',  # Adicione aqui
]

# Recompile
./build.sh
```

### Problema: Modelo YOLO não encontrado

**Solução:**
```bash
# Verifique se está no spec
cat scripts/takttime-tracker.spec | grep train_2025.pt

# Deve mostrar:
# ('../assets/train_2025.pt', '.'),

# Verifique no dist
ls -lh dist/takttime-tracker/train_2025.pt
```

### Problema: Executável muito grande (> 2GB)

**Solução:**
```bash
# Exclua pacotes desnecessários do spec
excludes=[
    'matplotlib',
    'scipy',
    'pandas',
    'notebook',
    'IPython',
],

# Use UPX para comprimir
upx=True,
```

### Problema: Erro ao conectar MQTT

**Diagnóstico:**
```bash
# Execute com console ativado
./takttime-tracker

# Veja logs
tail -f logs/app_debug.log
tail -f logs/main_debug.log
```

### Problema: "Permission denied"

**Solução:**
```bash
chmod +x takttime-tracker
chmod +x install.sh
```

---

## 📊 Checklist Final

Antes de publicar a release:

- [ ] ✅ Testei o executável em máquina limpa
- [ ] ✅ Modelo YOLO incluído e funcionando
- [ ] ✅ Dependências documentadas no README
- [ ] ✅ Script de instalação funciona
- [ ] ✅ Versão atualizada em todos os arquivos
- [ ] ✅ CHANGELOG.md atualizado
- [ ] ✅ Tag git criada
- [ ] ✅ Release notes escritas
- [ ] ✅ Arquivo .tar.gz testado
- [ ] ✅ Links de download funcionando

---

## 🎯 Resumo Rápido

```bash
# BUILD
./build.sh

# EMPACOTAR
cd dist/
tar -czf takttime-tracker-v1.0.0-linux-x64.tar.gz takttime-tracker-release/

# PUBLICAR
gh release create v1.0.0 takttime-tracker-v1.0.0-linux-x64.tar.gz

# INSTALAR (usuário final)
wget <URL_DA_RELEASE>
tar -xzf takttime-tracker-*.tar.gz
cd takttime-tracker-release/
./install.sh
```

---

## 📚 Recursos Adicionais

- [PyInstaller Documentation](https://pyinstaller.org/en/stable/)
- [GitHub Releases Guide](https://docs.github.com/en/repositories/releasing-projects-on-github)
- [Semantic Versioning](https://semver.org/)
- [Linux Desktop Entry Spec](https://specifications.freedesktop.org/desktop-entry-spec/latest/)

---

**Sucesso no seu build! 🚀**
