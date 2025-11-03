import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
import json
import threading
import time
import logging
from typing import Optional, Callable, Dict

# Configurar logger
logger = logging.getLogger(__name__)


class DeviceStatus:
    """Classe para armazenar status do dispositivo"""

    def __init__(self, device_id: str):
        self.device_id = device_id
        self.connected = False
        self.last_seen: Optional[datetime] = None
        self.last_heartbeat: Optional[dict] = None
        self.status_topic = f"takt/device/{device_id}/status"
        self.heartbeat_topic = f"takt/device/{device_id}/heartbeat"
        self.command_topic = f"takt/device/{device_id}"


class MQTTManager:
    """Gerenciador MQTT para comunicação com ESP32"""

    def __init__(
        self,
        broker: str,
        port: int = 1883,
        username: str = None,
        password: str = None,
        timeout_seconds: int = 60,
    ):
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.timeout_seconds = timeout_seconds

        self.client = mqtt.Client()
        self.devices: Dict[str, DeviceStatus] = {}
        self.monitoring = False
        self.on_status_change_callback: Optional[Callable] = None
        self._connected = False
        self._connect_event = threading.Event()

        # Configurar callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        if username and password:
            self.client.username_pw_set(username, password)

    def add_device(self, device_id: str):
        """Adiciona um dispositivo para monitoramento"""
        if device_id not in self.devices:
            new_device = DeviceStatus(device_id)
            self.devices[device_id] = new_device
            logger.info(f"📱 Dispositivo adicionado: {device_id}")
            logger.debug(f"   Status Topic: {new_device.status_topic}")
            logger.debug(f"   Heartbeat Topic: {new_device.heartbeat_topic}")
            logger.debug(f"   Command Topic: {new_device.command_topic}")
        else:
            logger.warning(f"Dispositivo {device_id} já está adicionado.")

    def connect(self, timeout: int = 10) -> bool:
        """Conecta ao broker MQTT"""
        try:
            self._connect_event.clear()
            self._connected = False

            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()

            # Aguardar confirmação de conexão
            if self._connect_event.wait(timeout):
                if self._connected:
                    # Iniciar thread de monitoramento
                    self.monitoring = True
                    monitor_thread = threading.Thread(target=self._monitor_devices)
                    monitor_thread.daemon = True
                    monitor_thread.start()
                    logger.info("Thread de monitoramento iniciada")

                    logger.info(f"Conectado ao broker MQTT: {self.broker}:{self.port}")
                    return True
                else:
                    logger.error("Conexão falhou após timeout")
                    return False
            else:
                logger.error(f"Timeout ao conectar ao broker ({timeout}s)")
                self.client.loop_stop()
                return False

        except Exception as e:
            logger.error(f"Erro ao conectar ao broker: {e}", exc_info=True)
            return False

    def _on_connect(self, client, userdata, flags, rc):
        """Callback de conexão"""
        if rc == 0:
            self._connected = True
            self._connect_event.set()
            logger.info("Conectado ao broker MQTT")

            # Inscrever nos tópicos de todos os dispositivos
            for device_id, device in self.devices.items():
                client.subscribe(device.status_topic)
                client.subscribe(device.heartbeat_topic)
                print(f"Inscrito em: {device.status_topic}")
                print(f"Inscrito em: {device.heartbeat_topic}")
        else:
            self._connected = False
            self._connect_event.set()
            error_messages = {
                1: "Protocolo incorreto",
                2: "Client ID rejeitado",
                3: "Servidor indisponível",
                4: "Usuário/senha inválidos",
                5: "Não autorizado",
            }
            error_msg = error_messages.get(rc, f"Código desconhecido: {rc}")
            logger.error(f"Falha na conexão MQTT: {error_msg}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback de desconexão"""
        self._connected = False
        if rc != 0:
            logger.warning(f"Desconectado inesperadamente. Código: {rc}")
        else:
            logger.info("Desconectado do broker MQTT")

    def _on_message(self, client, userdata, msg):
        """Callback para processar mensagens"""
        topic = msg.topic
        payload = msg.payload.decode()

        # Encontrar dispositivo pelo tópico
        device = None
        for dev in self.devices.values():
            if topic == dev.status_topic or topic == dev.heartbeat_topic:
                device = dev
                break

        if not device:
            return

        # Processar mensagem de status
        if topic == device.status_topic:
            old_status = device.connected
            device.connected = payload == "online"
            device.last_seen = datetime.now()

            status_emoji = "🟢" if device.connected else "🔴"
            logger.info(f"{status_emoji} {device.device_id}: {payload}")

            # Notificar mudança de status
            if old_status != device.connected and self.on_status_change_callback:
                try:
                    self.on_status_change_callback(device.device_id, device.connected)
                except Exception as e:
                    logger.error(
                        f"Erro no callback de mudança de status: {e}", exc_info=True
                    )

        # Processar heartbeat
        elif topic == device.heartbeat_topic:
            try:
                heartbeat_data = json.loads(payload)
                device.last_heartbeat = heartbeat_data
                device.last_seen = datetime.now()
                device.connected = True

                logger.debug(
                    f"Heartbeat de {device.device_id}: "
                    f"Uptime={heartbeat_data.get('uptime')}s, "
                    f"RSSI={heartbeat_data.get('wifi_rssi')}dBm"
                )
            except json.JSONDecodeError:
                logger.error(f"Erro ao decodificar heartbeat de {device.device_id}")

    def _monitor_devices(self):
        """Thread para monitorar timeout de dispositivos"""
        while self.monitoring:
            for device in self.devices.values():
                if device.last_seen:
                    timeout = datetime.now() - timedelta(seconds=self.timeout_seconds)

                    if device.connected and device.last_seen < timeout:
                        old_status = device.connected
                        device.connected = False
                        logger.warning(
                            f"{device.device_id} timeout - marcado como offline"
                        )

                        if self.on_status_change_callback:
                            try:
                                self.on_status_change_callback(device.device_id, False)
                            except Exception as e:
                                logger.error(
                                    f"Erro no callback de timeout: {e}", exc_info=True
                                )

            time.sleep(10)  # Verificar a cada 10 segundos
        logger.debug("Thread de monitoramento finalizada")

    def is_device_connected(self, device_id: str) -> bool:
        """Verifica se um dispositivo está conectado"""
        return self._connected and self.client.is_connected()

    def get_device_info(self, device_id: str) -> Optional[dict]:
        """Retorna informações do dispositivo"""
        device = self.devices.get(device_id)
        if not device:
            return None

        return {
            "id": device.device_id,
            "connected": device.connected,
            "last_seen": device.last_seen.isoformat() if device.last_seen else None,
            "last_heartbeat": device.last_heartbeat,
            "status_topic": device.status_topic,
            "heartbeat_topic": device.heartbeat_topic,
            "command_topic": device.command_topic,
        }

    def publish_command(self, device_id: str, command: dict, qos: int = 1) -> bool:
        """Publica comando para um dispositivo"""
        if not self._connected:
            logger.error("Não conectado ao broker MQTT")
            return False

        print(f"Publicando comando para {device_id}: {command}")
        device = self.devices.get(device_id)
        if not device:
            logger.error(f"Dispositivo {device_id} não encontrado")
            return False

        if not device.connected:
            logger.warning(f"{device_id} está offline!")

        try:
            payload = json.dumps(command)
            result = self.client.publish(device.command_topic, payload, qos=qos)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Comando enviado para {device_id}: {payload}")
                return True
            else:
                logger.error(f"Falha ao enviar comando: {result.rc}")
                return False
        except Exception as e:
            logger.error(f"Erro ao publicar: {e}")
            return False

    def on_status_change(self, callback: Callable):
        """Define callback para mudanças de status"""
        self.on_status_change_callback = callback

    def disconnect(self):
        """Desconecta do broker"""
        self.monitoring = False
        self.client.loop_stop()
        self.client.disconnect()
        self._connected = False
        logger.info("Desconectado do broker MQTT")
