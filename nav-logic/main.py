# main.py - Точка входа NavLogic (Автономный мозг)

import paho.mqtt.client as mqtt
import json
import time
from nav_interfaces import WorldState
from rule_engine import RuleEngine
from kinematic_solver import KinematicSolver

# Настройки MQTT
MQTT_HOST = "localhost"
TOPIC_WORLD_STATE = "sensors/world_state"
TOPIC_STEERING = "control/ship/steering"

class NavLogic:
    def __init__(self):
        self.rule_engine = RuleEngine()
        self.solver = KinematicSolver()
        
        self.client = mqtt.Client(client_id="nav-logic")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        print("🧠 NavLogic: Подключено к брокеру")
        self.client.subscribe(TOPIC_WORLD_STATE)

    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            
            # Формируем объект состояния
            state = WorldState(
                own_ship=data.get("own_ship"),
                targets=data.get("tracked_targets", []),
                is_fog=data.get("environment", {}).get("is_fog", False)
            )
            
            # 1. Анализируем ситуацию (Разработчик 1)
            directive = self.rule_engine.analyze(state)
            
            # 2. Решаем задачу движения (Разработчик 2)
            command = self.solver.solve(state, directive)
            
            # 3. Публикуем команду, если она есть
            if command:
                self.client.publish(TOPIC_STEERING, json.dumps(command))
                print(f"🚢 NavLogic -> Steering: {command}")
                
        except Exception as e:
            print(f"❌ Ошибка в NavLogic: {e}")

    def run(self):
        self.client.connect(MQTT_HOST, 1883)
        self.client.loop_forever()

if __name__ == "__main__":
    NavLogic().run()
