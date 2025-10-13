import websockets
import asyncio
from ultralytics import YOLO
from PIL import ImageGrab
import pytesseract
import cv2

pytesseract.pytesseract.tesseract_cmd = (
    r"/usr/bin/tesseract"
)
cap = cv2.VideoCapture("./utils/takt_menor.mp4")
# model = YOLO("./dataset/runs/detect/train/weights/best.pt")
model = YOLO("./train_2025.pt")

async def send_message(message):
    pass


async def main():
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Fazer a predição no frame atual
        results = model.predict(source=frame, stream=False, conf=0.15)

        # Para cada resultado, desenhar a caixa delimitadora e extrair a região de interesse
        for result in results:
            for box in result.boxes.xyxy:
                x1, y1, x2, y2 = map(int, box[:4])
                roi = frame[y1:y2, x1:x2]

                # Mostrar a região de interesse
                cv2.imshow("ROI", roi)

                # Usando pytesseract para extração do texto
                texto_extraido = pytesseract.image_to_string(roi)
                texto_extraido = texto_extraido.strip()

                if (
                    texto_extraido == """TAKT TIME\n00:00:00"""
                    or texto_extraido == """TAKT TIME\n\n00:00:00"""
                    or texto_extraido == """TART TIME\n\n00:00:00"""
                    or texto_extraido == """TAKT TIME\n\n"""
                    or texto_extraido == """TART TIME\n\n"""
                    or texto_extraido == """TAKT TIME\n"""
                    or texto_extraido == """TART TIME\n"""
                ):
                    print("Takt Time detected")
                    cap.release()
                    cv2.destroyAllWindows()
                    return

                # Pressionar 'q' para sair
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    cap.release()
                    cv2.destroyAllWindows()
                    return

        await asyncio.sleep(0.1)  # Pequeno delay para não sobrecarregar o sistema


asyncio.run(main())
