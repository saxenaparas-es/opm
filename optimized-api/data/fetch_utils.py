from optimized_api._imports import requests, time, pd, Dict, Any, List, Optional
from datetime import datetime
import os


def get_heatrates(unit_id: str) -> List[Dict]:
    try:
        config = {}
        url = config.get('api', {}).get('meta', '') + f'/units/{unit_id}/heatrates'
        res = requests.get(url)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return []


def get_forms(unit_id: str) -> List[Dict]:
    try:
        config = {}
        url = config.get('api', {}).get('meta', '') + f'/units/{unit_id}/forms?filter={{"where":{{"name":"Savings"}}}}'
        res = requests.get(url)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return []


def get_gauge_calcs(tags: List[str], start_time: int, end_time: int) -> Dict:
    return {}


def get_simple_cumulative(tags: List[str], start_time: int, end_time: int, calendar_year: str, measure_unit_dict: Dict) -> Dict:
    return {}


def get_running_cumulative(tags: List[str], start_time: int, end_time: int, calendar_year: str, measure_unit_dict: Dict) -> Dict:
    return {}


def get_measure_unit(tags: List[str]) -> Dict:
    return {}

config = {}


def init_config(cfg):
    global config
    config = cfg


def get_last_values(taglist: List[str], end_absolute: int = 0) -> pd.DataFrame:
    end_time = int((time.time() * 1000) + (5.5 * 60 * 60 * 1000))
    if end_absolute != 0:
        query = {"metrics": [], "start_absolute": 1, "end_absolute": end_time}
    else:
        query = {"metrics": [], "start_absolute": 1, "end_absolute": end_time}
    for tag in taglist:
        query["metrics"].append({"name": tag, "order": "desc", "limit": 1})
    try:
        res = requests.post(config.get('api', {}).get('query', ''), json=query).json()
        df = pd.DataFrame([{"time": res["queries"][0]["results"][0]["values"][0][0]}])
        for tag in res["queries"]:
            try:
                if df.iloc[0, 0] < tag["results"][0]["values"][0][0]:
                    df.iloc[0, 0] = tag["results"][0]["values"][0][0]
                df.loc[0, tag["results"][0]["name"]] = tag["results"][0]["values"][0][1]
            except:
                pass
    except Exception:
        return pd.DataFrame()
    return df


def get_proximate_data(fuel_proximate: Dict, loi: Dict, blr: Dict) -> pd.DataFrame:
    if not fuel_proximate:
        return pd.DataFrame()
    tags = [fuel_proximate["coalFC"][0], fuel_proximate["coalVM"][0], 
            fuel_proximate["coalAsh"][0], fuel_proximate["coalMoist"][0]]
    if "coalGCV" in fuel_proximate:
        tags.append(fuel_proximate["coalGCV"][0])
    df = get_last_values(tags)
    if not df.empty and "time" in df.columns:
        df["time"] = loi.get("loi", [None])[0] if loi.get("loi") else None
    return df


def get_ultimate_data(fuel_ultimate: Dict, loi: Dict, blr: Dict) -> pd.DataFrame:
    if not fuel_ultimate:
        return pd.DataFrame()
    tags = [fuel_ultimate["carbon"][0], fuel_ultimate["hydrogen"][0],
            fuel_ultimate["nitrogen"][0], fuel_ultimate["oxygen"][0],
            fuel_ultimate["coalAsh"][0], fuel_ultimate["coalSulphur"][0],
            fuel_ultimate["coalMoist"][0]]
    df = get_last_values(tags)
    if not df.empty and "time" in df.columns:
        df["time"] = loi.get("loi", [None])[0] if loi.get("loi") else None
    return df


def get_boiler_realtime_data(realtime: Dict) -> pd.DataFrame:
    if not realtime:
        return pd.DataFrame()
    tags = list(realtime.values())
    return get_last_values(tags)


def get_threshold(data_tag_id: str) -> Optional[float]:
    try:
        url = config.get('api', {}).get('meta', '') + f'/equipmentData?filter={{"where":{{"dataTagId":"{data_tag_id}"}}}}'
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json()
            if data and len(data) > 0:
                return float(data[0].get("threshold", 0))
    except:
        pass
    return None


def get_data_epoch(tag_list: List[str], start_time: int, end_time: int) -> pd.DataFrame:
    try:
        import ts_client as ts
        qr = ts.timeseriesquery()
        qr.addMetrics(tag_list)
        qr.chooseTimeType("absolute", {"start_absolute": str(start_time), "end_absolute": str(end_time)})
        qr.submitQuery()
        qr.formatResultAsDF()
        if len(qr.resultset["results"]) > 0:
            return qr.resultset["results"][0]["data"]
    except:
        pass
    return pd.DataFrame()


def get_heatrates(unit_id: str) -> List[Dict]:
    try:
        url = config.get('api', {}).get('meta', '') + f'/units/{unit_id}/heatrates'
        res = requests.get(url)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return []


def get_forms(unit_id: str) -> List[Dict]:
    try:
        url = config.get('api', {}).get('meta', '') + f'/units/{unit_id}/forms?filter={{"where":{{"name":"Savings"}}}}'
        res = requests.get(url)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return []


def fetch_efficiency_mapping(unit_id: str) -> List[Dict]:
    try:
        url = config.get('api', {}).get('meta', '') + f'/boilerStressProfiles?filter={{"where":{{"type":"efficiencyMapping", "unitsId":"{unit_id}"}}}}'
        res = requests.get(url)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return []


def get_month_start_time_in_epoch() -> int:
    current_date = datetime.now()
    start_of_month = current_date.replace(day=1, minute=0, hour=0, second=0)
    return int(((int(start_of_month.timestamp())) * 1000) - (5.5 * 3600 * 1000))


def get_year_start_time_in_epoch() -> int:
    current_date = datetime.now()
    start_of_year = current_date.replace(month=1, day=1)
    return int((start_of_year.timestamp() / 1000) * 1000)