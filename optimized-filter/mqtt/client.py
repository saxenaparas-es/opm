import paho.mqtt.client as mqtt
import json
import time
import requests


class MQTTPublisher:
    def __init__(self, broker_address, port, username, password, client_id="optimized_filter", kairos_url=None, unit_id=None):
        self.broker_address = broker_address
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.kairos_url = kairos_url
        self.unit_id = unit_id or ""
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
    
    def publish_to_kairos(self, metric_name, datapoints, tags=None):
        if not self.kairos_url:
            return None
        
        body = [{"name": metric_name, "datapoints": datapoints, "tags": tags or {}}]
        
        try:
            res = requests.post(self.kairos_url, json=body)
            return res.json() if res.status_code == 200 else None
        except:
            pass
        return None
    
    def publish_asset_manager(self, metric_name, datapoints, tags_dict: dict):
        if not self.kairos_url:
            body = [{"name": metric_name, "datapoints": datapoints, "tags": tags_dict}]
            return self.publish("kairoswriteexternal", json.dumps(body))
        
        body = [{"name": metric_name, "datapoints": datapoints, "tags": tags_dict}]
        
        try:
            res = requests.post(self.kairos_url, json=body)
            return res.json() if res.status_code == 200 else None
        except:
            pass
        return None
    
    def publish_with_relationship(self, metric_name, datapoints, tags_dict: dict, related_to: list):
        tags_dict["relatedTo"] = json.dumps(related_to)
        return self.publish_asset_manager(metric_name, datapoints, tags_dict)
    
    def close(self):
        self.client.loop_stop()
        self.client.disconnect()
    
    def post_query_method(self, combos, asset_manager_config, boiler_config, post_time):
        calc_type = ["actual", "design", "bperf"]
        
        for combo in combos:
            for k, v in combo.get("relationship", {}).items():
                related_to = []
                for v2 in v:
                    system_name = boiler_config.get("systemName", "")
                    output_key = boiler_config.get("outputs", {}).get(v2, "")
                    if system_name and output_key:
                        related_to.append(asset_manager_config.get(system_name, {}).get(output_key, ""))
                
                metric_name = f"{self.unit_id}_{boiler_config.get('systemName', 'boiler')}_asset_manager"
                tags_dict = {
                    "dataTagId": "-",
                    "parameter": k,
                    "measureUnit": "-",
                    "calculationType": calc_type[combos.index(combo)] if combo in combos else "actual"
                }
                tags_dict["relatedTo"] = json.dumps(related_to)
                
                datapoints = [[post_time, round(combo.get(k), 3)]]
                body = [{"name": metric_name, "datapoints": datapoints, "tags": tags_dict}]
                self.publish("kairoswriteexternal", json.dumps(body))