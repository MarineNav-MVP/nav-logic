# nav_interfaces.py - Контракт между Стратегом и Рулевым

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ManeuverDirective:
    """
    Стратегическое решение от Rule Engine.
    """
    encounter_type: str        # "head_on", "crossing_starboard", "crossing_port", "overtaking", "clear"
    obligation: str            # "stand_on" (сохранять курс), "give_way" (уступать)
    target_id: Optional[str]   # ID судна, с которым расходимся
    safe_cpa_nm: float = 1.0   # Желаемая дистанция расхождения
    suggested_action: str = "none" # "alter_starboard", "alter_port", "reduce_speed"
    priority: int = 0          # Уровень угрозы (0-10)

@dataclass
class WorldState:
    """
    Упрощенная картина мира для NavLogic
    """
    own_ship: dict
    targets: List[dict]
    is_fog: bool = False
    is_night: bool = False
