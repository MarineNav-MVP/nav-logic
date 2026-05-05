# FusionCore Module

Модуль слияния данных от радара, навигационных датчиков и видеоаналитики.

## Задача
https://github.com/MarineNav-MVP/fusion-core/issues/2

## MQTT брокер
`localhost:1883`

## Архитектура

FusionCore работает как конвейер обработки данных:

```
Радар (sensors/radar/targets) ─┐
                               ├──► Выбор цели (мин. TCPA) ─► PTZ команда
GPS/Компас (sensors/nmea/raw) ─┘                                 │
                                                                 ▼
Камера остановлена (camera/status) ─► CV-детекция ─► Fusion результат
                                                                 │
                                                                 ▼
                                                  fusion/tracked_objects
```

### Алгоритм работы:

1. **Приём радарных целей** → расчёт TCPA/CPA для каждой цели
2. **Выбор наиболее опасной цели** (минимальный TCPA)
3. **Поворот камеры** → `control/ptz/command` (pan = пеленг цели)
4. **Ожидание остановки камеры** → `camera/status.moving=false`
5. **CV-детекция** → классификация судна через `MaritimeDetector`
6. **Публикация результата** → `fusion/tracked_objects`

## Расчёт метрик

### TCPA (Time to Closest Point of Approach)
Время до кратчайшего сближения (секунды). Рассчитывается по формуле:
```
TCPA = -(R · V_rel) / |V_rel|²
```
где R — вектор относительной позиции, V_rel — вектор относительной скорости.

### CPA (Closest Point of Approach)
Минимальная дистанция сближения (морские мили). Рассчитывается как:
```
CPA = |R + V_rel × TCPA|
```

### Координаты цели
Если радар выдаёт только пеленг и дистанцию, координаты рассчитываются:
```
lat_tgt = lat_own + (distance / 60) × cos(bearing)
lon_tgt = lon_own + (distance / 60) × sin(bearing) / cos(lat_own)
```

## Контракты

### Входные данные

#### `sensors/radar/targets`
Массив целей радара. Формат каждой цели:
```json
[
  {
    "id": "TR01",
    "bearing": 45.2,
    "distance": 2.5,
    "course": 180.0,
    "speed": 12.0,
    "timestamp": 1709750000,
    "absolute_position": {
      "lat": 59.9950,
      "lon": 29.7800
    }
  }
]
```

#### `sensors/nmea/raw`
Данные своего судна (GPS, курс, скорость):
```json
{
  "lat": 59.9343,
  "lon": 29.7800,
  "course": 45.0,
  "speed": 10.0,
  "timestamp": 1709750000
}
```

#### `camera/status`
Статус PTZ камеры:
```json
{
  "pan": 45.0,
  "tilt": -5.0,
  "zoom": 2,
  "moving": false,
  "timestamp": 1709750000
}
```

### Выходные данные

#### `control/ptz/command`
Команда поворота камеры:
```json
{
  "pan": 45.5,
  "tilt": 5.0,
  "zoom": 2,
  "speed": 50,
  "mode": "absolute"
}
```

| Поле  | Тип   | Диапазон        | Описание                        |
|-------|-------|-----------------|---------------------------------|
| pan   | float | -180 ... +180   | Горизонтальный угол (градусы)   |
| tilt  | float | -45 ... +45     | Вертикальный угол (градусы)     |
| zoom  | int   | 1 ... 10        | Кратность увеличения            |
| speed | int   | 1 ... 100       | Скорость поворота (%)           |
| mode  | str   | absolute/relative/stop | Режим управления         |

#### `fusion/tracked_objects`
Объединённые данные (радар + CV):
```json
[
  {
    "id": "TR01",
    "timestamp": "2026-04-16T10:30:00+00:00",
    "position": {
      "lat": 59.9950,
      "lon": 29.7800,
      "bearing": 45.2,
      "distance_nm": 2.5
    },
    "motion": {
      "course": 180.0,
      "speed_knots": 12.0,
      "cpa_nm": 0.35,
      "tcpa_minutes": 8.5
    },
    "classification": {
      "type": "Sailing",
      "confidence": 0.82,
      "source": "cv"
    },
    "risk": {
      "cpa_nm": 0.35,
      "tcpa_minutes": 8.5,
      "is_dangerous": true
    }
  }
]
```

| Поле                    | Тип    | Описание                                    |
|-------------------------|--------|---------------------------------------------|
| id                      | str    | Уникальный идентификатор цели               |
| timestamp               | str    | Время публикации (ISO 8601 UTC)             |
| position.lat            | float  | Широта цели                                 |
| position.lon            | float  | Долгота цели                                |
| position.bearing        | float  | Пеленг цели (градусы)                       |
| position.distance_nm    | float  | Дистанция до цели (морские мили)            |
| motion.course           | float  | Курс цели (градусы)                         |
| motion.speed_knots      | float  | Скорость цели (узлы)                        |
| motion.cpa_nm           | float  | Кратчайшее сближение (морские мили)         |
| motion.tcpa_minutes     | float  | Время до сближения (минуты)                 |
| classification.type     | str    | Тип судна: Sailing, Power-driven, Fishing...|
| classification.confidence| float | Уверенность классификации (0..1)            |
| classification.source   | str    | Источник: "cv" или "mock"                   |
| risk.is_dangerous       | bool   | Цель опасна (CPA < 0.5нм И TCPA < 10мин)    |

## Требования

* Python 3.8+
* MQTT брокер (Mosquitto)

### Основные зависимости
```
paho-mqtt>=2.0.0
numpy>=1.24.0
python-dotenv>=1.0.0
```

### CV-детекция (опционально)
Если модели cv-core-main доступны, fusion-core загружает `MaritimeDetector`:
```
ultralytics>=8.0.0
torch>=2.0.0
torchvision>=0.15.0
opencv-python>=4.8.0
pillow>=10.0.0
```

## Запуск модуля

```bash
cd "fusion-core"
python -m venv venv
source venv/Scripts/activate  # Windows
source venv/bin/activate      # Linux/macOS
pip install -r requirements.txt
python main.py
```

## Запуск теста

1. Запустите Mosquitto: `mosquitto -v`
2. Запустите sensor-bridge
3. Запустите fusion-core (см. выше)
4. Запустите тест в отдельном терминале:

```bash
cd "fusion-core"
venv\Scripts\activate
python test.py
```

## Настройка параметров безопасности

В `settings.py` можно изменить:

| Параметр                  | По умолчанию | Описание                                |
|---------------------------|--------------|-----------------------------------------|
| SAFETY_RADIUS_NM          | 0.5          | Допустимый радиус безопасности (нм)     |
| TCPA_THRESHOLD_SECONDS    | 600          | Порог TCPA (10 минут)                   |
| PTZ_TILT_DEG              | 5.0          | Заглушка для tilt (пока не используется)|
| PTZ_ZOOM_DEFAULT          | 2            | Зум по умолчанию                        |
| PTZ_SPEED                 | 50           | Скорость поворота камеры (%)            |

## Контракт CV-детекции

FusionCore вызывает `MaritimeDetector.process_image()` из `cv-core-main`.

Возвращаемые типы судов:
| Тип            | Описание                              |
|----------------|---------------------------------------|
| Power-driven   | Судно под мотором                     |
| Sailing        | Парусное судно                        |
| Fishing        | Рыболовное судно                      |
| NUC            | Не управляется (Not Under Command)    |
| RAM            | Стеснено маневром (Restricted Ability)|
| CBD            | Стеснено осадкой (Constrained Draught)|
