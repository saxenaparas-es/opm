from data.collectors import DataCollector
from mqtt.client import MQTTPublisher


class TurbineSideProcessor:
    def __init__(self, collector: DataCollector, publisher: MQTTPublisher, unit_id: str):
        self.collector = collector
        self.publisher = publisher
        self.unit_id = unit_id
    
    def process(self, unit_id, post_time):
        try:
            mapping = self.collector.fetch_turbine_side_mapping()
            if not mapping:
                return
            
            config_data = mapping.get("input", {})
            if not config_data:
                return
            
            required_tags = []
            param_names = ["time"]
            for k, v in config_data.items():
                if isinstance(v, list):
                    required_tags.extend(v)
                    param_names.append(k)
            
            if not required_tags:
                return
            
            df = self.collector.get_last_values(required_tags)
            if df.empty:
                return
            
            df.columns = param_names
            
            for k, v in config_data.items():
                if not isinstance(v, list):
                    df[k] = v
            
            api_body = df.to_dict(orient="records")[0]
            
            result = self.collector.call_efficiency_api("turbineSide", api_body)
            
            if result:
                for k, v in result.items():
                    if k != "time":
                        metric_name = f"HRD_3_{k}"
                        datapoints = [[result.get("time", post_time), round(v, 4)]]
                        self.publisher.publish_datapoints(metric_name, datapoints, {"type": "raw"})
                        self.publisher.publish_to_kairos(metric_name, datapoints, {"type": "raw"})
        
        except Exception as e:
            pass