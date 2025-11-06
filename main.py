import os
import aio_pika
import asyncio
from ultralytics import YOLO
from PIL import ImageGrab
import pytesseract
import cv2
import numpy as np
import json
import logging
import time
from typing import Callable, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# Configuração de logging detalhado
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[logging.FileHandler("main_debug.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

logging.getLogger("pytesseract").setLevel(logging.WARNING)

# Carregar configuração do arquivo config.json
CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


def load_config():
    """Carrega configuração do arquivo JSON"""
    logger.debug(f"Carregando configuração de: {CONFIG_PATH}")
    if not os.path.exists(CONFIG_PATH):
        logger.warning("Arquivo de configuração não encontrado, usando padrões")
        return {
            "device": {"cell_number": "", "factory": "", "cell_leader": ""},
            "network": {"wifi_ssid": "", "wifi_pass": ""},
            "tech": {
                "amqp_host": "",
                "amqp_user": "",
                "amqp_pass": "",
                "model_path": "./train_2025.pt",
            },
        }
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
            return config
    except Exception as e:
        logger.error(f"Erro ao carregar configuração: {e}", exc_info=True)
        return {
            "device": {"cell_number": "", "factory": "", "cell_leader": ""},
            "network": {"wifi_ssid": "", "wifi_pass": ""},
            "tech": {
                "amqp_host": "",
                "amqp_user": "",
                "amqp_pass": "",
                "model_path": "./train_2025.pt",
            },
        }


# Carregar configuração
config = load_config()
tech_config = config.get("tech", {})
device_config = config.get("device", {})

# Configurações AMQP - prioriza config.json, depois .env, depois valores padrão
AMQP_URL = tech_config.get("amqp_host") or os.getenv(
    "AMQP_URL", "amqp://dass:pHUWphISTl7r_Geis@10.110.21.3/"
)
AMQP_EXCHANGE = "amq.topic"
CELL_NUMBER = device_config.get("cell_number")
FACTORY_NUMBER = device_config.get("factory")
DEVICE_ID = f"{FACTORY_NUMBER}-{CELL_NUMBER}"
ROUTING_KEY = f"takt.device.cost-{DEVICE_ID}"

pytesseract.pytesseract.tesseract_cmd = r"/usr/bin/tesseract"
MODEL_PATH = tech_config.get("model_path") or "./train_2025.pt"


def extract_roi(frame, box, pad=5, scale=2):
    """Extrai ROI da imagem com padding e escala para melhorar OCR."""
    x1, y1, x2, y2 = map(int, box)

    # Adiciona padding, limitado aos bounds da imagem
    x1, y1 = max(x1 - pad, 0), max(y1 - pad, 0)
    x2, y2 = min(x2 + pad, frame.shape[1]), min(y2 + pad, frame.shape[0])

    roi = frame[y1:y2, x1:x2]
    # Escala para melhorar reconhecimento de texto pequeno
    h, w = roi.shape[:2]
    scaled_roi = cv2.resize(roi, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
    return scaled_roi


def preprocess_for_ocr(roi_bgr):
    """Pré-processa ROI para melhorar qualidade do OCR."""
    gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th


def extract_takt_message(roi) -> Optional[dict]:
    """
    Extrai e reconhece texto da ROI usando OCR.
    
    Returns:
        dict: {'event': 'takt'/'takt_screen', 'message': str} com resultado do OCR
        None: se OCR falhar
    """
    tess_config = (
        r"--oem 3 "  # LSTM OCR engine
        r"-c tessedit_char_whitelist=0123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ "
    )
    text = (
        pytesseract.image_to_string(roi, config=tess_config)
        .strip()
        .replace("\n", " ")
        .strip()
    )

    logger.debug(f"Texto extraído por OCR: '{text}'")

    if "00:00:00" in text:
        logger.info("Padrão '00:00:00' detectado - Takt concluído!")
        return {"event": "takt", "message": "Takt detectado"}
    else:
        return {"event": "takt_screen", "message": "Takt Aberto"}


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
        logger.info(f"Mensagem publicada em '{routing_key}': {message_body}")

        # Notifica a UI que a mensagem foi enviada
        if on_event:
            on_event("message_sent", message_body)
    except Exception as e:
        logger.error(
            f"✗ Erro ao enviar mensagem para '{routing_key}': {e}", exc_info=True
        )
        if on_event:
            on_event("message_error", {"error": str(e)})


def update_takt_count(current_count: int) -> int:
    return current_count + 1


async def main(
    on_event: Optional[Callable[[str, Any], None]] = None,
    connection: Optional[Any] = None,
    device_id: Optional[str] = None,
):
    logger.info("=" * 60)
    logger.info(f"Iniciando Sistema de Detecção de Takt-Time")
    if device_id:
        logger.info(f"Dispositivo (passado por parâmetro): {device_id}")
        DEVICE_ID_ACTUAL = device_id
    else:
        DEVICE_ID_ACTUAL = DEVICE_ID
        logger.info(f"Dispositivo (config): {DEVICE_ID_ACTUAL}")

    logger.info("=" * 60)

    takt_tracker_count = 0

    is_mqtt_manager = connection and hasattr(connection, "publish_command")

    if is_mqtt_manager:
        logger.info("Usando MQTTManager para comunicação")
        if on_event:
            on_event("connected", {"url": "MQTT Manager ativo"})
    else:
        logger.error("Conexão MQTT inválida!")
        if on_event:
            on_event("connection_error", {"error": "MQTTManager não fornecido"})
        return

    # Carregar modelo
    logger.info(f"Carregando modelo YOLO de: {MODEL_PATH}")
    if not os.path.exists(MODEL_PATH):
        logger.error(f"Modelo não encontrado em {MODEL_PATH}")
        if on_event:
            on_event("model_missing", {"path": MODEL_PATH})
        return

    model = YOLO(MODEL_PATH)
    logger.info("Modelo YOLO carregado com sucesso!")
    if on_event:
        on_event("model_loaded", {"model_path": MODEL_PATH})

    last_message_time = None
    last_sent_message = None
    last_takt_screen_check = None
    last_device_warning_time = None  # Controle de aviso de dispositivo desconectado

    logger.info("Iniciando loop principal de detecção...")
    iteration = 0

    while True:
        try:
            iteration += 1
            if iteration % 100 == 0:
                logger.debug(f"Loop de detecção - Iteração: {iteration}")

            screen = ImageGrab.grab()
            screen_np = np.array(screen)
            frame = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)

            # Fazer a predição no frame atual
            results = model.predict(
                source=frame, stream=False, conf=0.15, verbose=False
            )

            extracted_text = None
            for result in results:
                for box in result.boxes.xyxy:
                    roi = extract_roi(frame, box)
                    if roi is None or roi.size == 0:
                        continue

                    processed_roi = preprocess_for_ocr(roi)
                    extracted_text = extract_takt_message(processed_roi)

                    if extracted_text is not None:
                        break
                if extracted_text:
                    break

            # Detecta o fim da etapa de um takt
            if extracted_text:
                now = time.time()
                
                # Validação adicional da estrutura
                if not isinstance(extracted_text, dict) or "event" not in extracted_text:
                    logger.error(
                        f"Estrutura inválida de extracted_text: {extracted_text}"
                    )
                    continue

                event_type = extracted_text.get("event")

                # Trata reconhecimento de tela da takt aberto (sem reconhecer fim de takt) - Faz check a cada 5 segundos
                if event_type == "takt_screen":
                    if (
                        last_takt_screen_check is None
                        or (now - last_takt_screen_check) > 5
                    ):
                        if on_event:
                            try:
                                on_event(
                                    "takt_screen_detected",
                                    {"message": extracted_text.get("message")},
                                )
                            except Exception as e:
                                logger.error(
                                    f"Erro ao chamar on_event para takt_screen: {e}",
                                    exc_info=True,
                                )
                        last_takt_screen_check = now
                    await asyncio.sleep(0.5)
                    continue

                # Trata detecção de conclusão de takt (00:00:00)
                if event_type == "takt":
                    logger.debug(f"===> Takt detectado em {now:.3f}")
                    # Debounce mais robusto
                    if last_sent_message is not None and (now - last_message_time) <= 20:
                        logger.debug(
                            f"Mensagem ignorada (debounce ativo - {now - last_message_time:.2f}s desde última)"
                        )
                        await asyncio.sleep(0.5)
                        continue
                        
                    logger.debug(f"✅ Passou pelo debounce em {now:.3f}")

                    # ===== VERIFICAÇÃO DE CONEXÃO DO ESP32 =====
                    # Verifica se o dispositivo ESP32 está conectado antes de enviar
                    is_device_connected = False
                    if is_mqtt_manager and hasattr(connection, 'device_status'):
                        device_status_dict = connection.device_status
                        is_device_connected = device_status_dict.get(DEVICE_ID_ACTUAL, False)
                        logger.debug(f"📊 device_status completo: {device_status_dict}")
                        logger.debug(f"✓ Status de conexão do dispositivo {DEVICE_ID_ACTUAL}: {is_device_connected}")
                    else:
                        logger.error("❌ connection.device_status não disponível!")
                    
                    # Só envia se o dispositivo estiver conectado
                    if not is_device_connected:
                        logger.warning(
                            f"ESP32 desconectado em {now:.3f} - aguardando conexão.. "
                            f"Mensagem de takt NÃO será enviada."
                        )
                        
                        # Notifica a UI sobre o dispositivo desconectado (com cooldown de 30s)
                        should_notify = False
                        if last_device_warning_time is None:
                            should_notify = True
                        elif (now - last_device_warning_time) >= 30:  # 30 segundos de cooldown
                            should_notify = True
                        
                        if should_notify and on_event:
                            last_device_warning_time = now
                            on_event("device_disconnected", {
                                "device_id": DEVICE_ID_ACTUAL,
                                "message": "ESP32 desconectado - mensagem não enviada",
                                "takt_detected": True
                            })
                            logger.info("Evento 'device_disconnected' enviado para UI")
                        else:
                            logger.debug(f"Aviso de dispositivo desconectado em cooldown (última notificação há {now - last_device_warning_time:.1f}s)")
                        
                        # Aguarda um tempo antes de verificar novamente
                        last_message_time = now
                        await asyncio.sleep(2)
                        continue

                    # ===== DISPOSITIVO CONECTADO - PROCESSAR TAKT =====
                    logger.info("=" * 60)
                    logger.info("EVENTO TAKT CONFIRMADO - Processando...")
                    logger.info(f"ESP32 ({DEVICE_ID_ACTUAL}) conectado!")
                    logger.info(f"Tempo desde última mensagem: {(now - last_message_time) if last_message_time else 'N/A'}")
                    logger.info("=" * 60)

                    last_sent_message = extracted_text
                    last_message_time = now
                    last_takt_screen_check = now  # Reset do check de tela

                    # Atualiza o contador de detecções
                    takt_tracker_count = update_takt_count(takt_tracker_count)
                    logger.info(
                        f"📊 Contador de takt atualizado: {takt_tracker_count}/3"
                    )

                    # Notifica a UI baseado no contador
                    try:
                        if on_event:
                            match takt_tracker_count:
                                case 1:
                                    logger.info(">>> 🟢 Primeira detecção de Takt (1/3)")
                                    on_event("takt_detected", {
                                        "takt": takt_tracker_count,
                                        "device_connected": True
                                    })

                                case 2:
                                    logger.info(">>> 🟡 Segunda detecção de Takt (2/3)")
                                    on_event("takt_detected", {
                                        "takt": takt_tracker_count,
                                        "device_connected": True
                                    })

                                case 3:
                                    logger.info(
                                        ">>> 🔴 Terceira detecção de Takt (3/3) - Talão completo!"
                                    )
                                    on_event("takt_detected", {
                                        "takt": takt_tracker_count,
                                        "device_connected": True
                                    })
                        else:
                            logger.warning("⚠️ on_event callback não está definido!")
                    except Exception as e:
                        logger.error(
                            f"❌ Erro ao notificar UI via on_event: {e}", exc_info=True
                        )

                    # Envia a mensagem via MQTT
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    extracted_text.update({"id": DEVICE_ID_ACTUAL})
                    extracted_text.update({"timestamp": timestamp})
                    extracted_text.update({"takt_count": takt_tracker_count})

                    if is_mqtt_manager:
                        try:
                            logger.info(f"📤 Enviando comando MQTT: {extracted_text}")
                            success = connection.publish_command(
                                DEVICE_ID_ACTUAL, extracted_text, qos=1
                            )
                            if success:
                                logger.info(
                                    f"✅ Mensagem enviada via MQTT: {extracted_text}"
                                )
                                if on_event:
                                    try:
                                        on_event("message_sent", extracted_text)
                                    except Exception as e:
                                        logger.error(
                                            f"Erro no callback message_sent: {e}",
                                            exc_info=True,
                                        )
                            else:
                                logger.error("❌ Falha ao enviar mensagem via MQTT (publish retornou False)")
                                if on_event:
                                    try:
                                        on_event(
                                            "message_error",
                                            {"error": "Falha no publish MQTT"},
                                        )
                                    except Exception as e:
                                        logger.error(
                                            f"Erro no callback message_error: {e}",
                                            exc_info=True,
                                        )
                        except Exception as e:
                            logger.error(
                                f"❌ Exceção ao publicar MQTT: {e}", exc_info=True
                            )
                            if on_event:
                                try:
                                    on_event("message_error", {"error": str(e)})
                                except Exception as inner_e:
                                    logger.error(
                                        f"Erro no callback de erro: {inner_e}",
                                        exc_info=True,
                                    )
                    else:
                        logger.error("❌ MQTTManager não disponível!")

                    # Reset do contador após takt 3
                    if takt_tracker_count >= 3:
                        logger.info("🔄 Resetando contador de takt para 0")
                        takt_tracker_count = 0

            await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(
                f"✗ Erro durante a execução do loop principal: {e}", exc_info=True
            )
            if on_event:
                try:
                    on_event("runtime_error", {"error": str(e)})
                except Exception as inner_e:
                    logger.error(f"Erro no callback de erro: {inner_e}", exc_info=True)
            await asyncio.sleep(2)


if __name__ == "__main__":
    try:
        logger.info("Iniciando sistema em modo standalone...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Sistema interrompido pelo usuário (Ctrl+C)")
    except Exception as e:
        logger.error(f"✗ Erro fatal ao iniciar o sistema: {e}", exc_info=True)
