import math
import random
import time
from typing import List, Optional
from core.ship_state import ShipState, Position
from core.world_map import WorldMap

def get_destination_point(pos: Position, distance_nm: float, bearing_deg: float) -> Position:
    """Вычисляет новую позицию на основе начальной, расстояния и пеленга."""
    lat1 = math.radians(pos.lat)
    lon1 = math.radians(pos.lon)
    bearing = math.radians(bearing_deg)
    
    # 1 градус широты ≈ 60 морских миль
    delta_lat = (distance_nm * math.cos(bearing)) / 60.0
    # 1 градус долготы ≈ 60 * cos(lat) морских миль
    delta_lon = (distance_nm * math.sin(bearing)) / (60.0 * math.cos(lat1))
    
    return Position(lat=pos.lat + delta_lat, lon=pos.lon + delta_lon)

class ChaosEngine:
    """
    Генератор процедурного трафика ("Бесконечный Океан").
    Создает опасные ситуации сближения в реальном времени.
    """
    
    def __init__(self, min_targets: int = 4, max_targets: int = 8):
        self.min_targets = min_targets
        self.max_targets = max_targets
        self.spawn_radius_nm = 7.0  # Уменьшили с 12 до 7, чтобы было видно на карте
        self.despawn_radius_nm = 12.0
        self.target_counter = 0
        
        # Вероятности статусов МППСС
        self.status_weights = {
            "NORMAL": 70,
            "SAILING": 10,
            "FISHING": 10,
            "NUC": 5,
            "RAM": 5
        }

    def update(self, own_ship: ShipState, current_targets: list, dt: float):
        """Обновление популяции судов."""
        # 1. Удаление слишком далеких целей
        to_remove = []
        for target in current_targets:
            dist = own_ship.position.distance_to(target.position)
            if dist > self.despawn_radius_nm:
                to_remove.append(target)
        
        for t in to_remove:
            current_targets.remove(t)
            print(f"🌊 ChaosEngine: Судно {t.id} ушло за горизонт.")

        # 2. Спавн новых целей, если их мало
        while len(current_targets) < self.min_targets:
            new_target = self._generate_intercept_target(own_ship)
            if new_target:
                current_targets.append(new_target)
                print(f"🚢 ChaosEngine: Сгенерирована цель {new_target.id} ({new_target.colreg_status})")
            else:
                # Если не удалось найти место на воде, выходим из цикла, чтобы не зависнуть
                break

    def _generate_intercept_target(self, own_ship: ShipState):
        """Генерирует судно, курс которого пересекается с нашим в будущем."""
        
        # Попытки найти место на воде (макс 10)
        spawn_pos = None
        for attempt in range(10):
            # Спавним цель на границе радиуса
            spawn_bearing = (own_ship.course + random.uniform(-90, 90)) % 360
            candidate_pos = get_destination_point(own_ship.position, self.spawn_radius_nm, spawn_bearing)
            
            if WorldMap.is_water(candidate_pos.lat, candidate_pos.lon):
                spawn_pos = candidate_pos
                break
            else:
                if attempt == 0:
                    print(f"🏜️ ChaosEngine: Попытка спавна на суше ({candidate_pos.lat:.2f}, {candidate_pos.lon:.2f}), ищу воду...")

        if not spawn_pos:
            return None

        self.target_counter += 1
        target_id = f"CH_{self.target_counter:03d}"
        
        # 1. Выбираем точку перехвата (Interception Point)
        # Впереди нашего судна на 2-5 миль
        intercept_dist = random.uniform(2.0, 5.0)
        # С небольшим отклонением от курса (-20 до +20 градусов), чтобы не всегда Head-on
        intercept_bearing = (own_ship.course + random.uniform(-20, 20)) % 360
        intercept_pos = get_destination_point(own_ship.position, intercept_dist, intercept_bearing)
        
        # 2. Рассчитываем время до точки (TTI)
        if own_ship.speed < 1.0:
            tti_hours = 0.5 # Дефолт 30 мин если мы стоим
        else:
            tti_hours = intercept_dist / own_ship.speed
            
        # 4. Вычисляем параметры движения цели, чтобы она попала в точку перехвата за TTI
        dist_to_intercept = spawn_pos.distance_to(intercept_pos)
        target_speed = dist_to_intercept / tti_hours
        
        # Ограничиваем скорость разумными пределами (5 - 25 узлов)
        target_speed = max(5.0, min(25.0, target_speed))
        
        # Направление от точки спавна к точке перехвата
        target_course = spawn_pos.bearing_to(intercept_pos)
        
        # 5. Рандомизируем статус
        status = random.choices(
            list(self.status_weights.keys()), 
            weights=list(self.status_weights.values())
        )[0]
        
        # Импорт здесь чтобы избежать циклической зависимости
        from scenarios.loader import MovingTarget
        
        return MovingTarget(
            target_id=target_id,
            position=spawn_pos,
            course=target_course,
            speed=target_speed,
            ship_type="sailing" if status == "SAILING" else "power",
            colreg_status=status
        )
