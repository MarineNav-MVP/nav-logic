# core/world_map.py - Улучшенная модель поверхности для Архангельска

from typing import List, Tuple

class WorldMap:
    """
    Улучшенная модель мира. Использует систему разрешенных (вода) 
    и запрещенных (суша) полигонов.
    """
    
    # Основная акватория Двинского залива (ГДЕ МОЖНО СПАВНИТЬ)
    WHITE_SEA_WATER = [
        (64.38, 38.04),
        (64.80, 37.80),
        (65.10, 38.50),
        (65.40, 39.50),
        (65.60, 40.50),
        (65.30, 41.50),
        (64.90, 40.50), # Западнее Архангельска
        (64.65, 40.10), # Устье Северной Двины
        (64.55, 39.80), # Северодвинск
        (64.40, 39.00)
    ]

    # Острова и дельта (ГДЕ НЕЛЬЗЯ СПАВНИТЬ - Суша)
    # Пятно Архангельск + Острова дельты
    ARKHANGELSK_LAND = [
        (64.63, 40.40),
        (64.75, 40.45),
        (64.75, 40.80),
        (64.50, 40.85),
        (64.45, 40.55)
    ]

    # Пятно Северодвинск + берег
    SEVERODVINSK_LAND = [
        (64.50, 39.70),
        (64.60, 39.70),
        (64.60, 39.95),
        (64.50, 39.95)
    ]

    @staticmethod
    def is_point_in_poly(lat: float, lon: float, polygon: List[Tuple[float, float]]) -> bool:
        """Алгоритм Ray Casting"""
        n = len(polygon)
        inside = False
        p1x, p1y = polygon[0][1], polygon[0][0]
        for i in range(n + 1):
            p2x, p2y = polygon[i % n][1], polygon[i % n][0]
            if lat > min(p1y, p2y):
                if lat <= max(p1y, p2y):
                    if lon <= max(p1x, p2x):
                        if p1y != p2y:
                            xints = (lat - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or lon <= xints:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    @classmethod
    def is_water(cls, lat: float, lon: float) -> bool:
        """
        Проверка: точка должна быть в 'Белом море' И НЕ в 'Зонах суши'.
        """
        # Если мы в районе Архангельска
        if 64.0 <= lat <= 66.0 and 37.0 <= lon <= 42.0:
            # 1. Должно быть в воде
            if not cls.is_point_in_poly(lat, lon, cls.WHITE_SEA_WATER):
                return False
            
            # 2. Не должно быть на суше Архангельска
            if cls.is_point_in_poly(lat, lon, cls.ARKHANGELSK_LAND):
                return False
                
            # 3. Не должно быть на суше Северодвинска
            if cls.is_point_in_poly(lat, lon, cls.SEVERODVINSK_LAND):
                return False
            
            return True
        
        # Дефолт для открытого моря
        return True
