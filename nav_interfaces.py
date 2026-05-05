# nav_interfaces.py - Единый контракт данных MarineNav 3
# Этот файл является эталоном для Разработчика Симуляции и Разработчика Логики.
# Любые изменения должны быть согласованы обеими сторонами.

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict


class VesselStatus(Enum):
    """Статусы судов согласно МППСС-72 (Правила 3, 18, 27, 28)"""
    NORMAL = "normal"               # Моторное судно (MECH)
    SAILING = "sailing"             # Парусное судно
    FISHING = "fishing"             # Судно, занятое ловом рыбы
    NUC = "nuc"                     # Лишенное возможности управляться
    RAM = "ram"                     # Ограниченное в возможности маневрировать
    CBD = "cbd"                     # Стесненное своей осадкой
    TOWING = "towing"               # Судно, занятое буксировкой


class EncounterType(Enum):
    """Типы ситуаций сближения (Раздел II МППСС-72)"""
    CLEAR = "clear"
    HEAD_ON = "head_on"             # Лобовое сближение (Правило 14)
    CROSSING_STARBOARD = "crossing_starboard"  # Пересечение (цель справа, Правило 15)
    CROSSING_PORT = "crossing_port"            # Пересечение (цель слева)
    OVERTAKING = "overtaking"       # Обгон (Правило 13)


class ManeuverObligation(Enum):
    """Обязанности сторон (Правила 16, 17)"""
    STAND_ON = "stand_on"           # Сохранять курс и скорость
    GIVE_WAY = "give_way"           # Уступить дорогу


@dataclass
class VesselDimensions:
    """Габариты судна (Правила 3, 9)"""
    length_m: float
    width_m: float
    draft_m: float = 0.0


@dataclass
class EnvironmentState:
    """Состояние внешней среды (Правила 6, 19, 12)"""
    visibility_nm: float            # Дальность видимости в морских милях
    is_night: bool
    wind_true_dir: float = 0.0      # Истинное направление ветра (0-360)
    wind_true_speed_kn: float = 0.0 # Скорость ветра в узлах
    depth_under_keel_m: float = 99.0


@dataclass
class NavContext:
    """Географический и навигационный контекст (Правила 9, 10)"""
    in_channel: bool = False        # В узкости/на фарватере
    in_tss: bool = False            # В системе разделения движения (TSS)
    required_tss_course: Optional[float] = None  # Предписанный курс в полосе TSS
    dist_to_hazard_nm: float = 10.0 # Дистанция до ближайшей навигационной опасности


@dataclass
class VesselState:
    """Полное описание физического состояния любого судна"""
    ship_id: str
    lat: float
    lon: float
    cog: float                      # Course Over Ground (Вектор движения)
    hdg: float                      # Heading (Направление носа - для Aspect Angle)
    speed_kn: float
    status: VesselStatus = VesselStatus.NORMAL
    dimensions: Optional[VesselDimensions] = None


@dataclass
class TargetState(VesselState):
    """Расширенное состояние цели относительно нашего судна"""
    bearing_rel: float = 0.0        # Относительный пеленг
    distance_nm: float = 0.0
    aspect_angle: float = 0.0       # Ракурс (угол между нашим пеленгом и HDG цели)
    cpa_nm: Optional[float] = None
    tcpa_min: Optional[float] = None


@dataclass
class WorldState:
    """Комплексная картина мира (Вход для NavLogic)"""
    timestamp: float
    own_ship: VesselState
    targets: List[TargetState] = field(default_factory=list)
    environment: EnvironmentState = field(default_factory=lambda: EnvironmentState(visibility_nm=10.0, is_night=False))
    nav_context: NavContext = field(default_factory=NavContext)


@dataclass
class ManeuverDirective:
    """Стратегическое решение (Выход RuleEngine -> Вход KinematicSolver)"""
    encounter_type: EncounterType
    obligation: ManeuverObligation
    target_id: Optional[str] = None
    suggested_action: str = "none"  # "alter_starboard", "alter_port", "reduce_speed"
    reasoning: str = ""             # Обоснование (номер правила МППСС)


@dataclass
class ControlCommand:
    """Конечная команда для исполнительных механизмов"""
    action: str                     # "set_course", "set_speed", "stop"
    course: Optional[float] = None
    speed: Optional[float] = None
    horn_signal: Optional[str] = None # "1_short", "5_short" и т.д.
