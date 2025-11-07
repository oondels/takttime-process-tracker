# Scripts de Build

Este diretório contém os scripts e arquivos necessários para compilar o aplicativo Takt-Time Process Tracker.

## Arquivos

### Scripts Executáveis

- **`build.sh`** - Script principal de compilação
  - Verifica dependências
  - Limpa builds anteriores
  - Compila o aplicativo com PyInstaller
  - Cria README no diretório de distribuição

- **`test_build.sh`** - Script de teste do build
  - Verifica arquivos necessários
  - Testa dependências do sistema
  - Oferece opção de executar o aplicativo

### Arquivos de Configuração

- **`takttime-tracker.spec`** - Especificação do PyInstaller
  - Define arquivos a incluir
  - Configura hiddenimports
  - Especifica metadados necessários
  - Configura ícone e executável

- **`hook-aio_pika.py`** - Hook personalizado do PyInstaller
  - Coleta submódulos de aio_pika
  - Inclui metadados necessários
  - Resolve problemas de importação

## Uso

### Da raiz do projeto

```bash
# Compilar
./build.sh

# Testar
./test.sh
```

### Diretamente nesta pasta

```bash
cd scripts/

# Compilar
./build.sh

# Testar
./test_build.sh
```

## Estrutura de Caminhos

Os scripts usam caminhos relativos baseados na estrutura:

```
projeto/
├── scripts/          # Este diretório
│   ├── build.sh
│   ├── test_build.sh
│   ├── takttime-tracker.spec
│   └── hook-aio_pika.py
├── assets/           # Recursos (modelo, ícones)
├── config/           # Configurações
├── app.py            # Código principal
├── main.py
└── mqtt_manager.py
```

## Personalização

### Modificar o .spec

Para adicionar arquivos ou dependências:

```python
datas=[
    ('../assets/train_2025.pt', '.'),
    ('../meu_arquivo.txt', '.'),  # Adicione aqui
],
```

### Adicionar hiddenimports

```python
hiddenimports=[
    # ... existentes ...
    'minha_biblioteca',  # Adicione aqui
],
```

## Troubleshooting

### Build falha

1. Verifique se está executando da pasta correta
2. Confirme que PyInstaller está instalado
3. Verifique se `assets/train_2025.pt` existe

### Executável não funciona

1. Execute `./test_build.sh` para diagnóstico
2. Verifique dependências do sistema (Tesseract, Qt5)
3. Execute o binário direto do terminal para ver erros

## Notas

- Os scripts são projetados para Linux
- Para Windows/macOS, ajuste os comandos conforme necessário
- O hook personalizado resolve problemas específicos do aio_pika
