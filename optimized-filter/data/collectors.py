import requests
import pandas as pd
import time
import json
import os
import logging

logger = logging.getLogger(__name__)

API_USERNAME = os.environ.get('API_USERNAME', '')
API_PASSWORD = os.environ.get('API_PASSWORD', '')


class DataCollector:
    def __init__(self, config, unit_id):
        self.config = config
        self.unit_id = unit_id
        self.api_meta = config.get('api_meta', '')
        self.api_query = config.get('api_query', '')
        self.efficiency_url = config.get('efficiency_url', '')
        self.auth = (API_USERNAME, API_PASSWORD) if API_USERNAME and API_PASSWORD else None
    
    def get_last_values(self, taglist, end_absolute=0):
        logger.info(f"get_last_values called with tags: {taglist}")
        end_time = int((time.time() * 1000) + (5.5 * 60 * 60 * 1000))
        if end_absolute != 0:
            one_month_ms = 30 * 24 * 60 * 60 * 1000
            start_time = end_time - one_month_ms
            query = {"metrics": [], "start_absolute": start_time, "end_absolute": end_time}
        else:
            query = {"metrics": [], "start_absolute": 1, "end_absolute": end_time}
        
        for tag in taglist:
            query["metrics"].append({"tags": {"type": ["raw", "form", "derived"]}, "name": tag, "order": "desc", "limit": 1})
        
        try:
            logger.info(f"Querying API: {self.api_query}")
            res = requests.post(self.api_query, json=query, auth=self.auth)
            logger.info(f"Query response status: {res.status_code}")
            if res.status_code != 200:
                logger.warning(f"API query failed: {res.text}")
                return pd.DataFrame()
            res_json = res.json()
            if "queries" not in res_json or not res_json["queries"]:
                logger.warning(f"No query results returned")
                return pd.DataFrame()
            df = pd.DataFrame([{"time": res_json["queries"][0]["results"][0]["values"][0][0]}])
            for tag_result in res_json["queries"]:
                try:
                    if df.iloc[0, 0] < tag_result["results"][0]["values"][0][0]:
                        df.iloc[0, 0] = tag_result["results"][0]["values"][0][0]
                    df.loc[0, tag_result["results"][0]["name"]] = tag_result["results"][0]["values"][0][1]
                except Exception as e:
                    logger.warning(f"Error processing tag result: {e}")
            logger.info(f"Returning data with columns: {list(df.columns)}")
            return df
        except Exception as e:
            logger.error(f"get_last_values error: {e}")
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
    
    def check_equipment_status(self, status_tag: str) -> int:
        if not status_tag:
            return 1
        try:
            data = self.get_last_values([status_tag])
            if not data.empty:
                return int(data.iloc[0, -1])
        except:
            pass
        return 1
    
    def fetch_mapping(self):
        try:
            url = f'{self.api_meta}/boilerStressProfiles?filter={{"where":{{"type":"efficiencyMapping", "unitsId":"{self.unit_id}"}}}}'
            res = requests.get(url, auth=self.auth)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.error(f"fetch_mapping error: {e}")
        return []
    
    def fetch_turbine_side_mapping(self):
        try:
            url = f'{self.api_meta}/boilerStressProfiles?filter={{"where":{{"type":"turbineSide", "unitsId":"{self.unit_id}"}}}}'
            res = requests.get(url)
            if res.status_code == 200:
                data = res.json()
                return data[0] if data else {}
        except:
            pass
        return {}
    
    def call_efficiency_api(self, endpoint, payload):
        try:
            url = f'{self.efficiency_url}/{endpoint}'
            logger.info(f"Calling efficiency API: {url} with payload: {payload}")
            res = requests.post(url, json=payload, auth=self.auth)
            logger.info(f"Efficiency API response status: {res.status_code}")
            if res.status_code == 200:
                return res.json()
            else:
                logger.warning(f"Efficiency API returned status {res.status_code}: {res.text}")
        except Exception as e:
            logger.error(f"call_efficiency_api error: {e}")
        return None
    
    def call_design_api(self, turbine: dict, realtime_data: dict):
        try:
            design_payload = {
                "realtime": turbine.get("realtime", {}),
                "loi": {},
                "load": realtime_data.get("load", 0),
                "loadTag": turbine.get("load", [None])[0] if turbine.get("load") else None,
                "realtimeData": realtime_data,
                "unitId": self.unit_id
            }
            url = f'{self.efficiency_url}/design'
            res = requests.post(url, json=design_payload, auth=self.auth)
            if res.status_code == 200:
                result = res.json()
                result["category"] = turbine.get("category", "cogent")
                return result
        except Exception as e:
            logger.error(f"call_design_api error: {e}")
        return None
    
    def call_bestachieved_api(self, turbine: dict, realtime_data: dict):
        try:
            bp_payload = {
                "realtime": turbine.get("realtime", {}),
                "load": realtime_data.get("load", 0),
                "loadTag": turbine.get("load", [None])[0] if turbine.get("load") else None,
                "realtimeData": realtime_data,
                "unitId": self.unit_id
            }
            url = f'{self.efficiency_url}/bestachieved'
            res = requests.post(url, json=bp_payload)
            if res.status_code == 200:
                result = res.json()
                result["category"] = turbine.get("category", "cogent")
                return result
        except:
            pass
        return None
    
    def call_design_api_boiler(self, boiler: dict, realtime_data: dict):
        try:
            design_payload = {
                "realtime": boiler.get("realtime", {}),
                "loi": {},
                "load": realtime_data.get("load", 0),
                "loadTag": boiler.get("load", [None])[0] if boiler.get("load") else None,
                "realtimeData": realtime_data,
                "unitId": self.unit_id
            }
            url = f'{self.efficiency_url}/design'
            res = requests.post(url, json=design_payload)
            if res.status_code == 200:
                return res.json()
        except:
            pass
        return None
    
    def call_bestachieved_api_boiler(self, boiler: dict, realtime_data: dict):
        try:
            bp_payload = {
                "realtime": boiler.get("realtime", {}),
                "load": realtime_data.get("load", 0),
                "loadTag": boiler.get("load", [None])[0] if boiler.get("load") else None,
                "realtimeData": realtime_data,
                "unitId": self.unit_id
            }
            url = f'{self.efficiency_url}/bestachieved'
            res = requests.post(url, json=bp_payload)
            if res.status_code == 200:
                return res.json()
        except:
            pass
        return None
    
    def apply_fuel_config(self, data: pd.DataFrame, fuel_config: dict, tags: list) -> pd.DataFrame:
        if not fuel_config or data.empty:
            return data
        
        mixture_type = fuel_config.get("mixtureType", "static")
        
        if mixture_type == "dynamic":
            fuel_flow = fuel_config.get("fuelFlow", [])
            if fuel_flow:
                try:
                    data[fuel_flow[0]] = data[fuel_flow[0]].clip(lower=0)
                    total_fuel_flow = data[fuel_flow].sum(axis=1).values[0]
                    if total_fuel_flow > 0:
                        data["coalFlow"] = total_fuel_flow
                except:
                    pass
        
        return data
    
    def get_historic_values(self, tag: str, duration_hours: int = 24):
        end_time = int(time.time() * 1000)
        start_time = end_time - (duration_hours * 60 * 60 * 1000)
        
        query = {
            "metrics": [{"name": tag, "order": "desc"}],
            "start_absolute": start_time,
            "end_absolute": end_time
        }
        
        try:
            res = requests.post(self.api_query, json=query).json()
            return res
        except:
            return None
    
    def get_last_value(self, tag: str):
        try:
            df = self.get_last_values([tag])
            if not df.empty:
                return df.iloc[0, -1]
        except:
            pass
        return None
    
    def get_dataTagId_from_meta(self, meta_query_dict: dict):
        try:
            url = f'{self.api_meta}/tagmeta'
            res = requests.get(url, params=meta_query_dict)
            if res.status_code == 200:
                return res.json()
        except:
            pass
        return []
    
    def should_run_as_cron(self) -> bool:
        cron_units = os.getenv("CRON_UNITS", "")
        if not cron_units:
            return False
        return self.unit_id in cron_units.split(",")