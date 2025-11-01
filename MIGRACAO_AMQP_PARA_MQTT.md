# 📘 Guia de Migração: AMQP para MQTT

## 🎯 Objetivo
Migrar o sistema de mensageria de **AMQP (porta 5672)** para **MQTT (porta 1883)** para comunicação direta com ESP32 e melhor compatibilidade IoT.

## 📊 Comparação: AMQP vs MQTT

| Aspecto | AMQP (atual) | MQTT (novo) |
|---------|--------------|-------------|
| **Protocolo** | Advanced Message Queuing Protocol | Message Queuing Telemetry Transport |
| **Porta** | 5672 | **1883** |
| **Biblioteca** | aio-pika | **asyncio-mqtt** |
| **Overhead** | Alto | **Baixo** |
| **ESP32** | ❌ Não suportado | ✅ **Suportado** |
| **Complexidade** | Alta | **Baixa** |

---

## 📦 Passo 1: Instalar Biblioteca MQTT

### 1.1 Atualizar requirements-app.txt

**Antes:**
```txt
# Mensageria AMQP/RabbitMQ
aio-pika>=9.3.0
```

**Depois:**
```txt
# Mensageria MQTT/RabbitMQ
asyncio-mqtt==0.16.2
```

### 1.2 Instalar

```bash
pip install asyncio-mqtt
```

✅ **Status**: Biblioteca já instalada!

---

## ⚙️ Passo 2: Atualizar config.json

### 2.1 Estrutura Antiga (AMQP)

```json
{
  "device": {
    "cell_number": "cost-2-2408",
    "factory": "Fabrica X",
    "cell_leader": "João"
  },
  "network": {
    "wifi_ssid": "MinhaRede",
    "wifi_pass": "senha123"
  },
  "tech": {
    "amqp_host": "amqp://dass:pHUWphISTl7r_Geis@10.100.1.43/",
    "amqp_user": "",
    "amqp_pass": "",
    "model_path": "./train_2025.pt"
  }
}
```

### 2.2 Nova Estrutura (MQTT)

```json
{
  "device": {
    "cell_number": "cost-2-2408",
    "factory": "Fabrica X",
    "cell_leader": "João"
  },
  "network": {
    "wifi_ssid": "MinhaRede",
    "wifi_pass": "senha123"
  },
  "tech": {
    "mqtt_broker": "10.100.1.43",
    "mqtt_port": 1883,
    "mqtt_user": "dass",
    "mqtt_pass": "pHUWphISTl7r_Geis",
    "model_path": "./train_2025.pt"
  }
}
```

### 2.3 Aplicar Mudança

```bash
# Editar manualmente o arquivo
nano config/config.json

# OU usar sed
sed -i 's/"amqp_host"/"mqtt_broker"/g' config/config.json
sed -i 's/"amqp_user"/"mqtt_user"/g' config/config.json
sed -i 's/"amqp_pass"/"mqtt_pass"/g' config/config.json
```

---

## 🔧 Passo 3: Refatorar main.py

### 3.1 Imports (linha 1-13)

**Antes:**
```python
import os
import aio_pika
import asyncio
```

**Depois:**
```python
import os
import asyncio_mqtt as aiomqtt
import asyncio
```

---

### 3.2 Configuração DEFAULT (linha 32-42)

**Antes:**
```python
return {
    "device": {"cell_number": "", "factory": "", "cell_leader": ""},
    "network": {"wifi_ssid": "", "wifi_pass": ""},
    "tech": {"amqp_host": "", "amqp_user": "", "amqp_pass": "", "model_path": "./train_2025.pt"}
}
```

**Depois:**
```python
return {
    "device": {"cell_number": "", "factory": "", "cell_leader": ""},
    "network": {"wifi_ssid": "", "wifi_pass": ""},
    "tech": {
        "mqtt_broker": "",
        "mqtt_port": 1883,
        "mqtt_user": "",
        "mqtt_pass": "",
        "model_path": "./train_2025.pt"
    }
}
```

---

### 3.3 Variáveis de Configuração (linha 57-67)

**Antes:**
```python
# Configurações AMQP - prioriza config.json, depois .env, depois valores padrão
AMQP_URL = tech_config.get("amqp_host") or os.getenv("AMQP_URL", "amqp://dass:pHUWphISTl7r_Geis@10.100.1.43/")
AMQP_EXCHANGE = "amq.topic"
DEVICE_ID = device_config.get("cell_number") or os.getenv("DEVICE_ID", "cost-2-2408")
ROUTING_KEY = f"takt.device.{DEVICE_ID}"

pytesseract.pytesseract.tesseract_cmd = r"/usr/bin/tesseract"
MODEL_PATH = tech_config.get("model_path") or "./train_2025.pt"

logger.info(f"=== Configuração Inicial ===")
logger.info(f"AMQP_URL: {AMQP_URL}")
logger.info(f"DEVICE_ID: {DEVICE_ID}")
logger.info(f"ROUTING_KEY: {ROUTING_KEY}")
logger.info(f"MODEL_PATH: {MODEL_PATH}")
logger.info(f"==========================")
```

**Depois:**
```python
# Configurações MQTT - prioriza config.json, depois .env, depois valores padrão
MQTT_BROKER = tech_config.get("mqtt_broker") or os.getenv("MQTT_BROKER", "10.100.1.43")
MQTT_PORT = tech_config.get("mqtt_port", 1883)
MQTT_USER = tech_config.get("mqtt_user") or os.getenv("MQTT_USER", "dass")
MQTT_PASS = tech_config.get("mqtt_pass") or os.getenv("MQTT_PASS", "pHUWphISTl7r_Geis")
DEVICE_ID = device_config.get("cell_number") or os.getenv("DEVICE_ID", "cost-2-2408")
MQTT_TOPIC = f"takt/device/{DEVICE_ID}"

pytesseract.pytesseract.tesseract_cmd = r"/usr/bin/tesseract"
MODEL_PATH = tech_config.get("model_path") or "./train_2025.pt"

logger.info(f"=== Configuração Inicial ===")
logger.info(f"MQTT_BROKER: {MQTT_BROKER}:{MQTT_PORT}")
logger.info(f"MQTT_USER: {MQTT_USER}")
logger.info(f"DEVICE_ID: {DEVICE_ID}")
logger.info(f"MQTT_TOPIC: {MQTT_TOPIC}")
logger.info(f"MODEL_PATH: {MODEL_PATH}")
logger.info(f"==========================")
```

---

### 3.4 Função send_message() (linha 121-144)

**Antes:**
```python
async def send_message(
    channel: aio_pika.Channel,
    routing_key: str,
    message_body: dict,
    on_event: Optional[Callable[[str, Any], None]] = None,
):
    """
    Publish a message to the RabbitMQ exchange.
    """
    try:
        message = aio_pika.Message(
            body=json.dumps(message_body).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        exchange = await channel.get_exchange("amq.topic")
        await exchange.publish(message, routing_key=routing_key)
        logger.info(f"✓ Mensagem publicada em '{routing_key}': {message_body}")

        if on_event:
            on_event("message_sent", message_body)
    except Exception as e:
        logger.error(f"✗ Erro ao enviar mensagem: {e}", exc_info=True)
        if on_event:
            on_event("message_error", {"error": str(e)})
```

**Depois:**
```python
async def send_message(
    client: aiomqtt.Client,
    topic: str,
    message_body: dict,
    on_event: Optional[Callable[[str, Any], None]] = None,
):
    """
    Publica mensagem via MQTT no RabbitMQ.
    """
    try:
        payload = json.dumps(message_body)
        await client.publish(topic, payload=payload, qos=1, retain=False)
        logger.info(f"✓ Mensagem MQTT publicada em '{topic}': {message_body}")

        if on_event:
            on_event("message_sent", message_body)
    except aiomqtt.MqttError as e:
        logger.error(f"✗✗✗ ERRO MQTT: {e}")
        if on_event:
            on_event("message_error", {"error": f"Erro MQTT: {e}"})
    except ConnectionError as e:
        logger.error(f"✗✗✗ CONEXÃO PERDIDA: {e}")
        if on_event:
            on_event("message_error", {"error": "Conexão MQTT perdida"})
    except Exception as e:
        logger.error(f"✗✗✗ ERRO DESCONHECIDO: {e}", exc_info=True)
        if on_event:
            on_event("message_error", {"error": str(e)})
```

---

### 3.5 Função main() - Conexão (linha 152-170)

**Antes:**
```python
async def main(on_event: Optional[Callable[[str, Any], None]] = None):
    logger.info("=" * 60)
    logger.info(f"Iniciando Sistema de Detecção de Takt-Time")
    logger.info(f"Dispositivo: {DEVICE_ID}")
    logger.info(f"Conectando ao RabbitMQ em {AMQP_URL}")
    logger.info("=" * 60)

    takt_tracker_count = 0
    connection = None
    try:
        logger.debug("Tentando estabelecer conexão robusta com RabbitMQ...")
        connection = await aio_pika.connect_robust(AMQP_URL)
        logger.info("✓ Conectado ao RabbitMQ com sucesso!")
    except Exception as e:
        logger.error(f"✗ Não foi possível conectar: {e}", exc_info=True)
        if on_event:
            on_event("connection_error", {"error": str(e)})
        return

    async with connection:
        channel = await connection.channel()
        logger.info("✓ Canal RabbitMQ criado")
```

**Depois:**
```python
async def main(on_event: Optional[Callable[[str, Any], None]] = None):
    logger.info("=" * 60)
    logger.info(f"Iniciando Sistema de Detecção de Takt-Time")
    logger.info(f"Dispositivo: {DEVICE_ID}")
    logger.info(f"Conectando ao RabbitMQ MQTT em {MQTT_BROKER}:{MQTT_PORT}")
    logger.info("=" * 60)

    takt_tracker_count = 0
    
    try:
        logger.debug(f"Tentando estabelecer conexão MQTT...")
        async with aiomqtt.Client(
            hostname=MQTT_BROKER,
            port=MQTT_PORT,
            username=MQTT_USER,
            password=MQTT_PASS,
            keepalive=60,
        ) as client:
            logger.info("✓ Conectado ao RabbitMQ MQTT com sucesso!")
```

---

### 3.6 Função main() - Notificação Conexão (linha 173-175)

**Antes:**
```python
        if on_event:
            on_event("connected", {"amqp_url": AMQP_URL})
```

**Depois:**
```python
            if on_event:
                on_event("connected", {"broker": MQTT_BROKER, "port": MQTT_PORT})
```

---

### 3.7 Função main() - Envio de Mensagem (linha 290)

**Antes:**
```python
                        # Envia a mensagem para o RabbitMQ
                        await send_message(channel, ROUTING_KEY, extracted_text)
```

**Depois:**
```python
                        # Envia a mensagem para o RabbitMQ via MQTT
                        await send_message(client, MQTT_TOPIC, extracted_text, on_event)
```

---

### 3.8 Função main() - Tratamento de Erros no Loop (linha 371-404)

**Antes:**
```python
            except Exception as e:
                logger.error(f"✗ Erro durante loop: {e}", exc_info=True)
                if on_event:
                    on_event("runtime_error", {"error": str(e)})
                await asyncio.sleep(2)
```

**Depois:**
```python
                except aiomqtt.MqttError as e:
                    logger.error(f"✗✗✗ ERRO MQTT DURANTE OPERAÇÃO ✗✗✗")
                    logger.error(f"    Iteração: {iteration}")
                    logger.error(f"    Detalhes: {e}")
                    if on_event:
                        on_event("runtime_error", {"error": f"Erro MQTT: {e}"})
                    break  # Interrompe loop - conexão perdida
                except ConnectionError as e:
                    logger.error(f"✗✗✗ CONEXÃO MQTT PERDIDA ✗✗✗")
                    logger.error(f"    Iteração: {iteration}")
                    logger.error(f"    Detalhes: {e}")
                    if on_event:
                        on_event("runtime_error", {"error": "Conexão MQTT perdida"})
                    break  # Interrompe loop
                except KeyboardInterrupt:
                    logger.warning("⚠ Interrupção manual detectada")
                    raise
                except Exception as e:
                    logger.error(f"✗✗✗ ERRO INESPERADO ✗✗✗")
                    logger.error(f"    Tipo: {type(e).__name__}")
                    logger.error(f"    Mensagem: {e}")
                    logger.error(f"    Stack trace:", exc_info=True)
                    if on_event:
                        on_event("runtime_error", {"error": str(e)})
                    await asyncio.sleep(2)
    
    except asyncio.TimeoutError as e:
        logger.error(f"✗✗✗ TIMEOUT ao conectar ✗✗✗")
        logger.error(f"    Broker: {MQTT_BROKER}:{MQTT_PORT}")
        if on_event:
            on_event("connection_error", {"error": "Timeout"})
    except aiomqtt.MqttError as e:
        logger.error(f"✗✗✗ ERRO MQTT ao conectar ✗✗✗")
        logger.error(f"    Broker: {MQTT_BROKER}:{MQTT_PORT}")
        logger.error(f"    Detalhes: {e}")
        if on_event:
            on_event("connection_error", {"error": f"Erro MQTT: {e}"})
    except Exception as e:
        logger.error(f"✗✗✗ ERRO ao conectar ✗✗✗")
        logger.error(f"    Tipo: {type(e).__name__}")
        logger.error(f"    Mensagem: {e}")
        if on_event:
            on_event("connection_error", {"error": str(e)})
```

---

## 🖥️ Passo 4: Atualizar app.py

### 4.1 InitializationWorker - Teste de Conexão (linha 80-120)

**Encontre:**
```python
        # 2. Verificar Conexão MQTT
        self.status_update.emit({"event": "mqtt_check_start"})
        
        try:
            import aio_pika
            
            # Obtém configuração AMQP
            tech_config = cfg.get("tech", {})
            amqp_url = tech_config.get("amqp_host", "")
```

**Substitua por:**
```python
        # 2. Verificar Conexão MQTT
        self.status_update.emit({"event": "mqtt_check_start"})
        
        try:
            import asyncio_mqtt as aiomqtt
            
            # Obtém configuração MQTT
            tech_config = cfg.get("tech", {})
            mqtt_broker = tech_config.get("mqtt_broker", "")
            mqtt_port = tech_config.get("mqtt_port", 1883)
            mqtt_user = tech_config.get("mqtt_user", "")
            mqtt_pass = tech_config.get("mqtt_pass", "")
```

**Continue:**
```python
            if not mqtt_broker:
                logger.debug("MQTT broker não configurado, usando variável de ambiente")
                from dotenv import load_dotenv
                load_dotenv()
                mqtt_broker = os.getenv("MQTT_BROKER", "10.100.1.43")
                mqtt_user = os.getenv("MQTT_USER", "dass")
                mqtt_pass = os.getenv("MQTT_PASS", "pHUWphISTl7r_Geis")
            
            logger.debug(f"Testando conexão MQTT em: {mqtt_broker}:{mqtt_port}")
            
            # Tenta conectar via MQTT
            async def test_connection():
                async with aiomqtt.Client(
                    hostname=mqtt_broker,
                    port=mqtt_port,
                    username=mqtt_user,
                    password=mqtt_pass,
                    keepalive=60,
                ) as client:
                    pass  # Conexão bem-sucedida
            
            # Executa teste
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(test_connection())
            loop.close()
            
            logger.info(f"✓ Conexão MQTT estabelecida: {mqtt_broker}:{mqtt_port}")
            self.status_update.emit({"event": "mqtt_connected", "broker": mqtt_broker, "port": mqtt_port})
            
        except Exception as e:
            logger.error(f"✗ Erro ao verificar MQTT: {e}", exc_info=True)
            self.status_update.emit({"event": "mqtt_error", "error": str(e)})
            return
```

---

### 4.2 MQTTReconnectWorker - Igual ao InitializationWorker

Copie a mesma lógica do InitializationWorker para o MQTTReconnectWorker.

---

### 4.3 ConfigDialog - Campos de Configuração (linha 150-200)

**Encontre no tech_group:**
```python
        self.amqp_host_input = QLineEdit()
        self.amqp_host_input.setPlaceholderText("amqp://user:pass@host:port/")
        tech_layout.addRow("🌐 AMQP Host:", self.amqp_host_input)
```

**Substitua por:**
```python
        self.mqtt_broker_input = QLineEdit()
        self.mqtt_broker_input.setPlaceholderText("10.100.1.43")
        tech_layout.addRow("🌐 MQTT Broker:", self.mqtt_broker_input)
        
        self.mqtt_port_input = QLineEdit()
        self.mqtt_port_input.setPlaceholderText("1883")
        tech_layout.addRow("🔌 MQTT Port:", self.mqtt_port_input)
        
        self.mqtt_user_input = QLineEdit()
        self.mqtt_user_input.setPlaceholderText("dass")
        tech_layout.addRow("👤 MQTT User:", self.mqtt_user_input)
        
        self.mqtt_pass_input = QLineEdit()
        self.mqtt_pass_input.setEchoMode(QLineEdit.Password)
        self.mqtt_pass_input.setPlaceholderText("senha")
        tech_layout.addRow("🔒 MQTT Pass:", self.mqtt_pass_input)
```

---

### 4.4 ConfigDialog - Load/Save (linha 250-300)

**load_config():**
```python
        tech_config = config.get("tech", {})
        self.mqtt_broker_input.setText(tech_config.get("mqtt_broker", ""))
        self.mqtt_port_input.setText(str(tech_config.get("mqtt_port", 1883)))
        self.mqtt_user_input.setText(tech_config.get("mqtt_user", ""))
        self.mqtt_pass_input.setText(tech_config.get("mqtt_pass", ""))
        self.model_path_input.setText(tech_config.get("model_path", "./train_2025.pt"))
```

**save_config():**
```python
        config["tech"] = {
            "mqtt_broker": self.mqtt_broker_input.text().strip(),
            "mqtt_port": int(self.mqtt_port_input.text().strip() or "1883"),
            "mqtt_user": self.mqtt_user_input.text().strip(),
            "mqtt_pass": self.mqtt_pass_input.text().strip(),
            "model_path": self.model_path_input.text().strip(),
        }
```

---

## ✅ Passo 5: Testar a Migração

### 5.1 Teste de Configuração
```bash
python -c "from app import load_config; import json; print(json.dumps(load_config(), indent=2))"
```

### 5.2 Teste de Conexão MQTT
```bash
python -c "
import asyncio
import asyncio_mqtt as aiomqtt

async def test():
    async with aiomqtt.Client('10.100.1.43', 1883, username='dass', password='pHUWphISTl7r_Geis') as client:
        print('✓ Conexão MQTT OK!')

asyncio.run(test())
"
```

### 5.3 Executar Aplicação
```bash
python app.py
```

**Verificar:**
- ✅ Status MQTT: Conectado (verde)
- ✅ Logs mostram porta 1883
- ✅ Botão "Iniciar Análise" habilitado após conexão

---

## 🔧 Passo 6: Configurar ESP32 (Receptor)

### 6.1 Código Arduino/PlatformIO

```cpp
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

const char* ssid = "SUA_REDE";
const char* password = "SUA_SENHA";
const char* mqtt_server = "10.100.1.43";
const int mqtt_port = 1883;
const char* mqtt_user = "dass";
const char* mqtt_pass = "pHUWphISTl7r_Geis";
const char* mqtt_topic = "takt/device/cost-2-2408";

WiFiClient espClient;
PubSubClient client(espClient);

void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("📩 Mensagem recebida [");
  Serial.print(topic);
  Serial.print("]: ");
  
  String message;
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.println(message);
  
  // Parse JSON
  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, message);
  
  if (!error) {
    const char* event = doc["event"];
    const char* msg = doc["message"];
    
    Serial.print("Event: ");
    Serial.println(event);
    Serial.print("Message: ");
    Serial.println(msg);
    
    // Processar evento (acender LED, atualizar display, etc)
    if (strcmp(event, "takt") == 0) {
      digitalWrite(LED_BUILTIN, HIGH);
      delay(500);
      digitalWrite(LED_BUILTIN, LOW);
    }
  }
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("🔄 Conectando ao MQTT...");
    
    if (client.connect("ESP32_Client", mqtt_user, mqtt_pass)) {
      Serial.println(" ✓ Conectado!");
      client.subscribe(mqtt_topic);
      Serial.print("📡 Inscrito no tópico: ");
      Serial.println(mqtt_topic);
    } else {
      Serial.print(" ✗ Falhou, rc=");
      Serial.print(client.state());
      Serial.println(" tentando novamente em 5s");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);
  
  // Conectar WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✓ WiFi conectado!");
  
  // Configurar MQTT
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();
}
```

### 6.2 Bibliotecas Necessárias (platformio.ini)

```ini
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
lib_deps = 
    knolleary/PubSubClient@^2.8
    bblanchon/ArduinoJson@^6.21.3
monitor_speed = 115200
```

---

## 📋 Checklist Final

### Arquivos Modificados
- [ ] `requirements-app.txt` → asyncio-mqtt
- [ ] `config/config.json` → mqtt_broker, mqtt_port, mqtt_user, mqtt_pass
- [ ] `main.py` → imports, variáveis, send_message(), main()
- [ ] `app.py` → InitializationWorker, MQTTReconnectWorker, ConfigDialog

### Testes
- [ ] Conexão MQTT (porta 1883) funciona
- [ ] Mensagens são publicadas no tópico correto
- [ ] ESP32 recebe mensagens
- [ ] Reconexão automática funciona
- [ ] Logs estão corretos

### Documentação
- [ ] README atualizado com instruções MQTT
- [ ] Comentários no código atualizados
- [ ] Este guia revisado

---

## 🆘 Troubleshooting

### Erro: "Import asyncio_mqtt could not be resolved"
```bash
pip install asyncio-mqtt
```

### Erro: "Connection refused (porta 1883)"
```bash
# Verificar se RabbitMQ MQTT plugin está ativo
sudo rabbitmq-plugins enable rabbitmq_mqtt

# Verificar porta aberta
netstat -tulpn | grep 1883
```

### Erro: "Authentication failed"
```bash
# Criar usuário MQTT no RabbitMQ
sudo rabbitmqctl add_user dass pHUWphISTl7r_Geis
sudo rabbitmqctl set_permissions -p / dass ".*" ".*" ".*"
```

### ESP32 não recebe mensagens
- Verificar se está no mesmo tópico: `takt/device/DEVICE_ID`
- Verificar credenciais MQTT no ESP32
- Testar com MQTT Explorer ou mosquitto_sub

---

## 📚 Referências

- [asyncio-mqtt Documentation](https://sbtinstruments.github.io/asyncio-mqtt/)
- [RabbitMQ MQTT Plugin](https://www.rabbitmq.com/mqtt.html)
- [ESP32 PubSubClient](https://github.com/knolleary/pubsubclient)
- [MQTT Protocol Specification](https://mqtt.org/)

---

## ✨ Benefícios da Migração

✅ Comunicação direta com ESP32  
✅ Protocolo mais leve (menor latência)  
✅ Menos overhead de rede  
✅ Padrão IoT amplamente suportado  
✅ Código mais simples e legível  
✅ Melhor compatibilidade com dispositivos embarcados  

---

**Criado em**: 1 de novembro de 2025  
**Versão**: 1.0  
**Autor**: GitHub Copilot  
