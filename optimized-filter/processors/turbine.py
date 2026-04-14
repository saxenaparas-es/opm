import json
import time
from data.collectors import DataCollector
from mqtt.client import MQTTPublisher


class TurbineProcessor:
    def __init__(self, collector: DataCollector, publisher: MQTTPublisher, mapping: dict, unit_id: str):
        self.collector = collector
        self.publisher = publisher
        self.mapping = mapping
        self.unit_id = unit_id
        self.topic_line = f"u/{unit_id}/"
        self.plant_heat_rate = {
            "realtime": {
                "turbineHeatRate": [],
                "boilerEfficiency": [],
                "boilerSteamFlow": [],
                "turbineSteamFlow": []
            },
            "design": {
                "turbineHeatRate": [],
                "boilerEfficiency": [],
                "boilerSteamFlow": [],
                "turbineSteamFlow": []
            },
            "bestAchieved": {
                "turbineHeatRate": [],
                "boilerEfficiency": [],
                "boilerSteamFlow": [],
                "turbineSteamFlow": []
            }
        }
    
    def check_threshold(self, turbine: dict, realtime_data: dict) -> bool:
        skip_flag = False
        threshold_tags = []
        threshold_names = {}
        
        if turbine.get("Threshold"):
            for k, v in turbine.get("Threshold", {}).items():
                threshold_tags.append(str(v[0]))
                threshold_names[v[0]] = str(k)
            
            if threshold_tags:
                threshold_data = self.collector.get_last_values(threshold_tags)
                if not threshold_data.empty:
                    threshold_data.rename(columns=threshold_names, inplace=True)
                    threshold = threshold_data.to_dict(orient="records")[0]
                    if threshold and realtime_data.get("load", 0) < threshold.get("load", 0):
                        skip_flag = True
                    if threshold and realtime_data.get("steamFlowMS", 0) < threshold.get("steamFlowMS", 0):
                        skip_flag = True
        
        default_load = realtime_data.get("load", 0)
        default_steam = realtime_data.get("steamFlowMS", 0)
        if default_load and default_load < 1:
            skip_flag = True
        if default_steam and default_steam < 10:
            skip_flag = True
            
        return skip_flag
    
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
            
            skip_flag = self.check_threshold(turbine, realtime_dict)
            if skip_flag:
                continue
            
            load_value = realtime_dict.get(turbine.get("load", [None])[0], 0) if turbine.get("load") else 0
            
            request_body = {k: v for k, v in realtime_dict.items() if k != "time"}
            if turbine.get("constants"):
                request_body.update(turbine["constants"])
            request_body["category"] = turbine.get("category", "cogent")
            request_body["load"] = load_value
            
            design_body = {k: v for k, v in realtime_dict.items() if k != "time"}
            if turbine.get("constants"):
                design_body.update(turbine["constants"])
            design_body["category"] = turbine.get("category", "cogent")
            design_body["load"] = load_value
            
            bp_body = {k: v for k, v in realtime_dict.items() if k != "time"}
            if turbine.get("constants"):
                bp_body.update(turbine["constants"])
            bp_body["category"] = turbine.get("category", "cogent")
            bp_body["load"] = load_value
            
            thr_result = self.collector.call_efficiency_api("thr", request_body)
            thr_design_result = self.collector.call_design_api(turbine, realtime_dict)
            thr_bp_result = self.collector.call_bestachieved_api(turbine, realtime_dict)
            
            if thr_result:
                for key, tag in turbine.get("outputs", {}).items():
                    value = thr_result.get(key, 0)
                    
                    datapoints = [[post_time, round(value, 3)]]
                    self.publisher.publish_datapoints(tag, datapoints, {"type": "heat_rate_hourly"})
                    self.publisher.publish(self.topic_line + tag + '/r', json.dumps([{"r": value, "t": post_time}]))
                    
                    self.publisher.publish_to_kairos(tag, datapoints, {"type": "heat_rate_hourly"})
                    
                    if thr_design_result:
                        des_value = thr_design_result.get(key, 0)
                        des_datapoints = [[post_time, round(des_value, 3)]]
                        des_tag = tag + "_des"
                        self.publisher.publish_datapoints(des_tag, des_datapoints, {"type": "heat_rate_hourly"})
                        self.publisher.publish(self.topic_line + des_tag + '/r', json.dumps([{"r": des_value, "t": post_time}]))
                        self.publisher.publish_to_kairos(des_tag, des_datapoints, {"type": "heat_rate_hourly"})
                    
                    if thr_bp_result:
                        bp_value = thr_bp_result.get(key, 0)
                        bp_datapoints = [[post_time, round(bp_value, 3)]]
                        bp_tag = tag + "_bperf"
                        self.publisher.publish_datapoints(bp_tag, bp_datapoints, {"type": "heat_rate_hourly"})
                        self.publisher.publish(self.topic_line + bp_tag + '/r', json.dumps([{"r": bp_value, "t": post_time}]))
                        self.publisher.publish_to_kairos(bp_tag, bp_datapoints, {"type": "heat_rate_hourly"})
                    
                    if self.mapping.get("plantHeatRate"):
                        self.plant_heat_rate["realtime"]["turbineHeatRate"].append(thr_result.get("turbineHeatRate", 0))
                        self.plant_heat_rate["design"]["turbineHeatRate"].append(des_value if thr_design_result else 0)
                        self.plant_heat_rate["bestAchieved"]["turbineHeatRate"].append(bp_value if thr_bp_result else 0)


class BoilerProcessor:
    def __init__(self, collector: DataCollector, publisher: MQTTPublisher, mapping: dict, unit_id: str):
        self.collector = collector
        self.publisher = publisher
        self.mapping = mapping
        self.unit_id = unit_id
        self.topic_line = f"u/{unit_id}/"
    
    def apply_fuel_config(self, data, fuel_config: dict):
        if not fuel_config:
            return data
        mixture_type = fuel_config.get("mixtureType", "static")
        
        if mixture_type == "dynamic":
            fuel_flow_tags = fuel_config.get("fuelFlow", [])
            if fuel_flow_tags:
                data = data.clip(lower=0)
                total_fuel_flow = data[fuel_flow_tags].sum(axis=1).values[0]
                if total_fuel_flow > 0:
                    data["coalFlow"] = total_fuel_flow
        
        return data
    
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
                    
                    fuel_config = boiler.get("fuelUltimateConfig")
                    if fuel_config:
                        proximate_data = self.apply_fuel_config(proximate_data, fuel_config)
                    
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
            
            design_request = {k: v for k, v in realtime_dict.items() if k != "time"}
            design_request.update(boiler.get("assumptions", {}))
            design_request["type"] = boiler.get("type", "type1")
            
            bp_request = {k: v for k, v in realtime_dict.items() if k != "time"}
            bp_request.update(boiler.get("assumptions", {}))
            bp_request["type"] = boiler.get("type", "type1")
            
            if self.mapping.get("plantHeatRate"):
                self.mapping["plantHeatRate"]["design"] = {
                    "turbineHeatRate": [],
                    "boilerEfficiency": [],
                    "boilerSteamFlow": [],
                    "turbineSteamFlow": []
                }
                self.mapping["plantHeatRate"]["bestAchieved"] = {
                    "turbineHeatRate": [],
                    "boilerEfficiency": [],
                    "boilerSteamFlow": [],
                    "turbineSteamFlow": []
                }
            
            boiler_result = self.collector.call_efficiency_api("boiler", request_body)
            boiler_design_result = self.collector.call_design_api_boiler(boiler, realtime_dict)
            boiler_bp_result = self.collector.call_bestachieved_api_boiler(boiler, realtime_dict)
            
            if boiler_result:
                for key, tag in boiler.get("outputs", {}).items():
                    value = boiler_result.get(key, 0)
                    datapoints = [[post_time, round(value, 3)]]
                    
                    self.publisher.publish_datapoints(tag, datapoints, {"type": "raw"})
                    self.publisher.publish(self.topic_line + tag + '/r', json.dumps([{"r": value, "t": post_time}]))
                    self.publisher.publish_to_kairos(tag, datapoints, {"type": "raw"})
                    
                    metric_name = f"{self.unit_id}_{boiler.get('systemName', 'boiler')}_asset_manager"
                    
                    tags_dict = {
                        "dataTagId": tag,
                        "parameter": tag,
                        "measureUnit": "%",
                        "calculationType": "actual"
                    }
                    self.publisher.publish_asset_manager(metric_name, datapoints, tags_dict)
                    
                    if boiler_design_result:
                        des_value = boiler_design_result.get(key, 0)
                        des_datapoints = [[post_time, round(des_value, 3)]]
                        des_tag = tag + "_des"
                        self.publisher.publish_datapoints(des_tag, des_datapoints, {"type": "raw"})
                        self.publisher.publish(self.topic_line + des_tag + '/r', json.dumps([{"r": des_value, "t": post_time}]))
                        self.publisher.publish_to_kairos(des_tag, des_datapoints, {"type": "raw"})
                        
                        des_dev = value - des_value
                        des_dev_datapoints = [[post_time, round(des_dev, 3)]]
                        des_dev_tag = tag + "_des_dev"
                        self.publisher.publish_datapoints(des_dev_tag, des_dev_datapoints, {"type": "raw"})
                        self.publisher.publish_to_kairos(des_dev_tag, des_dev_datapoints, {"type": "raw"})
                    
                    if boiler_bp_result:
                        bp_value = boiler_bp_result.get(key, 0)
                        bp_datapoints = [[post_time, round(bp_value, 3)]]
                        bp_tag = tag + "_bperf"
                        self.publisher.publish_datapoints(bp_tag, bp_datapoints, {"type": "raw"})
                        self.publisher.publish(self.topic_line + bp_tag + '/r', json.dumps([{"r": bp_value, "t": post_time}]))
                        self.publisher.publish_to_kairos(bp_tag, bp_datapoints, {"type": "raw"})
                        
                        bperf_dev = value - bp_value
                        bperf_dev_datapoints = [[post_time, round(bperf_dev, 3)]]
                        bperf_dev_tag = tag + "_bperf_dev"
                        self.publisher.publish_datapoints(bperf_dev_tag, bperf_dev_datapoints, {"type": "raw"})
                        self.publisher.publish_to_kairos(bperf_dev_tag, bperf_dev_datapoints, {"type": "raw"})
            
            coal_cal_result = self.collector.call_efficiency_api("coalCal", request_body)
            if coal_cal_result and boiler.get("coalCalOutputs"):
                for coal_key, coal_tag in boiler.get("coalCalOutputs", {}).items():
                    coal_value = coal_cal_result.get(coal_key, 0)
                    coal_datapoints = [[post_time, round(coal_value, 3)]]
                    self.publisher.publish_datapoints(coal_tag, coal_datapoints, {"type": "coalcal"})
                    self.publisher.publish_to_kairos(coal_tag, coal_datapoints, {"type": "coalcal"})