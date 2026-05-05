import paho.mqtt.client as mqtt, json, time
c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
c.connect('localhost')
# Наше судно сигналит "Поворачиваю вправо"
c.publish('sensors/signals', json.dumps({'action': 'emit', 'type': 'starboard', 'ship_id': 'OWN'}))
time.sleep(1)
# Цель сигналит "ОПАСНОСТЬ!"
c.publish('sensors/signals', json.dumps({'action': 'emit', 'type': 'danger', 'ship_id': 'TGT_NUC_02'}))