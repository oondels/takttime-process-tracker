# Takt-Time Process Tracker

Sistema distribuído para monitoramento de linha de produção baseado em **Takt-Time**, utilizando visão computacional e comunicação MQTT para sinalização física em tempo real.

## Índice

- [Visão Geral](#-visão-geral)
- [Arquitetura do Sistema](#-arquitetura-do-sistema)
- [Fluxo de Dados](#-fluxo-de-dados)
- [Componentes](#-componentes)
- [Instalação](#-instalação)
- [Configuração](#-configuração)
- [Uso](#-uso)
- [Tecnologias](#-tecnologias)

## Visão Geral

O sistema detecta automaticamente eventos de **Takt-Time** (padrão `00:00:00`) em telas de produção usando:

1. **Captura de Tela** → Detecção YOLO → OCR Tesseract
2. **Comunicação MQTT** → Envio de comandos para dispositivos
3. **ESP32** → Sinalização física (LEDs progressivos)

### Casos de Uso

- Monitoramento de linhas de produção
- Sinalização visual de metas de takt-time
- Rastreamento de ciclos de produção
- Alertas em tempo real para operadores

## Arquitetura do Sistema

```mermaid
graph TB

    subgraph Desktop_Application["Desktop Application"]
        UI[PyQt5 Interface]
        YOLO[YOLO Detector]
        OCR[Tesseract OCR]
        MQTT_PY[MQTT Client Python]
    end

    subgraph MQTT_Broker["MQTT Broker"]
        BROKER[RabbitMQ / Mosquitto]
    end

    subgraph ESP32_Device["ESP32 Device"]
        MQTT_ESP[MQTT Client ESP32]
        CTRL[Signalizer Controller]
        LED1[LED 1 - Nível 1]
        LED2[LED 2 - Nível 2]
        LED3[LED 3 - Nível 3]
        BUZZ[Buzzer]
    end

    UI --> YOLO
    YOLO --> OCR
    OCR --> MQTT_PY

    MQTT_PY -->|"takt/device/{id}"| BROKER

    BROKER -->|Commands| MQTT_ESP

    MQTT_ESP --> CTRL
    CTRL --> LED1
    CTRL --> LED2
    CTRL --> LED3
    CTRL --> BUZZ

    MQTT_ESP -->|"heartbeat/status"| BROKER
    BROKER -->|Telemetry| MQTT_PY

```

## Fluxo de Dados

### Fluxo Completo de Detecção

```mermaid
sequenceDiagram
    participant Screen as Tela Produção
    participant Desktop as Desktop App
    participant YOLO as YOLO Model
    participant OCR as Tesseract OCR
    participant MQTT as MQTT Broker
    participant ESP32 as ESP32
    participant LEDs as Sinalizadores
    
    loop A cada 500ms
        Desktop->>Screen: Captura tela (ImageGrab)
        Screen-->>Desktop: Screenshot
        Desktop->>YOLO: Detectar região takt
        YOLO-->>Desktop: Bounding box (conf>0.15)
        Desktop->>Desktop: Extract ROI + Upscale 2x
        Desktop->>OCR: Preprocessar + OCR
        OCR-->>Desktop: Texto extraído
        
        alt Padrão "00:00:00" detectado
            Desktop->>Desktop: Verificar status ESP32
            
            alt ESP32 Conectado (device_status[id]==True)
                Desktop->>Desktop: Incrementar takt_count (1→2→3)
                Desktop->>MQTT: Publicar JSON (QoS 1)
                Note over Desktop,MQTT: {"event":"takt","takt_count":2}
                
                MQTT->>ESP32: Encaminhar comando
                ESP32->>ESP32: Parse JSON (ArduinoJson)
                ESP32->>LEDs: Acionar nível correspondente
                
                alt takt_count == 3
                    Desktop->>Desktop: Agendar reset (3s)
                    Desktop->>Desktop: takt_count = 0
                end
            else ESP32 Desconectado
                Desktop->>Desktop: ⚠️ Bloquear envio
                Desktop->>Desktop: Log warning
                
                alt Cooldown expirado (>30s)
                    Desktop->>Desktop: Mostrar aviso na UI
                    Note over Desktop: Dialog não-bloqueante
                else Cooldown ativo (<30s)
                    Desktop->>Desktop: Skip notificação (apenas log)
                end
            end
            
            ESP32-->>MQTT: Heartbeat (a cada 30s)
            MQTT-->>Desktop: Atualizar status UI
            Note over Desktop: 🟢 ESP32 Online / 🔴 Offline
            
        else Timeout > 40s
            Desktop->>Desktop: Marcar tela offline
            Desktop->>Desktop: Pausar análise
        end
    end
```

### Topologia MQTT

```mermaid
graph LR

    subgraph MQTT_Topics["Tópicos MQTT"]
        CMD["takt/device/{id}"]
        STATUS["takt/device/{id}/status"]
        HEART["takt/device/{id}/heartbeat"]
    end
    
    PY[Python App] -->|"Publish Commands"| CMD
    CMD -->|"Subscribe"| ESP[ESP32]
    
    ESP -->|"LWT: offline"| STATUS
    ESP -->|"Publish: online"| STATUS
    STATUS -->|"Subscribe"| PY
    
    ESP -->|"Publish Telemetry"| HEART
    HEART -->|"Subscribe"| PY
```

## Componentes

### 1. Aplicação Desktop (Python)

**Arquitetura Multi-Thread:**

```
┌─────────────────┐
│   Main Thread   │  ← Interface PyQt5
└────────┬────────┘
         │
    ┌────┴─────┬──────────────────┐
    │          │                  │
┌───▼──────┐ ┌─▼──────────────┐ ┌─▼─────────────┐
│ Init     │ │ AsyncWorker    │ │ Timer Thread  │
│ Worker   │ │ (Event Loop)   │ │ (Status Check)│
└──────────┘ └────────────────┘ └───────────────┘
```

**Pipeline de Detecção:**

```python
ImageGrab.grab() 
    ↓
YOLO Detection (conf=0.15)
    ↓
extract_roi() → Padding + Upscaling 2x
    ↓
preprocess_for_ocr() → Grayscale + Bilateral + Otsu
    ↓
Tesseract OCR (whitelist=0-9:A-Z)
    ↓
Pattern Matching: "00:00:00"
```

**Otimizações Implementadas:**

- **Bilateral Filter**: Reduz ruído preservando bordas
- **Otsu Threshold**: Binarização adaptativa automática
- **Upscaling 2x**: Melhora legibilidade de textos pequenos
- **Confidence 0.15**: Detecta até regiões com baixa certeza
- **Debounce 2s**: Evita mensagens MQTT duplicadas
- **Verificação ESP32**: Checa conexão antes de enviar (economiza banda)
- **Cooldown de Avisos**: 30s entre notificações (previne spam de dialogs)

### 2. Sistema MQTT

**Mensagem de Comando Padrão (JSON):**

```json
{
  "event": "takt",
  "message": "Takt detectado",
  "id": "cost-{factory}-{cell}",
  "timestamp": "2025-11-04 14:32:15",
  "takt_count": etapa -> [0,1,2,3]
}
```

**Mensagem de Reset Manual (JSON):**

Mensagem enviada quando botão de reset é apertado

```json
{
  "event": "device_config",
  "message": "update_config",
  "takt_count": 0
}
```

**Mensagem de Atualização de Device ID (JSON):**

Enviada pelo dialog "Editar Takt" → "Atualiza conexao disp. Takt"

```json
{
  "event": "device_config",
  "message": "update_device_id",
  "factory": "3",
  "cell_number": "3324",
  "device_id": "cost-3-3324"
}
```

**Heartbeat ESP32 (Telemetria):**

```json
{
  "device_id": "TAKT_DEVICE-cost-2-2408-abc123",
  "timestamp": 123456,
  "uptime": 3600,
  "wifi_rssi": -65,
  "free_heap": 245760
}
```

**Last Will Testament (LWT):**
- Broker publica `"offline"` automaticamente se ESP32 desconectar
- Python monitora e atualiza UI (🔴 ESP32: Desconectado)

### 3. ESP32 Embarcado

**Processamento de Comandos:**

```cpp
void processarComando(int comando) {
    NivelSinalizacao nivel = static_cast<NivelSinalizacao>(comando);
    
    switch (nivel) {
        case NIVEL_1: // takt_count == 1
            sinalizadorController.setNivel(NIVEL_1);
            break;
        case NIVEL_2: // takt_count == 2
            sinalizadorController.setNivel(NIVEL_2);
            break;
        case NIVEL_3: // takt_count == 3
            sinalizadorController.setNivel(NIVEL_3);
            break;
    }
}
```

**Recursos:**
- Reconexão automática (5s retry)
- Heartbeat a cada 30s
- Buffer MQTT 512 bytes
- Parsing JSON automático

## Instalação

### Requisitos

- **Python**: 3.8+
- **Tesseract OCR**: 5.x
- **PlatformIO**: Para ESP32 (opcional)

### Opção 1: Executável Compilado (Recomendado)

Para usuários finais que não precisam modificar o código:

1. **Baixar o executável** do release mais recente
2. **Extrair o arquivo** `takttime-tracker-linux.tar.gz`:
   ```bash
   tar -xzf takttime-tracker-linux.tar.gz
   cd takttime-tracker/
   ```
3. **Instalar Tesseract OCR** (dependência do sistema):
   ```bash
   # Ubuntu/Debian
   sudo apt install tesseract-ocr tesseract-ocr-por -y
   ```
4. **Executar**:
   ```bash
   ./takttime-tracker
   ```

### Opção 2: Executar do Código Fonte

Para desenvolvedores ou personalização:

### Windows

1. **Instalar Tesseract OCR**
   - Download: [Tesseract Windows](https://github.com/UB-Mannheim/tesseract/wiki)
   - Adicionar ao PATH: `C:\Program Files\Tesseract-OCR`

2. **Instalar dependências Python**
   ```bash
   pip install -r requirements-app.txt
   ```

3. **Executar aplicação**
   ```bash
   python app.py
   ```

### Linux

#### Preparação do Ambiente

1. **Instalar Git**
   ```bash
   sudo apt update
   sudo apt install git -y
   ```

2. **Instalar Python 3.12 com pyenv** (recomendado)
   
   **Instalar dependências de build:**
   ```bash
   sudo apt update
   sudo apt install -y software-properties-common build-essential curl git \
     libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev \
     libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev
   ```

   **Instalar pyenv:**
   ```bash
   curl https://pyenv.run | bash
   ```

   **Configurar shell (bash/zsh):**
   ```bash
   # Para bash
   echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
   echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
   echo 'eval "$(pyenv init --path)"' >> ~/.bashrc
   echo 'eval "$(pyenv init -)"' >> ~/.bashrc
   source ~/.bashrc
   
   # Para zsh
   echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
   echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
   echo 'eval "$(pyenv init --path)"' >> ~/.zshrc
   echo 'eval "$(pyenv init -)"' >> ~/.zshrc
   source ~/.zshrc
   ```

   **Instalar e configurar Python 3.12:**
   ```bash
   pyenv install 3.12.7
   pyenv global 3.12.7   # ou 'pyenv local 3.12.7' no diretório do projeto
   python -V  # Verificar versão
   ```

3. **Criar ambiente virtual**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

#### Instalação da Aplicação

1. **Instalar Tesseract OCR**
   ```bash
   # Ubuntu/Debian
   sudo apt install tesseract-ocr tesseract-ocr-por -y
   
   # Arch Linux
   sudo pacman -S tesseract tesseract-data-por
   ```

2. **Instalar dependências Python**
   ```bash
   pip install -r requirements.txt
   ```

3. **Executar aplicação**
   ```bash
   python app.py
   ```

### Opção 3: Compilar o Executável

Para criar um executável autônomo:

1. **Instalar dependências** (inclui PyInstaller):

   ```bash
   pip install -r requirements.txt
   ```

2. **Executar o script de build**:

   ```bash
   ./build.sh
   ```

3. **O executável estará em** `dist/takttime-tracker/`

📖 Para instruções detalhadas de compilação, consulte [BUILD_INSTRUCTIONS.md](BUILD_INSTRUCTIONS.md)

### ESP32 (PlatformIO)

```bash
cd /path/to/takt-time-receptor
pio run --target upload
pio device monitor
```

## Configuração

### Arquivo local `config/config.json`

Use `config/config.example.json` como base e mantenha `config/config.json` apenas na máquina local:

```json
{
    "device": {
        "cell_number": "0000",
        "factory": "00",
        "cell_leader": "Nome do lider"
    },
    "network": {
        "wifi_ssid": "WIFI_NAME",
        "wifi_pass": "WIFI_PASSWORD"
    },
    "tech": {
        "mqtt_host": "broker-host-or-ip",
        "mqtt_user": "mqtt-user",
        "mqtt_pass": "mqtt-password",
        "model_path": "./assets/train_2025.pt"
    }
}
```

### Variáveis de ambiente locais

Você pode definir credenciais sensíveis em `.env` local com base em `.env.example`:

```env
AMQP_URL=amqp://user:password@broker-host/
TECH_CONFIG_USER=admin
TECH_CONFIG_PASS=change-me-before-use
```

### Interface de Configuração

1. Clicar em **"Configurar"** na aplicação
2. **Configurações Básicas**: 
   - Líder da Célula (editável diretamente)
3. **Configurações Técnicas**: Requer autenticação
   - Usuário: variável `TECH_CONFIG_USER` (padrão `admin`)
   - Senha: variável `TECH_CONFIG_PASS`
   - MQTT Host, Usuário, Senha
   - Caminho do modelo YOLO

**⚠️ Nota:** Os campos de Célula, Fábrica e WiFi não são editáveis no dialog de configurações. Use o dialog **"Editar Takt"** para atualizar remotamente o device_id do ESP32.

### Atualização do Device ID

Para alterar a identificação do dispositivo Takt (célula e fábrica):

1. **Abrir**: Botão **"Editar Takt"** na interface principal
2. **Seção**: "Conexão Takt Receptor"
3. **Editar**: Campos de Fábrica e Célula
4. **Autenticar**: Credenciais técnicas definidas localmente via ambiente
5. **Aplicar**: Botão **"🔗 Atualiza conexao disp. Takt"**
6. **Resultado**: ESP32 reconfigura automaticamente + config local atualizado

### Configuração ESP32

Editar `src/main.cpp`:

```cpp
const char *DEVICE_ID = "cost-00-0000";
const char *SSID = "WIFI_NAME";
const char *PASSWORD = "WIFI_PASSWORD";
const char *MQTT_SERVER = "broker-host-or-ip";
```

## Uso

### Iniciar Monitoramento

1. Abrir `app.py`
2. Verificar configurações
3. Clicar em **"▶ Iniciar Análise"**
4. Sistema aguarda detecção de tela takt

### Editar Configurações do Takt

#### Atualização Remota do Device ID (ESP32)

A aplicação permite atualizar remotamente o ID do dispositivo ESP32 através do dialog "Editar Takt":

1. **Abrir Dialog**: Clicar em **"Editar Takt"** na interface principal
2. **Seção "Conexão Takt Receptor"**:
   - Exibe o **Device ID atual** (formato: `cost-{factory}-{cell}`)
   - Campos editáveis para **Fábrica** e **Célula**
3. **Autenticação Requerida**:
   - Usuário: variável `TECH_CONFIG_USER`
   - Senha: variável `TECH_CONFIG_PASS`
4. **Confirmação**: Preview do novo device_id antes de aplicar
5. **Envio Automático**:
   - Comando MQTT enviado para o ESP32 **antes** de salvar localmente
   - ESP32 recebe novo device_id e se reconfigura automaticamente
   - Configuração local atualizada após confirmação
   - Interface atualizada automaticamente

**Payload MQTT enviado:**

```json
{
  "event": "device_config",
  "message": "update_device_id",
  "factory": "3",
  "cell_number": "3324",
  "device_id": "cost-3-3324"
}
```

**Comportamento Inteligente:**

- Sistema detecta automaticamente que novo device_id ainda não existe
- Usa o device_id **antigo registrado** para enviar o comando
- ESP32 recebe no tópico onde está inscrito (`takt/device/{id_antigo}`)
- Após reconfiguração, ESP32 passa a usar novo device_id
- ⚠️ **Importante**: Considere reiniciar a aplicação após atualização para reconectar com novo ID

#### Reset Manual do Contador

1. Clicar em **"🔄 Editar Estágio Contador"**
2. Confirmar reset para 0
3. Comando enviado via MQTT instantaneamente

### Estados do Sistema

| Estado | Descrição |
|--------|-----------|
| 🟢 **Takt Detectado** | Tela takt visível e sendo analisada |
| 🔴 **Tela Offline** | Timeout >40s sem detecção |
| 🟡 **Aguardando** | Sistema pronto, aguardando tela |
| � **ESP32 Conectado** | Dispositivo respondendo heartbeat |
| 🔴 **ESP32 Desconectado** | Sem heartbeat ou status offline |
| ⚠️ **ESP32 OFF (Takt OK)** | Takt detectado mas mensagem não enviada |

### Comportamento de Proteção

**Sistema de Verificação de Conexão:**

```
Takt Detectado
    ↓
Verificar device_status[ESP32_ID]
    ↓
┌─────────────────────┐
│   ESP32 Conectado?  │
└──────┬──────────┬───┘
       │          │
      SIM        NÃO
       │          │
       ↓          ↓
  Enviar MQTT   Bloquear
  ✅ Sucesso    ⚠️ Skip
       │          │
       └──────────┘
            ↓
    Análise Continua
```

**Sistema de Cooldown de Avisos:**

- **Primeira detecção com ESP32 OFF**: Mostra dialog de aviso
- **Detecções subsequentes < 30s**: Apenas log (silencioso)
- **Após 30 segundos**: Mostra novo aviso se problema persistir
- **Interface permanece responsiva**: Dialogs não-bloqueantes
- **Análise continua rodando**: Não interrompe o monitoramento

### Logs

- **App Desktop**: `logs/app_debug.log` e `logs/main_debug.log`
- **ESP32**: Monitor serial PlatformIO

## Tecnologias

| Componente | Tecnologia | Versão | Propósito |
|------------|-----------|--------|-----------|
| **Desktop** | Python | 3.8+ | Runtime principal |
| | PyQt5 | 5.15+ | Interface gráfica |
| | Ultralytics YOLO | 8.x | Detecção de objetos |
| | Tesseract OCR | 5.x | Reconhecimento de texto |
| | OpenCV | 4.x | Processamento de imagem |
| | paho-mqtt | 1.6+ | Cliente MQTT Python |
| **Embarcado** | ESP32 | - | Microcontrolador |
| | PlatformIO | - | Build system |
| | PubSubClient | 2.8+ | Cliente MQTT Arduino |
| | ArduinoJson | 6.x | Parser JSON embarcado |
| **Infraestrutura** | RabbitMQ/Mosquitto | 3.x | Broker MQTT |

## Performance

- **Detecção**: ~500ms por frame (depende da GPU)
- **Heartbeat ESP32**: 30s (reduz overhead de rede)
- **Debounce MQTT**: 2s (evita spam de comandos)
- **Cooldown de Avisos**: 30s (previne dialogs repetitivos)
- **Buffer MQTT**: 512 bytes (suficiente para JSON)
- **Timeout takt**: 40s (balanceado para falsos negativos)
- **Verificação ESP32**: Tempo real via device_status (sem overhead)
- **QoS Comandos**: 1 (at least once - garantia de entrega)
- **QoS Heartbeat**: 0 (at most once - telemetria)

## Segurança e Confiabilidade

- Configurações técnicas protegidas por autenticação
- Credenciais MQTT armazenadas em `config.json`
- Comunicação MQTT sem TLS (ambiente interno)
- LWT garante detecção de desconexões
- **Verificação de conexão antes de enviar** (economiza banda)
- **Sistema de cooldown** (previne spam de avisos)
- **Reconexão automática** do MQTT em caso de queda
- **Validação de device_status** em tempo real

## Troubleshooting

### Desktop não detecta tela

1. Verificar se YOLO está treinado para sua tela
2. Ajustar confidence threshold em `main.py`
3. Verificar logs: `logs/main_debug.log`

### ESP32 não conecta

1. Verificar credenciais WiFi
2. Testar conectividade com o broker configurado: `ping <broker-host>`
3. Monitor serial: `pio device monitor`
4. Verificar se heartbeat está sendo enviado (a cada 30s)
5. Checar Last Will Testament (LWT) no broker

### MQTT não comunica

1. Verificar broker rodando: `sudo systemctl status mosquitto`
2. Testar com mosquitto_pub/sub
3. Verificar firewall: porta 1883
4. Checar credenciais no `config.json`

### Mensagens não são enviadas

1. **Verificar status do ESP32 na UI**: 🟢 = Conectado / 🔴 = Desconectado
2. **Logs**: Buscar por `"ESP32 NÃO está conectado"` em `logs/main_debug.log`
3. **Heartbeat**: ESP32 deve enviar heartbeat a cada 30s
4. **device_status**: Verificar se `connection.device_status[id]` está `True`
5. **Last Will Testament**: Confirmar se ESP32 publicou status "online"

### Atualização de Device ID não funciona

**Problema:** ESP32 não recebe comando de atualização

**Soluções:**

1. **Verificar conexão MQTT**:
   - ESP32 deve estar 🟢 **Conectado** antes de enviar
   - Análise deve estar rodando (worker thread ativa)

2. **Logs detalhados**:
   ```bash
   tail -f logs/app_debug.log | grep "device_id"
   ```
   - Procure por: `"Enviando atualização de device_id via MQTT"`
   - Procure por: `"⚠️ Device ID não encontrado"` (indica fallback correto)

3. **Verificar tópico MQTT**:
   - Sistema deve usar device_id **antigo** automaticamente
   - ESP32 recebe em `takt/device/{id_antigo}`

4. **Reiniciar aplicação**:
   - Após atualização bem-sucedida, reinicie para reconectar com novo ID
   - Novo device_id será carregado de `config.json`

5. **Confirmar ESP32 suporta comando**:
   - Firmware ESP32 deve processar `"message": "update_device_id"`
   - Verificar se ESP32 atualiza seus tópicos MQTT após receber

### Spam de avisos de ESP32 desconectado

**Problema resolvido na v2.0+**

- Sistema implementa cooldown de 30s entre avisos
- Apenas 1 dialog mostrado a cada 30 segundos
- Logs continuam registrando todas as tentativas
- UI permanece responsiva durante problema

### Timeout de tela aumentado

O timeout padrão foi aumentado de 6s para 40s para:

- Reduzir falsos positivos
- Permitir momentos de transição na tela
- Melhorar estabilidade do sistema
- Evitar interrupções desnecessárias

---

## 📦 Compilando o Aplicativo

### Estrutura do Projeto

```
takttime-process-tracker/
├── app.py                  # Interface gráfica PyQt5
├── main.py                 # Lógica de detecção de takt
├── mqtt_manager.py         # Gerenciador MQTT
├── requirements.txt        # Dependências Python
├── assets/                 # Recursos do projeto
│   ├── train_2025.pt      # Modelo YOLO
│   ├── icon.png           # Ícone do aplicativo
│   └── icon.ico           # Ícone Windows
├── scripts/                # Scripts de build
│   ├── build.sh           # Script de compilação
│   ├── test_build.sh      # Script de teste
│   ├── hook-aio_pika.py   # Hook PyInstaller
│   └── takttime-tracker.spec  # Especificação PyInstaller
├── config/                 # Configurações
└── server/                 # Servidor TypeScript (opcional)
```

### Pré-requisitos para Build

#### Ubuntu/Debian

```bash
sudo apt update
sudo apt install -y tesseract-ocr python3-dev build-essential
```

#### Fedora/RHEL

```bash
sudo dnf install -y tesseract tesseract-langpack-por python3-devel gcc
```

### Dependências Python

```bash
pip install -r requirements.txt
```

O PyInstaller já está incluído nas dependências.

### Compilar o Executável

#### Método Automático (Recomendado)

```bash
cd scripts/
./build.sh
```

O script irá:
1. ✅ Verificar se PyInstaller está instalado
2. ✅ Limpar builds anteriores
3. ✅ Verificar arquivos necessários (modelo, tesseract)
4. ✅ Compilar o aplicativo
5. ✅ Criar README no diretório de distribuição

#### Método Manual

```bash
cd scripts/
# Limpar builds anteriores
rm -rf ../build/ ../dist/

# Compilar com PyInstaller
pyinstaller takttime-tracker.spec --clean
```

### Estrutura de Saída

Após a compilação:

```
dist/takttime-tracker/
├── takttime-tracker          # Executável principal

## Guia Rápido (Informações adicionais)

As seções abaixo reúnem informações práticas que complementam o conteúdo acima.

**Requisitos do Sistema (Linux)**:
- Python 3.8+ (recomendado 3.10/3.12)
- Tesseract OCR (binário em `/usr/bin/tesseract` ou caminho equivalente)
- Dependências do sistema para OpenCV/torch (drivers NVIDIA se for usar GPU)

**Instalação Rápida (Linux)**

```bash
# No diretório do projeto
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Instale o Tesseract (Debian/Ubuntu)
sudo apt update
sudo apt install -y tesseract-ocr libgl1

# Ajuste se o binário tesseract estiver em local diferente
export TESSERACT_CMD=/usr/bin/tesseract
```

**Executando a aplicação (desenvolvimento)**

```bash
# Ative o virtualenv
source .venv/bin/activate
# Execute a interface gráfica (PyQt5)
python app.py
```

**Executável (produção)**

Se você usou `./build.sh` ou o processo de build, o executável gerado está em `dist/takttime-tracker/`.

```bash
cd dist/takttime-tracker/
./takttime-tracker
```

**Arquivo de Configuração**

- O arquivo principal de configuração é `config/config.json`.
- Atenção: ele contém credenciais MQTT e outras informações sensíveis. Não o publique em repositórios públicos.
- Preferível usar mecanismos de segredos em produção (variáveis de ambiente, vaults) e manter um exemplo `config.example.json` sem credenciais.

**Variáveis de Ambiente úteis**

- `AMQP_URL` : quando definido, `main.py` usa esta URL para conexão AMQP/RabbitMQ.
- `TESSERACT_CMD` : caso o binário do tesseract não esteja em `/usr/bin/tesseract`, exporte esse caminho antes de iniciar.

**Rodando apenas o detector (headless / debug)**

O módulo `main.py` contém o loop de detecção e pode ser executado diretamente para testes. Ele espera receber um objeto `MQTTManager` quando usado junto com a UI; isoladamente ele pode ser usado para validar o modelo e OCR:

```bash
# Execução de teste (pode requerer ajustes de ambiente)
python main.py
```

**Build / Compilação**

- O script principal de build é `scripts/build.sh`. Ele invoca o PyInstaller com a spec apropriada.
- Antes de rodar o build, certifique-se de que `tesseract` está instalado no sistema e que o modelo (`assets/train_2025.pt`) está acessível.

**Segurança**

- `config/config.example.json` e `.env.example` são apenas modelos. Não versione `config/config.json` nem `.env` com credenciais reais.
- A comunicação MQTT no projeto atual não usa TLS por padrão — considere habilitar TLS/SSL no broker em ambientes sensíveis.

**Testes**

- Não há uma suíte de testes automatizados incluída neste repositório. Para validar mudanças, rode manualmente o aplicativo com o `--verbose` e verifique `logs/main_debug.log` e `logs/app_debug.log`.

**Contribuição e Contato**

- Abra issues para bugs e solicitações de features no repositório.
- Para contribuições via PR, crie uma branch com mudanças pequenas e documente o que foi alterado.

**Licença**

- Nenhuma licença foi definida no repositório. Se este projeto for distribuído, adicione um arquivo `LICENSE` com a licença desejada (por exemplo MIT) e atualize este README.

---

Se quiser, posso também:
- Adicionar um `config.example.json` sem credenciais
- Criar um `LICENSE` (ex.: MIT)
- Gerar um pequeno `quick_start.sh` que automatiza a criação do virtualenv e instalação

├── train_2025.pt             # Modelo YOLO
├── config/                   # Configurações
│   └── config.json          # Criado na primeira execução
├── README.txt                # Instruções de uso
└── _internal/                # Bibliotecas Python empacotadas
    ├── PyQt5/
    ├── cv2/
    ├── torch/
    ├── ultralytics/
    └── ...
```

### Executar o Aplicativo Compilado

```bash
cd ../dist/takttime-tracker/
./takttime-tracker
```

### Testar o Build

```bash
cd scripts/
./test_build.sh
```

Este script verifica:
- ✅ Executável criado e com permissões corretas
- ✅ Modelo YOLO presente
- ✅ Diretório de configuração
- ✅ Dependências do sistema (Tesseract, Qt5)

### Distribuir o Aplicativo

#### Criar Pacote Compactado

```bash
cd dist/
tar -czf takttime-tracker-linux-v1.0.tar.gz takttime-tracker/
```

#### O que Incluir na Distribuição

- ✅ Todo o diretório `takttime-tracker/`
- ✅ Instruções de instalação do Tesseract
- ✅ Requisitos de sistema (Linux x86_64)
- ✅ Configuração inicial necessária

### Personalizações

#### Adicionar Ícone Personalizado

1. **Criar/obter ícone** (256x256px PNG recomendado)
2. **Salvar em** `assets/icon.png`
3. **Recompilar** com `./build.sh`

#### Converter PNG para ICO (Windows)

```bash
convert assets/icon.png -define icon:auto-resize=256,128,64,48,32,16 assets/icon.ico
```

#### Recursos de Ícones Gratuitos

- [Flaticon](https://www.flaticon.com/) - Procure por "stopwatch", "production", "timer"
- [Font Awesome](https://fontawesome.com/) - Ícones vetoriais
- [IconFinder](https://www.iconfinder.com/) - Filtro por licença grátis

#### Sugestões de Design

Para aplicativo de monitoramento de takt-time:
- **Cores**: Verde (produção), Amarelo (atenção), Vermelho (alerta)
- **Símbolo**: Cronômetro, engrenagem, linha de produção
- **Estilo**: Moderno, flat design, alta legibilidade

### Problemas Comuns no Build

#### "ModuleNotFoundError" ao executar

**Causa:** Dependência não incluída automaticamente.

**Solução:** Adicione em `scripts/takttime-tracker.spec`:

```python
hiddenimports=[
    # ... existentes ...
    'modulo_faltante',
],
```

#### "FileNotFoundError: train_2025.pt"

**Causa:** Modelo não encontrado.

**Solução:**
- Verifique se `assets/train_2025.pt` existe
- Confirme que está listado em `datas` no `.spec`

#### Aplicativo não inicia

**Causa:** Erro sendo suprimido.

**Solução:** Execute no terminal para ver erros:

```bash
cd dist/takttime-tracker/
./takttime-tracker
```

#### Erro: "libQt5Core.so.5: cannot open shared object file"

**Causa:** Bibliotecas Qt não instaladas.

**Solução:**

```bash
sudo apt install libqt5core5a libqt5gui5 libqt5widgets5
```

#### Build muito grande

**Soluções:**
- Use UPX para compressão (já habilitado)
- Remova dependências não usadas
- Exclua módulos específicos:

```bash
pyinstaller takttime-tracker.spec --exclude-module matplotlib
```

### Tamanho Esperado do Build

- **Executável**: ~500KB
- **Bibliotecas (_internal/)**: ~1.5-2GB (PyTorch, OpenCV)
- **Modelo YOLO**: ~6-50MB
- **Total**: ~1.5-2.5GB

### Compatibilidade

O executável é específico para:
- **OS**: Linux
- **Arquitetura**: x86_64 (AMD64)
- **Distribuição**: Maioria das distribuições modernas

Para outros sistemas:
- **Windows**: Compile no Windows
- **macOS**: Compile no macOS

### Otimizações

#### Reduzir Tamanho

```bash
# Excluir módulos não usados
pyinstaller takttime-tracker.spec --exclude-module tkinter
```

#### Modo GUI Puro (sem console)

Edite `scripts/takttime-tracker.spec`:

```python
console=False,  # Mude para False
```

**⚠️ Atenção**: Sem console, logs não aparecerão.

---


