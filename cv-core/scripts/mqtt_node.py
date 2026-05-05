import json
import logging
import time
import os
import threading
from typing import Any, Dict

import cv2
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# Импортируем пайплайн из пакета src
import sys
from pathlib import Path

# Добавляем путь к src, чтобы импорты внутри colreg_vision работали
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from colreg_vision.pipeline import VideoAnalyticsPipeline

# Загружаем переменные окружения из корня проекта, если они там есть
# Или из текущей папки
load_dotenv(Path(__file__).parent.parent.parent / "sensor-bridge" / ".env")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ColregVisionNode")

# Конфигурация MQTT из .env с дефолтами
MQTT_BROKER = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC_COMMAND = "colreg/vision/command"
MQTT_TOPIC_RESULT = "colreg/vision/result"


class VisionNode:
    """
    MQTT-адаптер для конвейера видеоаналитики COLREG.
    """

    def __init__(self):
        logger.info("Инициализация конвейера видеоаналитики...")
        self.pipeline = VideoAnalyticsPipeline()
        self.is_ready = False
        
        # Запускаем прогрев в отдельном потоке
        threading.Thread(target=self._warmup_models, daemon=True).start()

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, "colreg_vision_node"
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _warmup_models(self):
        """Фоновый прогрев моделей для исключения задержек при первом запросе."""
        logger.info("🔥 Начинаю фоновый прогрев моделей...")
        try:
            # Путь к тестовому изображению внутри структуры cv-core
            test_img_path = Path(__file__).parent.parent / "test_images" / "day" / "sea.webp"
            if test_img_path.exists():
                dummy_img = cv2.imread(str(test_img_path))
                if dummy_img is not None:
                    self.pipeline.process(dummy_img)
                    logger.info("✅ Модели успешно прогреты и готовы к работе.")
                    self.is_ready = True
                else:
                    logger.warning(f"⚠️ Не удалось прочитать изображение для прогрева: {test_img_path}")
            else:
                logger.warning(f"⚠️ Изображение для прогрева не найдено: {test_img_path}")
                # Если изображения нет, прогрев произойдет на первом реальном кадре
                self.is_ready = True 
        except Exception as e:
            logger.error(f"❌ Ошибка при прогреве моделей: {e}")
            self.is_ready = True # Все равно помечаем как готовый, чтобы не блокировать работу

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: dict,
        reason_code: int,
        properties: Any,
    ) -> None:
        if reason_code == 0:
            logger.info(f"Успешное подключение к MQTT: {MQTT_BROKER}:{MQTT_PORT}")
            client.subscribe(MQTT_TOPIC_COMMAND)
            logger.info(f"Подписка на: {MQTT_TOPIC_COMMAND}")
        else:
            logger.error(f"Ошибка подключения: {reason_code}")

    def _on_message(
        self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage
    ) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            action = payload.get("action")
            if action == "analyze":
                self._handle_analyze_command(payload)
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения: {e}")

    def _handle_analyze_command(self, payload: Dict[str, Any]) -> None:
        request_id = payload.get("request_id", "unknown")
        source = payload.get("source")
        is_night = payload.get("is_night", False)

        if not self.is_ready:
            logger.warning(f"[{request_id}] Модели еще прогреваются, возможна задержка...")

        if not source:
            self._publish_error(request_id, "Missing 'source' in command.")
            return

        logger.info(f"[{request_id}] Анализ: {source} (night={is_night})")
        start_time = time.time()

        try:
            image = cv2.imread(source)
            if image is None:
                self._publish_error(request_id, f"Failed to load image: {source}")
                return

            result = self.pipeline.process(image, is_night=is_night)

            boats_data = []
            for boat in result.boats:
                boats_data.append(
                    {
                        "boat_id": boat.boat_id,
                        "bbox": boat.bbox,
                        "vessel_type": boat.final_vessel_type,
                        "confidence": round(boat.final_vessel_type_confidence, 2),
                    }
                )

            response = {
                "request_id": request_id,
                "status": "success",
                "is_night": result.is_night,
                "boat_count": result.boat_count,
                "boats": boats_data,
                "processing_time_ms": round((time.time() - start_time) * 1000, 2),
            }

            self.client.publish(MQTT_TOPIC_RESULT, json.dumps(response))
            logger.info(f"[{request_id}] Завершено за {response['processing_time_ms']}ms. Найдено: {result.boat_count}")

        except Exception as e:
            logger.error(f"[{request_id}] Ошибка анализа: {e}")
            self._publish_error(request_id, str(e))

    def _publish_error(self, request_id: str, error_message: str) -> None:
        response = {"request_id": request_id, "status": "error", "message": error_message}
        self.client.publish(MQTT_TOPIC_RESULT, json.dumps(response))

    def start(self):
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_forever()
        except KeyboardInterrupt:
            self.client.disconnect()
        except Exception as e:
            logger.error(f"Ошибка запуска: {e}")


if __name__ == "__main__":
    node = VisionNode()
    node.start()
