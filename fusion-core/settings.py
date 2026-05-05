# ==========================================
# FusionCore Configuration
# ==========================================

# Входные топики
TOPIC_VIDEO = "analytics/video/class"
TOPIC_SENSORS = "sensors/nmea/raw"
TOPIC_RADAR = "sensors/radar/targets"
TOPIC_CAMERA_STATUS = "camera/status"
TOPIC_WORLD_STATE = "sensors/world_state"
TOPIC_CV_RESULT = "colreg/vision/result"

# Выходные топики
TOPIC_FUSION = "fusion/tracked_objects"
TOPIC_PTZ_COMMAND = "control/ptz/command"
TOPIC_COMMAND = TOPIC_PTZ_COMMAND  # алиас для обратной совместимости
TOPIC_CV_COMMAND = "colreg/vision/command"  # Новый топик команд для CV

# Настройки системы
IS_NIGHT_MODE = False  # Флаг ночного режима (по умолчанию выкл)

# Настройки MQTT
MQTT_HOST = "localhost"
MQTT_PORT = 1883

# Параметры безопасности
SAFETY_RADIUS_NM = 0.5  # допустимый радиус безопасности (морские мили)
TCPA_THRESHOLD_SECONDS = 600  # порог TCPA (10 минут)

# Параметры PTZ камеры
PTZ_TILT_DEG = 5.0  # заглушка для tilt (пока sensor-bridge не поддерживает)
PTZ_ZOOM_DEFAULT = 2
PTZ_SPEED = 50

# Пути к моделям CV (относительно fusion-core)
CV_CORE_RELATIVE_PATH = "../cv-core"
CV_BINARY_MODEL_NAME = "models/best_model.pth"
CV_SHAPES_MODEL_NAME = "models/best.pt"