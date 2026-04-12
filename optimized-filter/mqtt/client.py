import paho.mqtt.client as mqtt
import json
import time


class MQTTPublisher:
    def __init__(self, broker_address, port, username, password, client_id="optimized_filter"):
        self.broker_address = broker_address
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.client = mqtt.Client(client_id=client_id)
        if username and password:
            self.client.username_pw_set(username, password)
        self.client.on_connect = self._on_connect
        self.client.on_log = self._on_log
        self.connected = False
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
        else:
            self.connected = False
    
    def _on_log(self, client, level, buf):
        pass
    
    def connect(self):
        self.client.connect(self.broker_address, self.port, 120)
        self.client.loop_start()
        time.sleep(1)
        return self.connected
    
    def publish(self, topic, payload):
        if isinstance(payload, dict):
            payload = json.dumps(payload)
        return self.client.publish(topic, payload)
    
    def publish_datapoints(self, metric_name, datapoints, tags=None):
        body = [{"name": metric_name, "datapoints": datapoints, "tags": tags or {}}]
        return self.publish("kairoswriteexternal", json.dumps(body))
    
    def close(self):
        self.client.loop_stop()
        self.client.disconnect()