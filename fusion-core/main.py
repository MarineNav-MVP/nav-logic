"""
FusionCore — модуль слияния данных радара, навигации и видеоаналитики.

Алгоритм работы:
1. Подписка на sensors/radar/targets → получение списка целей
2. Подписка на sensors/nmea/raw → данные своего судна (GPS, курс, скорость)
3. Расчёт TCPA для каждой цели → выбор цели с минимальным TCPA
4. Публикация control/ptz/command → поворот камеры к цели
5. Ожидание camera/status.moving=false → отправка запроса в Vision Node (MQTT)
6. Получение ответа от colreg/vision/result → публикация fusion/tracked_objects
"""

import paho.mqtt.client as mqtt
import json
import time
import math
import sys
import os
import shutil
from datetime import datetime, timezone
from settings import *

def calculate_tcpa(own_lat, own_lon, own_course, own_speed,
                   tgt_lat, tgt_lon, tgt_course, tgt_speed):
    """
    Расчёт TCPA (Time to Closest Point of Approach) в секундах.
    """
    try:
        # Переводим градусы в радианы
        own_course_rad = math.radians(own_course)
        tgt_course_rad = math.radians(tgt_course)

        # Разность координат (приближение: 1° широты ≈ 60 морских миль)
        dlat_nm = (tgt_lat - own_lat) * 60.0
        dlon_nm = (tgt_lon - own_lon) * 60.0 * math.cos(math.radians(own_lat))

        # Относительная позиция цели (x — север, y — восток)
        rx = dlat_nm
        ry = dlon_nm

        # Векторы скоростей (узлы → мили/сек)
        own_vx = own_speed * math.cos(own_course_rad) / 3600.0
        own_vy = own_speed * math.sin(own_course_rad) / 3600.0
        tgt_vx = tgt_speed * math.cos(tgt_course_rad) / 3600.0
        tgt_vy = tgt_speed * math.sin(tgt_course_rad) / 3600.0

        # Относительная скорость
        dvx = tgt_vx - own_vx
        dvy = tgt_vy - own_vy

        # Скалярное произведение и квадрат относительной скорости
        dot = rx * dvx + ry * dvy
        speed_sq = dvx * dvx + dvy * dvy

        if speed_sq < 1e-10:
            return None  # Нулевая относительная скорость

        tcpa = -dot / speed_sq
        return tcpa  # Разрешаем отрицательные значения (цель уже прошла)

    except Exception as e:
        print(f"⚠️ Ошибка расчёта TCPA: {e}")
        return None


def calculate_cpa(own_lat, own_lon, own_course, own_speed,
                  tgt_lat, tgt_lon, tgt_course, tgt_speed):
    """
    Расчёт CPA (Closest Point of Approach) в морских милях.
    """
    try:
        tcpa = calculate_tcpa(own_lat, own_lon, own_course, own_speed,
                              tgt_lat, tgt_lon, tgt_course, tgt_speed)
        if tcpa is None:
            # Если относительная скорость нулевая — текущая дистанция
            dlat = (tgt_lat - own_lat) * 60.0
            dlon = (tgt_lon - own_lon) * 60.0 * math.cos(math.radians(own_lat))
            return math.sqrt(dlat**2 + dlon**2)

        # Позиция цели через TCPA секунд
        own_course_rad = math.radians(own_course)
        tgt_course_rad = math.radians(tgt_course)

        own_vx = own_speed * math.cos(own_course_rad) / 3600.0
        own_vy = own_speed * math.sin(own_course_rad) / 3600.0
        tgt_vx = tgt_speed * math.cos(tgt_course_rad) / 3600.0
        tgt_vy = tgt_speed * math.sin(tgt_course_rad) / 3600.0

        # Начальная позиция
        rx = (tgt_lat - own_lat) * 60.0
        ry = (tgt_lon - own_lon) * 60.0 * math.cos(math.radians(own_lat))

        # Относительная скорость
        dvx = tgt_vx - own_vx
        dvy = tgt_vy - own_vy

        # Позиция в момент CPA
        cpa_x = rx + dvx * tcpa
        cpa_y = ry + dvy * tcpa

        return math.sqrt(cpa_x**2 + cpa_y**2)

    except Exception as e:
        print(f"⚠️ Ошибка расчёта CPA: {e}")
        return None


class FusionCore:
    def __init__(self):
        # Состояние системы
        self.own_ship = {
            "lat": None,
            "lon": None,
            "course": 0.0,
            "speed": 0.0,
            "timestamp": None
        }
        self.radar_targets = []
        self.pending_target = None
        self.camera_busy = False
        self.waiting_for_cv = False # Флаг ожидания ответа от нейросети
        self.is_fog = False         # Флаг тумана
        self.last_command_time = 0
        self.min_command_interval = 0.1
        self.current_camera_pan = 0.0
        self.current_camera_zoom = 1

        self.target_history = {}

        # MQTT клиент
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION1,
            client_id="fusion-core"
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("✅ FusionCore подключён к MQTT")
            subscriptions = [
                (TOPIC_RADAR, 1),
                (TOPIC_SENSORS, 1),
                (TOPIC_CAMERA_STATUS, 1),
                (TOPIC_WORLD_STATE, 1), # Следим за туманом
                (TOPIC_CV_RESULT, 1), # Подписка на результаты нового CV
            ]
            for topic, qos in subscriptions:
                self.client.subscribe(topic, qos)
                print(f"   📡 Подписка: {topic}")
        else:
            print(f"❌ Ошибка подключения к MQTT: {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode('utf-8')
            data = json.loads(payload)

            if msg.topic == TOPIC_RADAR:
                self._handle_radar_data(data)
            elif msg.topic == TOPIC_SENSORS:
                self._handle_sensor_data(data)
            elif msg.topic == TOPIC_CAMERA_STATUS:
                self._handle_camera_status(data)
            elif msg.topic == TOPIC_WORLD_STATE:
                self.is_fog = data.get("is_fog", False)
            elif msg.topic == TOPIC_CV_RESULT:
                self._handle_cv_result(data)

        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON ({msg.topic}): {e}")
        except Exception as e:
            print(f"❌ Ошибка обработки сообщения: {e}")

    def _on_publish(self, client, userdata, mid):
        pass

    def _handle_radar_data(self, targets):
        if not targets: return
        self.radar_targets = targets
        for t in targets:
            tid = t.get('id')
            if tid in self.target_history:
                # Сохраняем поля кеша CV перед обновлением данных радара
                cv_data = {k: v for k, v in self.target_history[tid].items() if k.startswith('cv_')}
                self.target_history[tid] = t
                self.target_history[tid].update(cv_data)
            else:
                self.target_history[tid] = t

        # Выбираем наилучшую цель прямо сейчас
        best_target = self._select_best_target(targets)
        if not best_target:
            return

        # Логика ПРЕРЫВАНИЯ: если новая цель лучше текущей, переключаемся сразу
        should_switch = False
        
        if not self.pending_target:
            should_switch = True
        else:
            # Сравниваем текущую и потенциальную цель по Danger Score
            current = self.pending_target
            
            # Мы переключаемся только если новая цель "значительно" опаснее (на 20%)
            # чтобы избежать дребезга камеры между двумя похожими целями
            if best_target.get('danger_score', 9999) < current.get('danger_score', 9999) * 0.8:
                should_switch = True
                print(f"🔄 ПЕРЕКЛЮЧЕНИЕ: Цель {best_target['id']} опаснее, чем {current['id']}")

        if should_switch:
            self.pending_target = best_target
            self.camera_busy = True
            self.waiting_for_cv = False # Сбрасываем ожидание старой цели
            self._send_ptz_command(best_target)
            # print(f"🎯 Наведение: {best_target['id']} (Danger={best_target.get('danger_score', 0):.1f})")

    def _handle_sensor_data(self, data):
        self.own_ship["lat"] = data.get("lat")
        self.own_ship["lon"] = data.get("lon")
        self.own_ship["course"] = data.get("course", 0.0)
        self.own_ship["speed"] = data.get("speed", 0.0)
        self.own_ship["timestamp"] = data.get("timestamp")

    def _handle_camera_status(self, status):
        if not self.camera_busy or self.waiting_for_cv:
            return

        moving = status.get('moving', True)
        if not moving and self.pending_target:
            if self.is_fog:
                print("🌫️ ТУМАН → CV недоступно. Использую только данные радара.")
                self._publish_fusion({"type": "Unknown (Fog)", "confidence": 0.0, "source": "radar_only"})
                self.camera_busy = False
                self.pending_target = None
                return
                
            target_id = self.pending_target.get('id', 'unknown')
            
            # Проверяем кеш классификации
            history = self.target_history.get(target_id, {})
            last_cv_time = history.get('cv_time', 0)
            
            if time.time() - last_cv_time < 20:
                print(f"ℹ️ Использую кешированную классификацию для {target_id} (прошло < 20с)")
                classification = {
                    "type": history.get('cv_class', 'Unknown'),
                    "confidence": history.get('cv_conf', 0.0),
                    "source": "cache"
                }
                self._publish_fusion(classification)
                self.camera_busy = False
                self.pending_target = None
            else:
                self.waiting_for_cv = True
                print(f"✅ Камера остановилась → запрос к Vision Node для {target_id}...")
                self._request_cv_analysis()

    def _request_cv_analysis(self):
        """Отправка запроса на анализ в Vision Node через MQTT"""
        if not self.pending_target: return
        
        target_id = self.pending_target.get('id', 'unknown')
        tgt_type = self.pending_target.get('type', 'power').lower()
        tgt_status = self.pending_target.get('colreg_status', 'NORMAL').upper()
        
        # Симуляция захвата кадра: выбираем "умный" кадр на основе статуса цели
        # Это позволяет тестировать МППСС-72 без реальной камеры
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_filename = f"snap_{target_id}_{timestamp_str}.jpg"
        snapshot_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "snapshots", snapshot_filename))
        
        # Мапинг статусов на реальные тестовые изображения в новом cv-core
        CV_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), CV_CORE_RELATIVE_PATH))
        img_map = {
            "SAILING": os.path.join("day", "sailing.jpg"),
            "NUC": os.path.join("day", "nuc.png"),
            "RAM": os.path.join("day", "ram.png"),
            "CBD": os.path.join("day", "cbd.png"),
            "FISHING": os.path.join("day", "fishing.png")
        }
        
        # Базовый кадр
        sub_path = img_map.get(tgt_status)
        if not sub_path and tgt_type == "sailing":
            sub_path = img_map["SAILING"]
            
        if sub_path:
            base_frame = os.path.join(CV_DIR, "test_images", sub_path)
        else:
            base_frame = os.path.join(os.path.dirname(__file__), "test_frame.jpg")
        
        try:
            if os.path.exists(base_frame):
                shutil.copy(base_frame, snapshot_path)
                print(f"📸 Смарт-кадр захвачен: {snapshot_filename} (Status: {tgt_status})")
            else:
                print(f"⚠️ Кадр не найден: {base_frame}, использую дефолт")
                shutil.copy(os.path.join(os.path.dirname(__file__), "test_frame.jpg"), snapshot_path)
        except Exception as e:
            print(f"⚠️ Ошибка захвата кадра: {e}")
            snapshot_path = os.path.join(os.path.dirname(__file__), "test_frame.jpg")

        command = {
            "request_id": f"req_{target_id}_{int(time.time())}",
            "action": "analyze",
            "source": snapshot_path,
            "is_night": IS_NIGHT_MODE
        }
        
        self._publish(TOPIC_CV_COMMAND, command)
        print(f"📡 Запрос CV отправлен: {command['request_id']} для {target_id}")

    def _handle_cv_result(self, data):
        """Обработка асинхронного результата от Vision Node"""
        if not self.pending_target: return
        
        target_id = self.pending_target.get('id', 'unknown')
        print(f"📥 Получен результат CV: {data.get('status')}")
        
        classification = {"type": "Not detected", "confidence": 0.0, "source": "cv"}
        
        if data.get("status") == "success" and data.get("boats"):
            boat = data["boats"][0]
            classification = {
                "type": boat["vessel_type"],
                "confidence": boat["confidence"],
                "source": "cv_node"
            }
            print(f"✅ CV Node распознал: {classification['type']} ({classification['confidence']})")
            
            # Сохраняем результат в историю для кеширования (на 30 секунд)
            if target_id in self.target_history:
                self.target_history[target_id]['cv_class'] = classification['type']
                self.target_history[target_id]['cv_conf'] = classification['confidence']
                self.target_history[target_id]['cv_time'] = time.time()
        
        self._publish_fusion(classification)
        
        # Сброс состояния для возможности выбора новой цели
        self.camera_busy = False
        self.waiting_for_cv = False
        self.pending_target = None

    def _select_best_target(self, targets):
        if not targets: return None
        own_lat = self.own_ship.get("lat")
        own_lon = self.own_ship.get("lon")
        
        if own_lat is None: return None
        
        best_target = None
        min_danger_score = float('inf')

        for target in targets:
            abs_pos = target.get('absolute_position', {})
            tgt_lat = abs_pos.get('lat')
            tgt_lon = abs_pos.get('lon')
            
            if tgt_lat is None or tgt_lon is None: continue

            tcpa = calculate_tcpa(
                own_lat, own_lon, self.own_ship["course"], self.own_ship["speed"],
                tgt_lat, tgt_lon, target.get('course', 0.0), target.get('speed', 0.0)
            )
            cpa = calculate_cpa(
                own_lat, own_lon, self.own_ship["course"], self.own_ship["speed"],
                tgt_lat, tgt_lon, target.get('course', 0.0), target.get('speed', 0.0)
            )

            target['tcpa_seconds'] = tcpa if tcpa is not None else 9999
            target['cpa_nm'] = cpa if cpa is not None else 9.9
            
            # Вычисляем комплексную оценку опасности (Danger Score)
            # Приоритет ТОЛЬКО целям на сближение (TCPA > 0)
            dist = target.get('distance', 10.0)

            if tcpa is not None and tcpa > 0:
                # Группа сближения: чем меньше время и дистанция, тем выше опасность
                danger_score = tcpa + (dist * 50)
            else:
                # Группа отдаления: цель уже не опасна, ставим огромный штраф
                danger_score = 50000 + dist 

            target['danger_score'] = danger_score
            target['is_closing'] = (tcpa is not None and tcpa > 0)

            if danger_score < min_danger_score:
                min_danger_score = danger_score
                best_target = target


        # Если никто не на коллизии, берем просто ближайшего
        if not best_target and targets:
            best_target = min(targets, key=lambda t: t.get('distance', 999))
            best_target['danger_score'] = best_target.get('distance', 999) * 100
            
        return best_target

    def _send_ptz_command(self, target):
        now = time.time()
        if now - self.last_command_time < self.min_command_interval: return
        
        target_bearing = target.get('bearing', 0.0)
        distance_nm = target.get('distance', 1.0)

        # СЛОЙ 1: Dynamic Zoom (Умный зум)
        # Дистанция <= 1 мили: 1x, >= 5 миль: 20x, линейно между ними
        if distance_nm <= 1.0:
            target_zoom = 1
        elif distance_nm >= 5.0:
            target_zoom = 20
        else:
            target_zoom = int(1 + ((distance_nm - 1.0) / 4.0) * 19)

        # СЛОЙ 2: Lazy Tracking (Мертвая зона)
        # FOV ~ 60 / zoom. Мертвая зона = 40% от полу-поля обзора.
        current_fov = 60.0 / target_zoom
        deadzone_half = current_fov * 0.4
        
        # Разница углов (кратчайший путь)
        diff = (target_bearing - self.current_camera_pan + 180) % 360 - 180
        
        # Если цель в мертвой зоне и зум совпадает — не крутим моторы
        if abs(diff) < deadzone_half and self.current_camera_zoom == target_zoom:
            if not self.waiting_for_cv:
                print(f"🎯 Lazy Tracking: Цель {target['id']} в кадре. Анализируем...")
                self.waiting_for_cv = True
                self._request_cv_analysis()
            return

        command = {
            "pan": round(target_bearing, 1),
            "tilt": PTZ_TILT_DEG,
            "zoom": target_zoom,
            "speed": PTZ_SPEED,
            "mode": "absolute"
        }
        
        self.current_camera_pan = target_bearing
        self.current_camera_zoom = target_zoom
        
        self._publish(TOPIC_PTZ_COMMAND, command)
        self.last_command_time = now

    def _publish_fusion(self, classification):
        target = self.pending_target
        if not target: return
        abs_pos = target.get('absolute_position', {})
        tcpa = target.get('tcpa_seconds', 0.0)
        cpa = target.get('cpa_nm', 0.0)

        fusion_object = {
            "id": target.get('id', 'unknown'),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "position": {
                "lat": abs_pos.get('lat', 0.0),
                "lon": abs_pos.get('lon', 0.0),
                "bearing": target.get('bearing', 0.0),
                "distance_nm": target.get('distance', 0.0)
            },
            "motion": {
                "course": target.get('course', 0.0),
                "speed_knots": target.get('speed', 0.0),
                "cpa_nm": round(cpa, 3) if cpa != float('inf') else None,
                "tcpa_minutes": round(tcpa / 60.0, 2) if tcpa != float('inf') else None
            },
            "classification": classification,
            "risk": {
                "cpa_nm": round(cpa, 3) if cpa != float('inf') else None,
                "tcpa_minutes": round(tcpa / 60.0, 2) if tcpa != float('inf') else None,
                "is_dangerous": (cpa < SAFETY_RADIUS_NM) and (tcpa < TCPA_THRESHOLD_SECONDS)
            }
        }
        self._publish(TOPIC_FUSION, [fusion_object])

    def _publish(self, topic, data):
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        self.client.publish(topic, payload)

    def start(self):
        print("=" * 50)
        print("🚀 Запуск FusionCore (Async CV Mode)...")
        print(f"   MQTT: {MQTT_HOST}:{MQTT_PORT}")
        print("=" * 50)
        try:
            self.client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            self.client.loop_forever()
        except Exception as e:
            print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    FusionCore().start()
