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
        self.ack_topic = f"takt/device/{device_id}/ack"
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
        self._devices_lock = threading.RLock()
        self._primary_device_id: Optional[str] = None
        self._id_update_ack_events: Dict[str, threading.Event] = {}
        self._last_id_update_ack: Dict[str, dict] = {}

        # Configurar callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        if username and password:
            self.client.username_pw_set(username, password)

    def add_device(self, device_id: str):
        """Adiciona um dispositivo para monitoramento"""
        with self._devices_lock:
            if device_id in self.devices:
                logger.warning(f"Dispositivo {device_id} já está adicionado.")
                return

            new_device = DeviceStatus(device_id)
            self.devices[device_id] = new_device
            self._id_update_ack_events.setdefault(device_id, threading.Event())
            if not self._primary_device_id:
                self._primary_device_id = device_id

        logger.info(f"📱 Dispositivo adicionado: {device_id}")
        logger.debug(f"   Status Topic: {new_device.status_topic}")
        logger.debug(f"   Heartbeat Topic: {new_device.heartbeat_topic}")
        logger.debug(f"   Ack Topic: {new_device.ack_topic}")
        logger.debug(f"   Command Topic: {new_device.command_topic}")

        if self._connected:
            self.client.subscribe(new_device.status_topic)
            self.client.subscribe(new_device.heartbeat_topic)
            self.client.subscribe(new_device.ack_topic)
            logger.info(f"Inscrito em: {new_device.status_topic}")
            logger.info(f"Inscrito em: {new_device.heartbeat_topic}")
            logger.info(f"Inscrito em: {new_device.ack_topic}")

    def remove_device(self, device_id: str):
        """Remove um dispositivo do monitoramento"""
        with self._devices_lock:
            device = self.devices.pop(device_id, None)
            self._id_update_ack_events.pop(device_id, None)
            self._last_id_update_ack.pop(device_id, None)
            if self._primary_device_id == device_id:
                self._primary_device_id = next(iter(self.devices.keys()), None)

        if not device:
            return

        if self._connected:
            self.client.unsubscribe(device.status_topic)
            self.client.unsubscribe(device.heartbeat_topic)
            self.client.unsubscribe(device.ack_topic)
        logger.info(f"🗑️ Dispositivo removido: {device_id}")

    def set_primary_device(self, device_id: str) -> bool:
        """Define dispositivo principal usado para comandos e status"""
        with self._devices_lock:
            if device_id not in self.devices:
                logger.error(f"Não é possível definir primário: dispositivo {device_id} não existe")
                return False
            self._primary_device_id = device_id
        logger.info(f"🎯 Dispositivo primário atualizado para: {device_id}")
        return True

    def get_primary_device_id(self) -> Optional[str]:
        """Retorna o device_id primário atual"""
        with self._devices_lock:
            return self._primary_device_id

    def switch_primary_device(self, old_device_id: str, new_device_id: str):
        """Troca o dispositivo primário para um novo ID e remove o antigo."""
        if not new_device_id:
            return

        self.add_device(new_device_id)
        self.set_primary_device(new_device_id)

        if old_device_id and old_device_id != new_device_id:
            self.remove_device(old_device_id)

    def prepare_device_id_update_ack_wait(self, new_device_id: str) -> float:
        """Prepara evento de ACK para evitar race antes do publish."""
        with self._devices_lock:
            event = self._id_update_ack_events.setdefault(new_device_id, threading.Event())
            event.clear()
        return time.time()

    def wait_for_device_id_update_ack(
        self, new_device_id: str, min_timestamp: float = 0.0, timeout: float = 12.0
    ) -> bool:
        """Aguarda ACK explícito de atualização de device_id."""
        with self._devices_lock:
            ack = self._last_id_update_ack.get(new_device_id)
            if ack and ack.get("status") == "ok" and ack.get("timestamp", 0) >= min_timestamp:
                return True
            event = self._id_update_ack_events.setdefault(new_device_id, threading.Event())

        if not event.wait(timeout):
            return False

        with self._devices_lock:
            ack = self._last_id_update_ack.get(new_device_id)
            if not ack:
                return False
            return ack.get("status") == "ok" and ack.get("timestamp", 0) >= min_timestamp

    def get_last_device_id_update_ack(self, new_device_id: str) -> Optional[dict]:
        """Retorna último ACK de atualização de ID para inspeção."""
        with self._devices_lock:
            ack = self._last_id_update_ack.get(new_device_id)
            return dict(ack) if ack else None

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
            with self._devices_lock:
                devices_snapshot = list(self.devices.values())
            for device in devices_snapshot:
                client.subscribe(device.status_topic)
                client.subscribe(device.heartbeat_topic)
                client.subscribe(device.ack_topic)
                print(f"Inscrito em: {device.status_topic}")
                print(f"Inscrito em: {device.heartbeat_topic}")
                print(f"Inscrito em: {device.ack_topic}")
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
        with self._devices_lock:
            devices_snapshot = list(self.devices.values())
        for dev in devices_snapshot:
            if topic == dev.status_topic or topic == dev.heartbeat_topic or topic == dev.ack_topic:
                device = dev
                break

        if not device:
            return

        if topic == device.ack_topic:
            try:
                ack_data = json.loads(payload)
            except json.JSONDecodeError:
                logger.warning(f"⚠️  Ack inválido para {device.device_id}: {payload}")
                return

            if (
                ack_data.get("event") == "device_config_ack"
                and ack_data.get("message") == "update_device_id_ack"
            ):
                ack_new_id = ack_data.get("new_device_id") or ack_data.get("device_id") or device.device_id
                ack_entry = {
                    "timestamp": time.time(),
                    "status": ack_data.get("status", ""),
                    "old_device_id": ack_data.get("old_device_id"),
                    "new_device_id": ack_new_id,
                    "request_id": ack_data.get("request_id"),
                }
                with self._devices_lock:
                    self._last_id_update_ack[ack_new_id] = ack_entry
                    event = self._id_update_ack_events.setdefault(ack_new_id, threading.Event())
                    event.set()

                logger.info(
                    f"📨 ACK update_device_id recebido: old={ack_entry['old_device_id']}, "
                    f"new={ack_entry['new_device_id']}, status={ack_entry['status']}"
                )
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
                old_status = device.connected
                device.last_heartbeat = heartbeat_data
                device.last_seen = datetime.now()
                device.connected = True

                logger.debug(
                    f"Heartbeat de {device.device_id}: "
                    f"Uptime={heartbeat_data.get('uptime')}s, "
                    f"RSSI={heartbeat_data.get('wifi_rssi')}dBm, "
                    f"Free Heap={heartbeat_data.get('free_heap')} bytes"
                )
                
                # Notificar mudança de status se passou de offline para online
                if not old_status and device.connected and self.on_status_change_callback:
                    try:
                        logger.info(f"🟢 {device.device_id}: online (via heartbeat)")
                        self.on_status_change_callback(device.device_id, device.connected)
                    except Exception as e:
                        logger.error(
                            f"Erro no callback de mudança de status (heartbeat): {e}", exc_info=True
                        )
            except json.JSONDecodeError as e:
                logger.error(f"⚠️  Erro ao decodificar heartbeat de {device.device_id}: {e}")

    def _monitor_devices(self):
        """Thread para monitorar timeout de dispositivos"""
        while self.monitoring:
            with self._devices_lock:
                devices_snapshot = list(self.devices.values())

            for device in devices_snapshot:
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
        with self._devices_lock:
            device = self.devices.get(device_id)
        return device.connected if device else False

    @property
    def device_status(self) -> Dict[str, bool]:
        """Retorna dicionário com status de conexão de todos os dispositivos"""
        with self._devices_lock:
            return {device_id: device.connected for device_id, device in self.devices.items()}

    def get_device_info(self, device_id: str) -> Optional[dict]:
        """Retorna informações do dispositivo"""
        with self._devices_lock:
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
            "ack_topic": device.ack_topic,
            "command_topic": device.command_topic,
        }

    def publish_command(self, device_id: str, command: dict, qos: int = 1) -> bool:
        """Publica comando para um dispositivo"""
        if not self._connected:
            logger.error("Não conectado ao broker MQTT")
            return False

        print(f"Publicando comando para {device_id}: {command}")
        with self._devices_lock:
            device = self.devices.get(device_id)
        
        # Se o device_id não existe, mas estamos tentando atualizar o device_id,
        # usar o primeiro (e provavelmente único) dispositivo registrado
        target_device = device
        if not device:
            # Verificar se é um comando de atualização de device_id
            with self._devices_lock:
                has_devices = len(self.devices) > 0
                primary_id = self._primary_device_id
                if primary_id and primary_id in self.devices:
                    primary_device = self.devices[primary_id]
                else:
                    primary_device = next(iter(self.devices.values()), None)

            if command.get("message") == "update_device_id" and has_devices:
                # Usar o dispositivo primário (ID atual) para enviar atualização de ID
                target_device = primary_device
                logger.info(
                    f"⚠️  Device ID {device_id} não encontrado. "
                    f"Usando dispositivo registrado {target_device.device_id} para enviar atualização de ID."
                )
            else:
                logger.error(f"Dispositivo {device_id} não encontrado")
                return False

        if not target_device.connected:
            logger.warning(f"{target_device.device_id} está offline!")

        try:
            payload = json.dumps(command)
            result = self.client.publish(target_device.command_topic, payload, qos=qos)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(
                    f"✅ Comando enviado para {target_device.device_id} "
                    f"(topic: {target_device.command_topic}): {payload}"
                )
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

    def is_connected(self) -> bool:
        """Verifica se está conectado ao broker"""
        return self._connected
    
    def reconnect(self, timeout: int = 10) -> bool:
        """Tenta reconectar ao broker MQTT"""
        logger.info("Tentando reconectar ao broker MQTT...")
        
        # Se já está conectado, não precisa reconectar
        if self._connected:
            logger.info("Já está conectado ao broker MQTT")
            return True
        
        # Desconecta completamente antes de reconectar
        try:
            self.disconnect()
        except Exception as e:
            logger.debug(f"Erro ao desconectar antes de reconectar (pode ser normal): {e}")
        
        # Aguarda um pouco antes de reconectar
        import time
        time.sleep(1)
        
        # Tenta conectar novamente
        return self.connect(timeout=timeout)
