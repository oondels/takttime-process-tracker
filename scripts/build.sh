#!/bin/bash

# Obtém o diretório do script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Diretório raiz do projeto (um nível acima de scripts)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Muda para o diretório raiz do projeto
cd "$PROJECT_ROOT"

echo "============================================"
echo "  Takt-Time Process Tracker - Build Script"
echo "============================================"
echo ""
echo "📂 Diretório do projeto: $PROJECT_ROOT"
echo ""

# Verifica se PyInstaller está instalado
if ! command -v pyinstaller &> /dev/null
then
    echo "❌ PyInstaller não encontrado!"
    echo "📦 Instalando PyInstaller..."
    pip install pyinstaller
    if [ $? -ne 0 ]; then
        echo "❌ Erro ao instalar PyInstaller"
        exit 1
    fi
    echo "✅ PyInstaller instalado com sucesso!"
    echo ""
fi

# Limpa builds anteriores
echo "🧹 Limpando builds anteriores..."
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
pyinstaller scripts/takttime-tracker.spec --clean

# Verifica se a compilação foi bem-sucedida
if [ $? -eq 0 ]; then
    echo ""
    echo "============================================"
    echo "✅ Compilação concluída com sucesso!"
    echo "============================================"
    echo ""
    echo "📁 Executável criado em: dist/takttime-tracker/"
    echo "🚀 Para executar:"
    echo "   cd dist/takttime-tracker"
    echo "   ./takttime-tracker"
    echo ""
    
    # Cria arquivo README no diretório de distribuição
    cat > dist/takttime-tracker/README.txt << 'EOF'
===========================================
 Takt-Time Process Tracker
===========================================

📋 PRÉ-REQUISITOS:
------------------
1. Tesseract OCR instalado no sistema
   Ubuntu/Debian: sudo apt install tesseract-ocr
   
2. Modelo YOLO (train_2025.pt) no mesmo diretório

3. Arquivo config/config.json com as configurações


🚀 COMO EXECUTAR:
------------------
./takttime-tracker


⚙️ CONFIGURAÇÃO:
-----------------
1. Execute o aplicativo
2. Clique em "⚙️ Configurar"
3. Preencha os dados do dispositivo (obrigatório):
   - Número da Célula
   - Fábrica
   - Líder da Célula
4. Configure a rede WiFi (opcional)
5. Desbloqueie e configure dados técnicos (opcional):
   - Usuário: admin
   - Senha: dass@2025


📝 LOGS:
---------
Os logs são salvos em:
- logs/app_debug.log (interface gráfica)
- logs/main_debug.log (detecção de takt)


❓ PROBLEMAS:
-------------
- Erro no modelo: Verifique se train_2025.pt existe
- Erro MQTT: Verifique configurações técnicas e conexão de rede
- Erro OCR: Instale tesseract-ocr
- Erro ao iniciar: Execute no terminal para ver mensagens de erro


📧 SUPORTE:
-----------
Para problemas ou dúvidas, contate o suporte técnico.

EOF
    
    echo "📄 README criado em: dist/takttime-tracker/README.txt"
    echo ""
    
    # Copia o ícone para o diretório de distribuição
    echo "🎨 Copiando ícone..."
    cp assets/icon.png dist/takttime-tracker/
    
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
    
    echo "🖼️  Ícone e arquivo .desktop criados"
    echo ""
    echo "💡 Para adicionar ao menu de aplicativos do Linux:"
    echo "   1. Copie takttime-tracker.desktop para ~/.local/share/applications/"
    echo "   2. Edite o campo Exec= com o caminho absoluto do executável (se necessário)"
    echo "   3. Edite o campo Icon= com o caminho absoluto do ícone (se necessário)"
    echo "   4. Rode chmod +x ~/.local/share/applications/takttime-tracker.desktop"
    echo ""
else
    echo ""
    echo "============================================"
    echo "❌ Erro durante a compilação!"
    echo "============================================"
    echo ""
    echo "Verifique os erros acima e tente novamente."
    exit 1
fi
