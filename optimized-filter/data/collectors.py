import requests
import pandas as pd
import time
import json
import os
import logging
from config.logging_utils import (
    logger, log_section, log_variable, log_info, log_warning, log_error,
    log_debug, collector_logger as cl
)

API_USERNAME = os.environ.get('API_USERNAME', '')
API_PASSWORD = os.environ.get('API_PASSWORD', '')


class DataCollector:
    def __init__(self, config, unit_id):
        log_section("INITIALIZING DATA COLLECTOR")
        self.config = config
        self.unit_id = unit_id
        self.api_meta = config.get('api_meta', '')
        self.api_query = config.get('api_query', '')
        self.efficiency_url = config.get('efficiency_url', '')
        self.auth = (API_USERNAME, API_PASSWORD) if API_USERNAME and API_PASSWORD else None
        
        log_variable("unit_id", unit_id)
        log_variable("api_meta", self.api_meta)
        log_variable("api_query", self.api_query)
        log_variable("efficiency_url", self.efficiency_url)
        log_variable("has_auth", self.auth is not None)
    
    def get_last_values(self, taglist, end_absolute=0):
        cl.info(f"{'='*60}")
        cl.info(f"▶ get_last_values START")
        log_variable("tags_count", len(taglist))
        log_variable("tags_list", taglist[:5] if len(taglist) > 5 else taglist)
        
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
            cl.info(f"Querying API: {self.api_query}")
            res = requests.post(self.api_query, json=query, auth=self.auth)
            cl.info(f"Query response status: {res.status_code}")
            if res.status_code != 200:
                log_warning(f"API query failed: {res.text[:200]}")
                return pd.DataFrame()
            res_json = res.json()
            if "queries" not in res_json or not res_json["queries"]:
                log_warning("No query results returned")
                return pd.DataFrame()
            df = pd.DataFrame([{"time": res_json["queries"][0]["results"][0]["values"][0][0]}])
            for tag_result in res_json["queries"]:
                try:
                    if df.iloc[0, 0] < tag_result["results"][0]["values"][0][0]:
                        df.iloc[0, 0] = tag_result["results"][0]["values"][0][0]
                    df.loc[0, tag_result["results"][0]["name"]] = tag_result["results"][0]["values"][0][1]
                except Exception as e:
                    log_warning(f"Error processing tag result: {e}")
            log_variable("result_columns", list(df.columns))
            log_variable("result_shape", df.shape)
            cl.info(f"✓ Returning data with columns: {list(df.columns)}")
            cl.info(f"{'='*60}")
            return df
        except Exception as e:
            log_error(e, "get_last_values")
            return pd.DataFrame()
    
    def get_threshold(self, data_tag_id):
        cl.info(f"get_threshold for tag: {data_tag_id}")
        try:
            url = f'{self.api_meta}/equipmentData?filter={{"where":{{"dataTagId":"{data_tag_id}"}}}}'
            res = requests.get(url)
            if res.status_code == 200:
                data = res.json()
                if data and len(data) > 0:
                    threshold = float(data[0].get("threshold", 0))
                    log_variable("threshold", threshold)
                    return threshold
        except Exception as e:
            log_error(e, "get_threshold")
        return None
    
    def check_equipment_status(self, status_tag: str) -> int:
        if not status_tag:
            return 1
        try:
            data = self.get_last_values([status_tag])
            if not data.empty:
                status = int(data.iloc[0, -1])
                log_variable("equipment_status", status)
                return status
        except Exception as e:
            log_error(e, "check_equipment_status")
        return 1
    
    def fetch_mapping(self):
        cl.info(f"{'='*60}")
        cl.info(f"▶ fetch_mapping START")
        log_variable("unit_id", self.unit_id)
        try:
            url = f'{self.api_meta}/boilerStressProfiles?filter={{"where":{{"type":"efficiencyMapping", "unitsId":"{self.unit_id}"}}}}'
            cl.info(f"Fetching from: {url}")
            res = requests.get(url, auth=self.auth)
            log_variable("response_status", res.status_code)
            if res.status_code == 200:
                data = res.json()
                log_variable("records_count", len(data))
                cl.info(f"✓ fetch_mapping END - Got {len(data)} records")
                cl.info(f"{'='*60}")
                return data
            else:
                log_warning(f"fetch_mapping failed: {res.text[:200]}")
        except Exception as e:
            log_error(e, "fetch_mapping")
        cl.info(f"{'='*60}")
        return []
    
    def fetch_turbine_side_mapping(self):
        cl.info("fetch_turbine_side_mapping")
        try:
            url = f'{self.api_meta}/boilerStressProfiles?filter={{"where":{{"type":"turbineSide", "unitsId":"{self.unit_id}"}}}}'
            res = requests.get(url)
            if res.status_code == 200:
                data = res.json()
                return data[0] if data else {}
        except Exception as e:
            log_error(e, "fetch_turbine_side_mapping")
        return {}
    
    def call_efficiency_api(self, endpoint, payload):
        cl.info(f"{'─'*60}")
        cl.info(f"📤 CALLING EFFICIENCY API: {endpoint}")
        log_variable("payload_keys", list(payload.keys()) if payload else [])
        
        try:
            url = f'{self.efficiency_url}/{endpoint}'
            cl.info(f"URL: {url}")
            log_debug(f"Full payload: {json.dumps(payload)[:500]}...")
            
            res = requests.post(url, json=payload, auth=self.auth, timeout=30)
            cl.info(f"Response status: {res.status_code}")
            
            if res.status_code == 200:
                result = res.json()
                log_variable("result_keys", list(result.keys()) if result else [])
                cl.info(f"✓ API call SUCCESS")
                return result
            else:
                log_warning(f"API returned {res.status_code}: {res.text[:200]}")
        except Exception as e:
            log_error(e, f"call_efficiency_api ({endpoint})")
        cl.info(f"{'─'*60}")
        return None
    
    def call_design_api(self, turbine: dict, realtime_data: dict):
        cl.info("▶ call_design_api START")
        log_variable("turbine_keys", list(turbine.keys()) if turbine else [])
        
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
            cl.info(f"Calling: {url}")
            res = requests.post(url, json=design_payload, auth=self.auth)
            log_variable("response_status", res.status_code)
            
            if res.status_code == 200:
                result = res.json()
                result["category"] = turbine.get("category", "cogent")
                cl.info("✓ call_design_api SUCCESS")
                return result
            else:
                log_warning(f"design API returned {res.status_code}")
        except Exception as e:
            log_error(e, "call_design_api")
        cl.info("◀ call_design_api END")
        return None
    
    def call_bestachieved_api(self, turbine: dict, realtime_data: dict):
        cl.info("▶ call_bestachieved_api START")
        
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
            log_variable("response_status", res.status_code)
            
            if res.status_code == 200:
                result = res.json()
                result["category"] = turbine.get("category", "cogent")
                cl.info("✓ call_bestachieved_api SUCCESS")
                return result
        except Exception as e:
            log_error(e, "call_bestachieved_api")
        cl.info("◀ call_bestachieved_api END")
        return None
    
    def call_design_api_boiler(self, boiler: dict, realtime_data: dict):
        cl.info("▶ call_design_api_boiler START")
        
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
            log_variable("response_status", res.status_code)
            
            if res.status_code == 200:
                result = res.json()
                cl.info("✓ call_design_api_boiler SUCCESS")
                return result
        except Exception as e:
            log_error(e, "call_design_api_boiler")
        cl.info("◀ call_design_api_boiler END")
        return None
    
    def call_bestachieved_api_boiler(self, boiler: dict, realtime_data: dict):
        cl.info("▶ call_bestachieved_api_boiler START")
        
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
            log_variable("response_status", res.status_code)
            
            if res.status_code == 200:
                result = res.json()
                cl.info("✓ call_bestachieved_api_boiler SUCCESS")
                return result
        except Exception as e:
            log_error(e, "call_bestachieved_api_boiler")
        cl.info("◀ call_bestachieved_api_boiler END")
        return None
    
    def apply_fuel_config(self, data: pd.DataFrame, fuel_config: dict, tags: list) -> pd.DataFrame:
        cl.info("▶ apply_fuel_config START")
        log_variable("data_empty", data.empty)
        log_variable("fuel_config_keys", list(fuel_config.keys()) if fuel_config else [])
        
        if not fuel_config or data.empty:
            cl.info("◀ apply_fuel_config END - No config or empty data")
            return data
        
        mixture_type = fuel_config.get("mixtureType", "static")
        log_variable("mixture_type", mixture_type)
        
        if mixture_type == "dynamic":
            fuel_flow = fuel_config.get("fuelFlow", [])
            if fuel_flow:
                try:
                    data[fuel_flow[0]] = data[fuel_flow[0]].clip(lower=0)
                    total_fuel_flow = data[fuel_flow].sum(axis=1).values[0]
                    if total_fuel_flow > 0:
                        data["coalFlow"] = total_fuel_flow
                        log_variable("coalFlow_set", total_fuel_flow)
                except Exception as e:
                    log_error(e, "apply_fuel_config")
        
        cl.info("◀ apply_fuel_config END")
        return data
    
    def get_historic_values(self, tag: str, duration_hours: int = 24):
        cl.info(f"get_historic_values for tag: {tag}, duration: {duration_hours}h")
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
        except Exception as e:
            log_error(e, "get_historic_values")
        return None
    
    def get_last_value(self, tag: str):
        try:
            df = self.get_last_values([tag])
            if not df.empty:
                return df.iloc[0, -1]
        except Exception as e:
            log_error(e, "get_last_value")
        return None
    
    def get_dataTagId_from_meta(self, meta_query_dict: dict):
        try:
            url = f'{self.api_meta}/tagmeta'
            res = requests.get(url, params=meta_query_dict)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            log_error(e, "get_dataTagId_from_meta")
        return []
    
    def should_run_as_cron(self) -> bool:
        cron_units = os.getenv("CRON_UNITS", "")
        if not cron_units:
            return False
        result = self.unit_id in cron_units.split(",")
        log_variable("should_run_as_cron", result)
        return result

    def getTurbineRealtimeData(self, realtime):
        if not realtime:
            return pd.DataFrame()
        tags = []
        for key, tag_list in realtime.items():
            if isinstance(tag_list, list) and tag_list:
                tags.extend(tag_list)
        return self.get_last_values(tags)

    def getProximateDataOld(self, fuelProximate, loi, blr):
        if not fuelProximate:
            return pd.DataFrame()
        tags = []
        for key, tag_list in fuelProximate.items():
            if isinstance(tag_list, list) and tag_list:
                tags.append(tag_list[0])
        return self.get_last_values(tags)

    def getBoilerRealtimeDataOld(self, realtime):
        if not realtime:
            return pd.DataFrame()
        tags = []
        for key, tag_list in realtime.items():
            if isinstance(tag_list, list) and tag_list:
                tags.append(tag_list[0])
        return self.get_last_values(tags)

    def apply_ultimate_config(self, data, fuel, fuel_config):
        if not fuel_config or data.empty:
            return data
        mixture_type = fuel_config.get("mixtureType", "static")
        if mixture_type == "dynamic":
            fuel_flow = fuel_config.get("fuelFlow", [])
            if fuel_flow:
                try:
                    for ff in fuel_flow:
                        if ff in data.columns:
                            data[ff] = data[ff].clip(lower=0)
                    total_fuel_flow = data[fuel_flow].sum(axis=1).values[0]
                    if total_fuel_flow > 0:
                        data["coalFlow"] = total_fuel_flow
                except:
                    pass
        return data

    def get_ultimate_data(self, fuel_ultimate, loi, blr):
        if not fuel_ultimate:
            return pd.DataFrame()
        tags = []
        for key, tag_list in fuel_ultimate.items():
            if isinstance(tag_list, list) and tag_list:
                tags.append(tag_list[0])
        df = self.get_last_values(tags)
        if not df.empty and "time" in df.columns:
            df["time"] = loi.get("loi", [None])[0] if loi.get("loi") else None
        return df

    def get_boiler_realtime_data(self, realtime):
        if not realtime:
            return pd.DataFrame()
        tags = []
        for key, tag_list in realtime.items():
            if isinstance(tag_list, list) and tag_list:
                tags.extend(tag_list)
        return self.get_last_values(tags)


def make_config_for_query_metric(unit_id):
    return {
        "api_meta": os.environ.get('API_META', ''),
        "api_query": os.environ.get('API_QUERY', ''),
        "kairos": os.environ.get('KAIROS_URL', ''),
        "efficiency_url": os.environ.get('EFFICIENCY_URL', '')
    }


def get_dataTagId_from_meta(unit_id, meta_query_dict):
    url = f'{unit_id}/tagmeta'
    try:
        res = requests.get(url, params=meta_query_dict)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return []


# === Missing functions from index-b.py ===

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(f"Connected to MQTT broker successfully")
    else:
        logger.error(f"MQTT connection failed with code {rc}")


def on_log(client, userdata, level, buf):
    logger.debug(f"MQTT Log: {buf}")


def getThreshold(data_tag_id: str):
    from data.collectors import DataCollector
    collector = DataCollector(
        config={'api_meta': os.environ.get('API_META', '')},
        unit_id=''
    )
    return collector.get_threshold(data_tag_id)


def getLastValue(tag: str):
    from data.collectors import DataCollector
    collector = DataCollector(
        config={'api_meta': os.environ.get('API_META', '')},
        unit_id=''
    )
    return collector.get_last_value(tag)


def applyUltimateConfig(data: pd.DataFrame, fuel_config: dict):
    if fuel_config is None or data.empty:
        return data
    mixture_type = fuel_config.get("mixtureType", "static")
    if mixture_type == "dynamic":
        fuel_flow = fuel_config.get("fuelFlow", [])
        if fuel_flow:
            try:
                for ff in fuel_flow:
                    if ff in data.columns:
                        data[ff] = data[ff].clip(lower=0)
                total_fuel_flow = data[fuel_flow].sum(axis=1).values[0]
                if total_fuel_flow > 0:
                    data["coalFlow"] = total_fuel_flow
            except:
                pass
    return data


def getUltimateData(fuel_ultimate: dict, loi: dict, blr: dict):
    from data.collectors import DataCollector
    collector = DataCollector(
        config={'api_meta': os.environ.get('API_META', '')},
        unit_id=''
    )
    if not fuel_ultimate:
        return pd.DataFrame()
    return collector.get_ultimate_data(fuel_ultimate, loi, blr)


def getProximateData(fuelProximate: dict, loi: dict, blr: dict):
    from data.collectors import DataCollector
    collector = DataCollector(
        config={'api_meta': os.environ.get('API_META', '')},
        unit_id=''
    )
    if not fuelProximate:
        return pd.DataFrame()
    return collector.getProximateDataOld(fuelProximate, loi, blr)


def post_query_method(actual_data: dict, design_data: dict, bperf_data: dict, asset_manager_config: dict, boiler_config: dict, post_time: int):
    """Post query results to database."""
    try:
        import qr
        for loss in boiler_config.get("outputs", {}).keys():
            metric_name = f"{boiler_config.get('unitId', '')}_{boiler_config.get('systemName', 'boiler')}_asset_manager"
            tags_dict = {
                "dataTagId": boiler_config["outputs"][loss],
                "parameter": asset_manager_config.get(boiler_config["systemName"], {}).get(boiler_config["outputs"][loss], ""),
                "measureUnit": "%",
                "calculationType": "actual"
            }
            body = [{
                "name": metric_name,
                "datapoints": [[post_time, round(actual_data.get(loss, 0), 3)]],
                "tags": tags_dict
            }]
            qr.postDataPacket(body)
    except Exception as e:
        logger.error(f"Error in post_query_method: {e}")


def getLastValues(taglist: List[str], end_absolute: int = 0) -> pd.DataFrame:
    collector = DataCollector(
        config={'api_meta': os.environ.get('API_META', '')},
        unit_id=''
    )
    return collector.get_last_values(taglist, end_absolute)


def getProximateDataOld(fuel_proximate: dict, loi: dict) -> pd.DataFrame:
    if not fuel_proximate:
        return pd.DataFrame()
    tags = []
    for key, tag_list in fuel_proximate.items():
        if isinstance(tag_list, list) and tag_list:
            tags.append(tag_list[0])
    collector = DataCollector(
        config={'api_meta': os.environ.get('API_META', '')},
        unit_id=''
    )
    return collector.get_last_values(tags)


def getTurbineRealtimeData(realtime: dict) -> pd.DataFrame:
    if not realtime:
        return pd.DataFrame()
    tags = []
    for key, tag_list in realtime.items():
        if isinstance(tag_list, list) and tag_list:
            tags.extend(tag_list)
    collector = DataCollector(
        config={'api_meta': os.environ.get('API_META', '')},
        unit_id=''
    )
    return collector.get_last_values(tags)


def getBoilerRealtimeDataOld(realtime: dict) -> pd.DataFrame:
    return getTurbineRealtimeData(realtime)


def getBoilerRealtimeData(realtime: dict) -> pd.DataFrame:
    return getTurbineRealtimeData(realtime)
