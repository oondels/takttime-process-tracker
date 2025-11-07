#!/bin/bash

# Script para testar o executável compilado

echo "============================================"
echo "  Takt-Time Tracker - Test Script"
echo "============================================"
echo ""

# Verifica se o diretório dist existe
if [ ! -d "../dist/takttime-tracker" ]; then
    echo "❌ Erro: Diretório ../dist/takttime-tracker não encontrado!"
    echo ""
    echo "Por favor, compile o aplicativo primeiro:"
    echo "  cd scripts"
    echo "  ./build.sh"
    exit 1
fi

echo "✅ Diretório de distribuição encontrado"
echo ""

# Verifica arquivos necessários
echo "🔍 Verificando arquivos necessários..."
echo ""

files_ok=true

# Executável principal
if [ -f "../dist/takttime-tracker/takttime-tracker" ]; then
    echo "  ✅ takttime-tracker (executável)"
    
    # Verifica se é executável
    if [ -x "../dist/takttime-tracker/takttime-tracker" ]; then
        echo "     ✅ Permissões de execução OK"
    else
        echo "     ⚠️  Sem permissão de execução, corrigindo..."
        chmod +x ../dist/takttime-tracker/takttime-tracker
    fi
else
    echo "  ❌ takttime-tracker (executável) - NÃO ENCONTRADO"
    files_ok=false
fi

# Modelo YOLO
if [ -f "../dist/takttime-tracker/train_2025.pt" ]; then
    echo "  ✅ train_2025.pt (modelo YOLO)"
    
    # Verifica tamanho do modelo
    size=$(du -h ../dist/takttime-tracker/train_2025.pt | cut -f1)
    echo "     📊 Tamanho: $size"
else
    echo "  ⚠️  train_2025.pt (modelo YOLO) - NÃO ENCONTRADO"
    echo "     O aplicativo pode não funcionar sem o modelo"
fi

# Diretório de configuração
if [ -d "../dist/takttime-tracker/config" ]; then
    echo "  ✅ config/ (diretório)"
    
    if [ -f "../dist/takttime-tracker/config/config.json" ]; then
        echo "     ✅ config.json encontrado"
    else
        echo "     ⚠️  config.json não encontrado (será criado na primeira execução)"
    fi
else
    echo "  ⚠️  config/ (diretório) - NÃO ENCONTRADO"
fi

# README
if [ -f "../dist/takttime-tracker/README.txt" ]; then
    echo "  ✅ README.txt"
else
    echo "  ℹ️  README.txt - Não encontrado"
fi

echo ""

# Verifica dependências do sistema
echo "🔍 Verificando dependências do sistema..."
echo ""

deps_ok=true

# Tesseract
if command -v tesseract &> /dev/null; then
    version=$(tesseract --version | head -n1)
    echo "  ✅ Tesseract OCR instalado ($version)"
else
    echo "  ❌ Tesseract OCR NÃO INSTALADO"
    echo "     Instale com: sudo apt install tesseract-ocr"
    deps_ok=false
fi

# Qt5
if ldconfig -p | grep -q libQt5Core; then
    echo "  ✅ Bibliotecas Qt5 instaladas"
else
    echo "  ⚠️  Bibliotecas Qt5 podem estar ausentes"
    echo "     Instale com: sudo apt install libqt5core5a libqt5gui5 libqt5widgets5"
fi

echo ""
echo "============================================"

# Resumo
if [ "$files_ok" = true ] && [ "$deps_ok" = true ]; then
    echo "✅ Todos os pré-requisitos OK!"
    echo ""
    echo "🚀 Para testar o aplicativo:"
    echo "   cd ../dist/takttime-tracker/"
    echo "   ./takttime-tracker"
    echo ""
    
    # Oferecer para executar
    read -p "Deseja executar o aplicativo agora? (s/N) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        echo ""
        echo "🚀 Iniciando aplicativo..."
        echo "============================================"
        echo ""
        cd ../dist/takttime-tracker/
        ./takttime-tracker
    fi
else
    echo "⚠️  Alguns problemas foram encontrados"
    echo ""
    echo "Corrija os problemas acima antes de executar o aplicativo."
    echo ""
    
    if [ "$deps_ok" = false ]; then
        echo "📦 Para instalar dependências do sistema:"
        echo "   sudo apt install tesseract-ocr libqt5core5a libqt5gui5 libqt5widgets5"
        echo ""
    fi
    
    if [ "$files_ok" = false ]; then
        echo "🔨 Para recompilar o aplicativo:"
        echo "   cd scripts"
        echo "   ./build.sh"
        echo ""
    fi
    
    exit 1
fi
