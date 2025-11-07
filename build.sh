#!/bin/bash

# Muda para o diretório do script
cd "$(dirname "$0")"

# Muda para a pasta scripts e executa o build
cd scripts
./build.sh "$@"