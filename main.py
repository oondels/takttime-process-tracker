import os
import aio_pika
import asyncio
from ultralytics import YOLO
from PIL import ImageGrab
import pytesseract
import cv2
import numpy as np
import json

AMQP_URL = os.getenv("AMQP_URL", "amqp://siren:secret@127.0.0.1/")
AMQP_EXCHANGE = "amq.topic"
DEVICE_ID = os.getenv("DEVICE_ID", "cost-2-2408")
ROUTING_KEY = f"siren.esp32.{DEVICE_ID}"    

pytesseract.pytesseract.tesseract_cmd = r"/usr/bin/tesseract"
model = YOLO("./train_2025.pt")


# TODO: Config RabbitMQ
async def send_message(message):
    pass


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

    if "00:00:10" in text:
        return {"takt_time": "10", "message": "Takt: 10 segundos."}
    elif "00:01:00" in text:
        return {"takt_time": "60", "message": "Takt: 60 segundos."}
    elif "00:00:30" in text:
        return {"takt_time": "30", "message": "Takt: 30 segundos."}
    elif "00:00:05" in text:
        return {"takt_time": "5", "message": "Takt: 5 segundos."}
    elif "00:00:00" in text:
        return {"takt_time": "0", "message": "Takt Liberado!"}


async def main():
    while True:
        screen = ImageGrab.grab()
        screen_np = np.array(screen)

        frame = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)

        # Fazer a predição no frame atual
        results = model.predict(source=frame, stream=False, conf=0.15)

        for result in results:
            for box in result.boxes.xyxy:
                roi = extract_roi(frame, box)
                processed_roi = preprocess_for_ocr(roi)

                # Mostrar a região de interesse
                # cv2.imshow("ROI", processed_roi)

                extracted_text = extract_takt_message(processed_roi)
                if extracted_text:
                    print(extracted_text["message"])
                    
                    # Envia mensagem via RabbitMQ
                    await send_message(extracted_text)

        await asyncio.sleep(0.5)


asyncio.run(main())
