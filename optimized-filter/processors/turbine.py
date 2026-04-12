import json
import time
from data.collectors import DataCollector
from mqtt.client import MQTTPublisher


class TurbineProcessor:
    def __init__(self, collector: DataCollector, publisher: MQTTPublisher, mapping: dict):
        self.collector = collector
        self.publisher = publisher
        self.mapping = mapping
    
    def process(self, unit_id, post_time):
        for turbine in self.mapping.get("turbineHeatRate", []):
            tags = []
            for key, tag_list in turbine.get("realtime", {}).items():
                if isinstance(tag_list, list):
                    tags.extend(tag_list)
            
            if not tags:
                continue
            
            realtime_data = self.collector.get_last_values(tags)
            if realtime_data.empty:
                continue
            
            realtime_dict = realtime_data.to_dict(orient="records")[0]
            
            request_body = {k: v for k, v in realtime_dict.items() if k != "time"}
            request_body["category"] = turbine.get("category", "cogent")
            request_body["load"] = realtime_dict.get(turbine.get("load", [None])[0], 0)
            
            thr_result = self.collector.call_efficiency_api("thr", request_body)
            if thr_result:
                for key, tag in turbine.get("outputs", {}).items():
                    value = thr_result.get(key, 0)
                    datapoints = [[post_time, round(value, 4)]]
                    self.publisher.publish_datapoints(tag, datapoints, {"type": "turbine"})


class BoilerProcessor:
    def __init__(self, collector: DataCollector, publisher: MQTTPublisher, mapping: dict):
        self.collector = collector
        self.publisher = publisher
        self.mapping = mapping
    
    def process(self, unit_id, post_time):
        for boiler in self.mapping.get("boilerEfficiency", []):
            fuel_proximate = boiler.get("fuelProximate", {})
            fuel_tags = []
            for key, tag in fuel_proximate.items():
                if isinstance(tag, list) and tag:
                    fuel_tags.append(tag[0])
            
            if fuel_tags:
                proximate_data = self.collector.get_last_values(fuel_tags)
                if not proximate_data.empty:
                    request_body = proximate_data.to_dict(orient="records")[0]
                    request_body["type"] = boiler.get("type", "type1")
                    ultimate_result = self.collector.call_efficiency_api("proximatetoultimate", request_body)
            
            realtime_tags = []
            for key, tag in boiler.get("realtime", {}).items():
                if isinstance(tag, list) and tag:
                    realtime_tags.append(tag[0])
            
            if not realtime_tags:
                continue
            
            realtime_data = self.collector.get_last_values(realtime_tags)
            if realtime_data.empty:
                continue
            
            realtime_dict = realtime_data.to_dict(orient="records")[0]
            
            request_body = {k: v for k, v in realtime_dict.items() if k != "time"}
            request_body.update(boiler.get("assumptions", {}))
            request_body["type"] = boiler.get("type", "type1")
            
            boiler_result = self.collector.call_efficiency_api("boiler", request_body)
            if boiler_result:
                for key, tag in boiler.get("outputs", {}).items():
                    value = boiler_result.get(key, 0)
                    datapoints = [[post_time, round(value, 4)]]
                    self.publisher.publish_datapoints(tag, datapoints, {"type": "boiler"})