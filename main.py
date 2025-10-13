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
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

AMQP_URL = os.getenv("AMQP_URL", "amqp://siren:secret@127.0.0.1/")
AMQP_EXCHANGE = "amq.topic"
DEVICE_ID = os.getenv("DEVICE_ID", "cost-2-2408")
ROUTING_KEY = f"takt.device.{DEVICE_ID}"

pytesseract.pytesseract.tesseract_cmd = r"/usr/bin/tesseract"
MODEL_PATH = "./train_2025.pt"


def extract_roi(frame, box, pad=5, scale=2):
    x1, y1, x2, y2 = map(int, box)
    # add padding, clamp to image bounds
    x1, y1 = max(x1 - pad, 0), max(y1 - pad, 0)
    x2, y2 = min(x2 + pad, frame.shape[1]), min(y2 + pad, frame.shape[0])
    roi = frame[y1:y2, x1:x2]
    # upscale to improve tiny text
    h, w = roi.shape[:2]
    return cv2.resize(roi, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)


def preprocess_for_ocr(roi_bgr):
    gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th


def extract_takt_message(roi):
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

    if "00:00:00" in text:
        # return {"takt_time": "0", "message": "Takt Liberado!"}
        return 3
    # if "00:00:10" in text:
    #     return {"takt_time": "10", "message": "Takt: 10 segundos."}
    # elif "00:01:00" in text:
    #     return {"takt_time": "60", "message": "Takt: 60 segundos."}
    # elif "00:00:30" in text:
    #     return {"takt_time": "30", "message": "Takt: 30 segundos."}
    # elif "00:00:05" in text:
    #     return {"takt_time": "5", "message": "Takt: 5 segundos."}


# TODO: Config RabbitMQ
async def send_message(channel: aio_pika.Channel, routing_key: str, message_body: dict):
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
        logging.info(f"Mensagem enviada para '{routing_key}': {message_body}")
    except Exception as e:
        logging.error(f"Erro ao enviar mensagem para '{routing_key}': {e}")


async def main():
    logging.info(
        f"Iniciando Sistema de Detecção de Takt-Time para o dispositivo: {DEVICE_ID}"
    )
    logging.info(f"Conectadno ao RabbitMQ em {AMQP_URL}")

    try:
        connection = await aio_pika.connect_robust(AMQP_URL)
    except Exception as e:
        logging.error(
            f"Não foi possível conectar ao RabbitMQ. Verifique o servidor: {e}"
        )
        return

    async with connection:
        channel = await connection.channel()
        logging.info("Conectado ao RabbitMQ com sucesso!")

        logging.info("Carregando modelo YOLO...")
        if not os.path.exists(MODEL_PATH):
            logging.error(f"Modelo não encontrado em {MODEL_PATH}")
            return
        model = YOLO(MODEL_PATH)
        logging.info("Modelo carregado com sucesso!")

        last_message_time = None
        last_sent_message = None
        while True:
            try:
                screen = ImageGrab.grab()
                screen_np = np.array(screen)
                frame = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)

                # Fazer a predição no frame atual
                results = model.predict(source=frame, stream=False, conf=0.15, verbose=False)

                extracted_text = None
                for result in results:
                    for box in result.boxes.xyxy:
                        roi = extract_roi(frame, box)
                        if roi is None or roi.size == 0:
                            continue

                        processed_roi = preprocess_for_ocr(roi)
                        extracted_text = extract_takt_message(processed_roi)

                if extracted_text:
                    now = time.time()
                    if last_sent_message is None or (time.time() - last_message_time > 5):
                        # await send_message(channel, ROUTING_KEY, extracted_text)
                        last_sent_message = extracted_text
                        last_message_time = now
                        print(f"\n\n Mensagem enviada: {extracted_text} \n\n")
                    else:
                        pass

                await asyncio.sleep(0.5)
            except Exception as e:
                logging.error(f"Erro durante a execução: {e}")
                await asyncio.sleep(2)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"Erro ao iniciar o sistema: {e}")
