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

logger.info(f"=== Configuração Inicial ===")
logger.info(f"AMQP_URL: {AMQP_URL}")
logger.info(f"DEVICE_ID: {DEVICE_ID}")
logger.info(f"ROUTING_KEY: {ROUTING_KEY}")
logger.info(f"MODEL_PATH: {MODEL_PATH}")
logger.info(f"==========================")


def extract_roi(frame, box, pad=5, scale=2):
    x1, y1, x2, y2 = map(int, box)
    # logger.debug(f"Extraindo ROI - Box original: ({x1}, {y1}, {x2}, {y2})")

    # add padding, clamp to image bounds
    x1, y1 = max(x1 - pad, 0), max(y1 - pad, 0)
    x2, y2 = min(x2 + pad, frame.shape[1]), min(y2 + pad, frame.shape[0])

    # logger.debug(f"ROI com padding: ({x1}, {y1}, {x2}, {y2})")

    roi = frame[y1:y2, x1:x2]
    # upscale to improve tiny text
    h, w = roi.shape[:2]
    scaled_roi = cv2.resize(roi, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
    # logger.debug(f"ROI redimensionada de {w}x{h} para {w*scale}x{h*scale}")
    return scaled_roi


def preprocess_for_ocr(roi_bgr):
    gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th


def extract_takt_message(roi) -> Optional[dict]:
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

    # logger.debug(f"Texto extraído por OCR: '{text}'")

    if "00:00:00" in text:
        logger.info("Padrão '00:00:00' detectado - Takt concluído!")
        return {"event": "takt", "message": "Takt detectado"}
    else:
        # logger.debug("Tela de takt aberta (sem conclusão de etapa)")
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
    connection: Optional[aio_pika.RobustConnection] = None,
):
    logger.info("=" * 60)
    logger.info(f"Iniciando Sistema de Detecção de Takt-Time")
    logger.info(f"Dispositivo: {DEVICE_ID}")
    logger.info("=" * 60)

    takt_tracker_count = 0

    connection_created = False
    if connection is None:
        try:
            logger.debug("Tentando estabelecer conexão robusta com RabbitMQ...")
            connection = await aio_pika.connect_robust(AMQP_URL)
            connection_created = True
            logger.info("Conectado ao RabbitMQ com sucesso!")
        except Exception as e:
            logger.error(f"Não foi possível conectar ao RabbitMQ: {e}", exc_info=True)
            if on_event:
                on_event("connection_error", {"error": str(e)})
            return
    else:
        logger.info("Reutilizando conexão RabbitMQ existente do app.py")


    try:
        channel = await connection.channel()
        logger.info("Canal RabbitMQ criado")
        if on_event:
            on_event("connected", {"amqp_url": AMQP_URL})

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
                # logger.debug(f"Screenshot capturado: {frame.shape}")

                # Fazer a predição no frame atual
                results = model.predict(
                    source=frame, stream=False, conf=0.15, verbose=False
                )

                # num_detections = sum(len(result.boxes.xyxy) for result in results)
                # if num_detections > 0:
                #     logger.debug(f"YOLO detectou {num_detections} objetos")

                extracted_text = None
                for result in results:
                    for box in result.boxes.xyxy:
                        roi = extract_roi(frame, box)
                        if roi is None or roi.size == 0:
                            continue

                        processed_roi = preprocess_for_ocr(roi)
                        extracted_text = extract_takt_message(processed_roi)

                # Decta o fim da etapa de um takt
                if extracted_text and on_event:
                    now = time.time()

                    # Trata reconhecimento de tela da takt aberto (sem reconhecer fim de takt) - Faz check a cada 5 segundos
                    if (
                        isinstance(extracted_text, dict)
                        and extracted_text.get("event") == "takt_screen"
                    ):
                        if (
                            last_takt_screen_check is None
                            or (now - last_takt_screen_check) > 5
                        ):
                            # logger.debug("Tela de takt detectada (sem fim de etapa)")
                            # Notifica a UI que a tela de takt está aberta
                            on_event(
                                "takt_screen_detected",
                                {"message": extracted_text.get("message")},
                            )
                            last_takt_screen_check = now
                        await asyncio.sleep(0.5)
                        continue

                    if last_sent_message is None or (
                        time.time() - last_message_time > 2
                    ):
                        last_sent_message = extracted_text
                        last_message_time = now

                        # Atualiza o contador de detecções
                        takt_tracker_count = update_takt_count(takt_tracker_count)
                        logger.info(
                            f"Contador de takt atualizado: {takt_tracker_count}/3"
                        )

                        match takt_tracker_count:
                            case 1:
                                print("\n")
                                logger.info(">>> Primeira detecção de Takt (1/3)")
                                on_event(
                                    "takt_detected",
                                    {
                                        "takt": takt_tracker_count,
                                    },
                                )

                            case 2:
                                print("\n")
                                logger.info(">>> Segunda detecção de Takt (2/3)")
                                on_event(
                                    "takt_detected",
                                    {
                                        "takt": takt_tracker_count,
                                    },
                                )
                            case 3:
                                print("\n")
                                logger.info(
                                    ">>> Terceira detecção de Takt (3/3) - Talão completo!"
                                )
                                on_event(
                                    "takt_detected",
                                    {
                                        "takt": takt_tracker_count,
                                    },
                                )

                        # Envia a mensagem para o RabbitMQ
                        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                        extracted_text.update({"id": DEVICE_ID})
                        extracted_text.update({"timestamp": timestamp})
                        extracted_text.update({"takt_count": takt_tracker_count})
                        await send_message(channel, ROUTING_KEY, extracted_text)

                        if takt_tracker_count >= 3:
                            # reseta contador
                            takt_tracker_count = 0
                    else:
                        logger.debug("Mensagem ignorada (debounce de 2s ativo)")
                        continue

                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(
                    f"✗ Erro durante a execução do loop principal: {e}", exc_info=True
                )
                if on_event:
                    on_event("runtime_error", {"error": str(e)})
                await asyncio.sleep(2)
    finally:
        if connection_created and connection:
            logger.info("Conexão RabbitMQ fechada")
            await connection.close()
    

if __name__ == "__main__":
    try:
        logger.info("Iniciando sistema em modo standalone...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Sistema interrompido pelo usuário (Ctrl+C)")
    except Exception as e:
        logger.error(f"✗ Erro fatal ao iniciar o sistema: {e}", exc_info=True)
