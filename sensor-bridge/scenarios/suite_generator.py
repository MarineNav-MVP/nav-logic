import json
import os
import math

SCENARIOS_DIR = "colreg_suite"
BASE_PATH = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(BASE_PATH, SCENARIOS_DIR)

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def generate_scenario(id, name, rule, description, own_ship, targets, expected):
    scenario = {
        "id": id,
        "name": name,
        "rule": rule,
        "description": description,
        "own_ship": own_ship,
        "targets": targets,
        "expected_outcome": expected
    }
    filename = f"{id}.json"
    with open(os.path.join(OUTPUT_DIR, filename), 'w', encoding='utf-8') as f:
        json.dump(scenario, f, indent=2, ensure_ascii=False)
    return filename

# --- ГЕНЕРАЦИЯ БАЗОВОЙ ГЕОМЕТРИИ (Level 1) ---

# 1. Head-On (Правило 14)
generate_scenario(
    "S1_HeadOn", "Head-On Situation", "Rule 14",
    "Встречное сближение. Оба судна должны отвернуть вправо.",
    {"id": "OWN", "course": 0, "speed": 10, "start": {"lat": 60.0, "lon": 30.0}},
    [{"id": "TGT_01", "type": "power", "colreg_status": "NORMAL", "course": 180, "speed": 10, "start": {"lat": 60.05, "lon": 30.0}}],
    {"action": "ALTER_COURSE_RIGHT", "reason": "Head-on collision risk"}
)

# 2. Crossing (Give-way) - Цель справа (Правило 15)
generate_scenario(
    "S2_Crossing_Right", "Crossing (Give-Way)", "Rule 15",
    "Пересечение курсов, цель справа. Мы обязаны уступить дорогу.",
    {"id": "OWN", "course": 0, "speed": 10, "start": {"lat": 60.0, "lon": 30.0}},
    [{"id": "TGT_01", "type": "power", "colreg_status": "NORMAL", "course": 270, "speed": 10, "start": {"lat": 60.03, "lon": 30.05}}],
    {"action": "ALTER_COURSE_RIGHT", "reason": "Give way to vessel on starboard"}
)

# 3. Crossing (Stand-on) - Цель слева (Правило 17)
generate_scenario(
    "S3_Crossing_Left", "Crossing (Stand-On)", "Rule 17",
    "Пересечение курсов, цель слева. Мы сохраняем курс и скорость.",
    {"id": "OWN", "course": 0, "speed": 10, "start": {"lat": 60.0, "lon": 30.0}},
    [{"id": "TGT_01", "type": "power", "colreg_status": "NORMAL", "course": 90, "speed": 10, "start": {"lat": 60.03, "lon": 29.95}}],
    {"action": "KEEP_COURSE", "reason": "Stand-on vessel (target on port side)"}
)

# 4. Overtaking (Правило 13)
generate_scenario(
    "S4_Overtaking", "Overtaking", "Rule 13",
    "Мы догоняем более медленное судно. Обязаны держаться в стороне.",
    {"id": "OWN", "course": 0, "speed": 15, "start": {"lat": 60.0, "lon": 30.0}},
    [{"id": "TGT_01", "type": "power", "colreg_status": "NORMAL", "course": 0, "speed": 5, "start": {"lat": 60.02, "lon": 30.0}}],
    {"action": "ALTER_COURSE_ANY", "reason": "Overtaking vessel must keep clear"}
)

# --- ГЕНЕРАЦИЯ ИЕРАРХИИ (Level 2) ---

statuses = ["SAILING", "NUC", "RAM", "CBD", "FISHING"]
for status in statuses:
    generate_scenario(
        f"S5_Priority_{status}", f"Priority: {status}", "Rule 18",
        f"Цель слева, но имеет статус {status}. Мы обязаны уступить дорогу.",
        {"id": "OWN", "course": 0, "speed": 10, "start": {"lat": 60.0, "lon": 30.0}},
        [{"id": "TGT_01", "type": status.lower() if status=="SAILING" else "power", 
          "colreg_status": status, "course": 90, "speed": 5, "start": {"lat": 60.03, "lon": 29.95}}],
        {"action": "ALTER_COURSE_RIGHT", "reason": f"Give way to {status} vessel"}
    )

# --- ГЕНЕРАЦИЯ ТУМАНА (Level 3 - Rule 19) ---

generate_scenario(
    "S6_Fog_HeadOn", "Fog: Head-On", "Rule 19",
    "Встречное сближение в тумане. Действия только по радару.",
    {"id": "OWN", "course": 0, "speed": 5, "start": {"lat": 60.0, "lon": 30.0}},
    [{"id": "TGT_01", "type": "power", "colreg_status": "NORMAL", "course": 180, "speed": 5, "start": {"lat": 60.05, "lon": 30.0}}],
    {"action": "ALTER_COURSE_RIGHT", "is_fog": True, "reason": "Restricted visibility maneuvering"}
)

# --- СТАТИЧЕСКИЕ ОБЪЕКТЫ (Rule 30) ---

generate_scenario(
    "S7_Anchored", "Vessel at Anchor", "Rule 30",
    "Судно на якоре прямо по курсу. Обязаны обойти.",
    {"id": "OWN", "course": 0, "speed": 10, "start": {"lat": 60.0, "lon": 30.0}},
    [{"id": "TGT_01", "type": "power", "colreg_status": "ANCHORED", "course": 0, "speed": 0, "start": {"lat": 60.03, "lon": 30.0}}],
    {"action": "ALTER_COURSE_RIGHT", "reason": "Avoid stationary object"}
)

# --- ГРУППОВЫЕ КОНФЛИКТЫ (Level 4 - Complex) ---

# 1. Hammer and Anvil (Молот и Наковальня)
generate_scenario(
    "S8_Hammer_Anvil", "Hammer & Anvil", "Rule 18 + 15",
    "Справа катер (уступаем), слева парусник (ТОЖЕ уступаем). Тупиковая ситуация для простого маневра.",
    {"id": "OWN", "course": 0, "speed": 10, "start": {"lat": 60.0, "lon": 30.0}},
    [
        {"id": "TGT_POWER_R", "type": "power", "colreg_status": "NORMAL", "course": 270, "speed": 10, "start": {"lat": 60.03, "lon": 30.05}},
        {"id": "TGT_SAIL_L", "type": "sailing", "colreg_status": "NORMAL", "course": 90, "speed": 6, "start": {"lat": 60.03, "lon": 29.95}}
    ],
    {"action": "REDUCE_SPEED_OR_DEEP_RIGHT", "reason": "Complex priority conflict (Power on right, Sail on left)"}
)

# 2. Roundabout (Тройное сближение)
generate_scenario(
    "S9_Triple_Threat", "Triple Conflict", "Rule 15 Multi",
    "Три судна сходятся в точку под углом 120°. Каждое должно уступать.",
    {"id": "OWN", "course": 0, "speed": 10, "start": {"lat": 60.0, "lon": 30.0}},
    [
        {"id": "TGT_1", "type": "power", "colreg_status": "NORMAL", "course": 240, "speed": 10, "start": {"lat": 60.04, "lon": 30.04}},
        {"id": "TGT_2", "type": "power", "colreg_status": "NORMAL", "course": 120, "speed": 10, "start": {"lat": 60.04, "lon": 29.96}}
    ],
    {"action": "ALTER_COURSE_RIGHT", "reason": "Multi-vessel crossing"}
)

# 3. Blind Overtaking (Обгон с помехой)
generate_scenario(
    "S10_Blind_Overtake", "Blind Overtake", "Rule 13 + 14",
    "Обгоняем медленное судно, а из-за него выходит встречное.",
    {"id": "OWN", "course": 0, "speed": 15, "start": {"lat": 60.0, "lon": 30.0}},
    [
        {"id": "TGT_SLOW", "type": "power", "colreg_status": "NORMAL", "course": 0, "speed": 5, "start": {"lat": 60.02, "lon": 30.0}},
        {"id": "TGT_HEADON", "type": "power", "colreg_status": "NORMAL", "course": 180, "speed": 10, "start": {"lat": 60.06, "lon": 30.01}}
    ],
    {"action": "ABORT_OVERTAKE", "reason": "Hazard detected during overtaking"}
)

print(f"✅ Успешно сгенерировано {len(os.listdir(OUTPUT_DIR))} сценариев в {SCENARIOS_DIR}")
