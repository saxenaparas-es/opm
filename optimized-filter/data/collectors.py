import requests
import pandas as pd
import time


class DataCollector:
    def __init__(self, config, unit_id):
        self.config = config
        self.unit_id = unit_id
        self.api_meta = config.get('api_meta', '')
        self.api_query = config.get('api_query', '')
    
    def get_last_values(self, taglist):
        end_time = int((time.time() * 1000) + (5.5 * 60 * 60 * 1000))
        query = {"metrics": [], "start_absolute": 1, "end_absolute": end_time}
        for tag in taglist:
            query["metrics"].append({"name": tag, "order": "desc", "limit": 1})
        try:
            res = requests.post(self.api_query, json=query).json()
            df = pd.DataFrame([{"time": res["queries"][0]["results"][0]["values"][0][0]}])
            for tag in res["queries"]:
                try:
                    if df.iloc[0, 0] < tag["results"][0]["values"][0][0]:
                        df.iloc[0, 0] = tag["results"][0]["values"][0][0]
                    df.loc[0, tag["results"][0]["name"]] = tag["results"][0]["values"][0][1]
                except:
                    pass
            return df
        except:
            return pd.DataFrame()
    
    def get_threshold(self, data_tag_id):
        try:
            url = f'{self.api_meta}/equipmentData?filter={{"where":{{"dataTagId":"{data_tag_id}"}}}}'
            res = requests.get(url)
            if res.status_code == 200:
                data = res.json()
                if data and len(data) > 0:
                    return float(data[0].get("threshold", 0))
        except:
            pass
        return None
    
    def fetch_mapping(self):
        try:
            url = f'{self.api_meta}/boilerStressProfiles?filter={{"where":{{"type":"efficiencyMapping", "unitsId":"{self.unit_id}"}}}}'
            res = requests.get(url)
            if res.status_code == 200:
                return res.json()
        except:
            pass
        return []
    
    def call_efficiency_api(self, endpoint, payload):
        try:
            url = f'{self.config.get("efficiency_url", "")}/{endpoint}'
            res = requests.post(url, json=payload)
            if res.status_code == 200:
                return res.json()
        except:
            pass
        return None