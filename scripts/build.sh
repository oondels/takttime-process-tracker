#!/bin/bash

# Script para compilar o aplicativo com PyInstaller

echo "============================================"
echo "  Takt-Time Process Tracker - Build Script"
echo "============================================"
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
rm -rf ../build/ ../dist/

# Verifica se o modelo existe
if [ ! -f "../assets/train_2025.pt" ]; then
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
pyinstaller takttime-tracker.spec --clean

# Verifica se a compilação foi bem-sucedida
if [ $? -eq 0 ]; then
    echo ""
    echo "============================================"
    echo "✅ Compilação concluída com sucesso!"
    echo "============================================"
    echo ""
    echo "📁 Executável criado em: ../dist/takttime-tracker/"
    echo "🚀 Para executar:"
    echo "   cd ../dist/takttime-tracker"
    echo "   ./takttime-tracker"
    echo ""
    
    # Cria arquivo README no diretório de distribuição
    cat > ../dist/takttime-tracker/README.txt << 'EOF'
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
   - Senha: change-me-before-use


📝 LOGS:
---------
Os logs são salvos em:
- app_debug.log (interface gráfica)
- main_debug.log (detecção de takt)


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
    
    echo "📄 README criado em: ../dist/takttime-tracker/README.txt"
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
