from _imports import requests, time, pd, Dict, Any, List, Optional, datetime, os


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


def get_last_values_time_wise(taglist: List[str], start_time: int, end_time: int, end_absolute: int = 0) -> pd.DataFrame:
    taglist = list(filter(lambda tag: tag.lower() != "time", taglist))
    if end_absolute != 0:
        query = {"metrics": [], "start_absolute": start_time, "end_absolute": end_time}
    else:
        query = {"metrics": [], "start_absolute": 1, "end_absolute": end_time}
    for tag in taglist:
        query["metrics"].append({
            "name": tag,
            "aggregators": [{"name": "last", "sampling": {"value": "3", "unit": "months"}, "align_sampling": True}],
            "order": "desc",
            "limit": 1
        })
    try:
        res = requests.post(config.get('api', {}).get('query', ''), json=query).json()
        df = pd.DataFrame([{"time": res["queries"][0]["results"][0]["values"][0][0]}])
        for tag in res["queries"]:
            try:
                if tag["results"][0]["values"]:
                    if df.iloc[0, 0] < tag["results"][0]["values"][0][0]:
                        df.iloc[0, 0] = tag["results"][0]["values"][0][0]
                    df.loc[0, tag["results"][0]["name"]] = tag["results"][0]["values"][0][1]
                else:
                    df.loc[0, tag["results"][0]["name"]] = 0
            except Exception:
                pass
    except Exception:
        return pd.DataFrame()
    return df


def get_historic_values(taglist: Dict[str, List], start_time: int, end_time: int) -> pd.DataFrame:
    tags, names = [], {}
    for i, j in taglist.items():
        tags.append(str(j[0]))
        names[str(j[0])] = str(i)
    queries = {}
    metrics = []
    var = {
        "tags": {},
        "name": "",
        "aggregators": [
            {"name": "filter", "filter_op": "lte", "threshold": "0"},
            {"name": "avg", "sampling": {"value": "1", "unit": "hours"}, "align_start_time": True}
        ],
    }
    for tag in tags:
        query_metric = var.copy()
        query_metric["name"] = tag
        metrics.append(query_metric)
    query = {"metrics": metrics, "start_absolute": start_time, "end_absolute": end_time}
    
    try:
        res = requests.post(config.get('api', {}).get('query', ''), json=query).json()
        merged_df = pd.DataFrame()
        for query_result in res.get('queries', []):
            try:
                if query_result.get("results") and query_result["results"]:
                    tag_name = query_result["name"]
                    values = query_result["results"][0].get("values", [])
                    if values:
                        temp_df = pd.DataFrame(values, columns=["time", tag_name])
                        if merged_df.empty:
                            merged_df = temp_df
                        else:
                            merged_df = merged_df.merge(temp_df, on="time", how="outer")
            except Exception:
                pass
        merged_df = merged_df.sort_values("time")
        return merged_df
    except Exception:
        return pd.DataFrame()


def fetch_tags(unit_id: str) -> List[str]:
    mapping_url = config.get('api', {}).get('meta', '') + f'/units/{unit_id}/boilerStressProfiles?filter={{"where":{{"type":"efficiencyMapping"}}}}'
    
    try:
        res = requests.get(mapping_url)
        if res.status_code == 200 and len(res.json()) != 0:
            mapping_file = res.json()[0]
            mapping = mapping_file.get("output", {})
        else:
            return []
    except Exception:
        return []
    
    tags = []
    for item in mapping.get("boilerEfficiency", []):
        for i, j in item.get("realtime", {}).items():
            if str(i) != "ambientAirTemp":
                tags.extend(j)
    
    if mapping.get("turbineHeatRate"):
        for item in mapping.get("turbineHeatRate", []):
            for i in item.get("realtime", {}).values():
                tags.extend(i)
    
    ld_tags = []
    api_meta = config.get('api', {}).get('meta', '')
    for tag in tags:
        url = f'{api_meta}/units/{unit_id}/tagmeta?filter={{"where":{{"dataTagId":"{tag}"}},"fields":["equipmentId"]}}'
        try:
            res = requests.get(url)
            if res.status_code == 200 and len(res.json()):
                equip_id = res.json()[0].get("equipmentId")
                url = f'{api_meta}/units/{unit_id}/equipment/{equip_id}'
                res = requests.get(url)
                if res.status_code == 200 and len(res.json()):
                    load = res.json().get("equipmentLoad", {}).get("loadTag")
                    if load:
                        ld_tags.append(load)
        except Exception:
            pass
    
    tags = tags + ld_tags
    tags = [tag[0] if isinstance(tag, list) else tag for tag in tags]
    tags = list(set(tags))
    return tags


def get_prefix(unit_id: str) -> str:
    return f"u/{unit_id}/"


def fetch_data(unit_id: str) -> Dict:
    mapping_url = config.get('api', {}).get('meta', '') + f'/units/{unit_id}/boilerStressProfiles?filter={{"where":{{"type":"efficiencyMapping"}}}}'
    try:
        res = requests.get(mapping_url)
        if res.status_code == 200:
            return res.json()[0]
    except Exception:
        pass
    return {}


def get_current_month_and_year() -> tuple:
    now = datetime.now()
    return now.month, now.year


def date_to_epoch_milliseconds(year: int, month: int, day: int) -> int:
    dt = datetime(year, month, day)
    return int(dt.timestamp() * 1000)


def get_duration_in_months(start_time: int, end_time: int) -> int:
    start_dt = datetime.fromtimestamp(start_time / 1000)
    end_dt = datetime.fromtimestamp(end_time / 1000)
    return (end_dt.year - start_dt.year) * 12 + end_dt.month - start_dt.month


def get_end_date(month_number: int) -> datetime:
    now = datetime.now()
    if month_number < 12:
        return datetime(now.year, month_number + 1, 1)
    return datetime(now.year + 1, 1, 1)


def get_single_day_data(tag: str, start_time: int, end_time: int) -> pd.DataFrame:
    query = {
        "metrics": [{"name": tag, "aggregators": [{"name": "avg", "sampling": {"value": "1", "unit": "days"}}],
        "start_absolute": start_time,
        "end_absolute": end_time
    }
    try:
        res = requests.post(config.get('api', {}).get('query', ''), json=query).json()
        if res.get("queries"):
            values = res["queries"][0].get("results", [{}])[0].get("values", [])
            return pd.DataFrame(values, columns=["time", tag])
    except Exception:
        pass
    return pd.DataFrame()


def get_single_day_data_2(tag: str, start_time: int, end_time: int) -> pd.DataFrame:
    return get_single_day_data(tag, start_time, end_time)


def get_monthly_simple_cumulative_data(tag: str, start_time: int, end_time: int) -> pd.DataFrame:
    return pd.DataFrame()


def get_yearly_simple_cumulative_data(tag: str, start_time: int, end_time: int, calender_year: str) -> pd.DataFrame:
    return pd.DataFrame()


def get_monthly_running_cumulative_data(tag: str, start_time: int, end_time: int, calender_year: str) -> pd.DataFrame:
    return pd.DataFrame()


def get_yearly_running_cumulative_data(tag: str, start_time: int, end_time: int, calender_year: str) -> pd.DataFrame:
    return pd.DataFrame()


def calculate_cumulative_sum(data: pd.DataFrame, start_date: datetime) -> float:
    try:
        filtered = data[data["time"] >= start_date.timestamp()]
        return filtered.iloc[:, 1].sum() if len(filtered) > 0 else 0
    except Exception:
        return 0


def handle_limits_of_tagmeta(tag_meta: List[Dict]) -> List[Dict]:
    if not tag_meta:
        return []
    filtered = []
    for tag in tag_meta:
        tag_id = tag.get("dataTagId", "")
        if tag_id and len(tag_id) > 3:
            filtered.append(tag)
    return filtered