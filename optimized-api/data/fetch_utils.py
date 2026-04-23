from _imports import requests, time, pd, Dict, Any, List, Optional, datetime, os


# === Missing utility functions from index-api.py ===

def replace_with_description(data_dict: Dict, description_dict: Dict) -> Dict:
    """Replace dictionary keys with description mappings."""
    updated_dict = {}
    for key, value in data_dict.items():
        if key in description_dict:
            updated_dict[description_dict[key]] = value
        else:
            updated_dict[key] = value
    return updated_dict


def add_hr_reconciliation(result_dict: Dict) -> Dict:
    """Add heat rate reconciliation calculations."""
    before = result_dict.get("before_turbine_heat_rate", 0.0)
    after = result_dict.get("after_turbine_heat_rate", 0.0)
    actual_diff = after - before
    
    accounted_sum = sum(
        v for k, v in result_dict.items()
        if k not in ["before_turbine_heat_rate", "after_turbine_heat_rate"]
    )
    
    result_dict["unaccountedLoss"] = actual_diff - accounted_sum
    
    before_val = result_dict.pop("before_turbine_heat_rate", None)
    after_val = result_dict.pop("after_turbine_heat_rate", None)
    
    if before_val is not None:
        result_dict["before_turbine_heat_rate"] = before_val
    if after_val is not None:
        result_dict["after_turbine_heat_rate"] = after_val
    
    return result_dict


def getPrefix(unitId: str) -> str:
    """Get unit prefix from API."""
    url = config.get("api", {}).get("meta", "") + f'/ingestconfigs?filter={{"where":{{"unitsId":"{unitId}"}}}}'
    try:
        res = requests.get(url)
        if res.status_code == 200 and res.json():
            return res.json()[0].get("TAG_PREFIX", "")
    except:
        pass
    return ""


def updateform(form: str) -> int:
    """Update form data via API."""
    form_data = {"id": form.get("id")}
    if "id" in form:
        del form["id"]
    update_url = config.get("api", {}).get("meta", "") + f'/forms/update?where={{"id":"{form_data.get("id")}"}}'
    try:
        res = requests.post(update_url, json=form)
        return res.status_code
    except:
        return 500


def getHistoricValues(taglist: List, startTime: int, endTime: int) -> pd.DataFrame:
    """Fetch historical values for tags."""
    tags, names = [], {}
    for i, j in taglist.items():
        tags.append(str(j[0]))
        names[str(j[0])] = str(i)
    
    queries = {}
    metrics = []
    var_template = {
        "tags": {},
        "name": "",
        "aggregators": [
            {"name": "filter", "filter_op": "lte", "threshold": "0"},
            {"name": "avg", "sampling": {"value": "1", "unit": "hours"}, "align_start_time": True}
        ]
    }
    
    def getdata_api(query):
        try:
            res = requests.post(config.get("api", {}).get("query", ""), json=query).json()
            merged_df = pd.DataFrame()
            for query_result in res.get("queries", []):
                tag = query_result["results"][0]["name"]
                listOfList = query_result["results"][0]["values"]
                temp_df = pd.DataFrame(listOfList, columns=["time", tag])
                temp_df["time"] = pd.to_datetime(temp_df["time"], unit="ms", utc=True)
                temp_df.set_index("time", inplace=True)
                
                if merged_df.empty:
                    merged_df = temp_df
                else:
                    merged_df = merged_df.merge(temp_df, how="outer", left_index=True, right_index=True)
            
            merged_df.reset_index(inplace=True)
            return merged_df
        except Exception as e:
            print(f"Error in getHistoricValues: {e}")
            return pd.DataFrame()
    
    for tag in tags:
        var = var_template.copy()
        var["name"] = tag
        metrics.append(var)
    
    queries["metrics"] = metrics
    queries["start_absolute"] = startTime
    queries["end_absolute"] = endTime
    
    result = getdata_api(queries)
    
    if not result.empty:
        result["time"] = pd.to_datetime(result["time"], unit="ms", utc=True).dt.tz_convert("Asia/Kolkata").dt.strftime("%d-%m-%Y %H:%M:%S")
        result.rename(columns=names, inplace=True)
    
    return result


def fetch_tags(unitId: str) -> List[str]:
    """Fetch all tags from efficiency mapping."""
    mapping = ""
    cfg_unit = config.get(unitId, {})
    effURL = cfg_unit.get("api", {}).get("efficiency", "")
    topic_line = f"u/{unitId}/"
    mapping_file_url = cfg_unit.get("api", {}).get("meta", "") + f'/units/{unitId}/boilerStressProfiles?filter={{"where":{{"type":"efficiencyMapping"}}}}'
    
    try:
        res = requests.get(mapping_file_url)
        if res.status_code == 200 and len(res.json()) != 0:
            mapping = res.json()[0].get("output", {})
    except:
        pass
    
    tags = []
    if mapping.get("boilerEfficiency"):
        for item in mapping["boilerEfficiency"]:
            for i, j in item.get("realtime", {}).items():
                if str(i) != "ambientAirTemp":
                    tags.extend(j)
    
    if mapping.get("turbineHeatRate"):
        for item in mapping["turbineHeatRate"]:
            for i in item.get("realtime", {}).values():
                tags.extend(i)
    
    ld_tags = []
    for tag in tags:
        url = cfg_unit.get("api", {}).get("meta", "") + f'/units/{unitId}/tagmeta?filter={{"where":{{"dataTagId":"{tag}"}},"fields":["equipmentId"]}}'
        try:
            res = requests.get(url)
            if res.status_code == 200 and res.json():
                equipId = res.json()[0].get("equipmentId")
                url2 = cfg_unit.get("api", {}).get("meta", "") + f"/units/{unitId}/equipment/{equipId}"
                res2 = requests.get(url2)
                if res2.status_code == 200 and res2.json():
                    load = res2.json().get("equipmentLoad", {}).get("loadTag")
                    ld_tags.append(load)
        except:
            pass
    
    tags = tags + ld_tags
    tags = [tag[0] if isinstance(tag, list) else tag for tag in tags]
    tags = list(set(tags))
    return tags


def uploadRefernceData(fileName: str) -> str:
    """Upload reference data file to API."""
    path = ""
    files = {"upload_file": open(str(path + fileName), "rb")}
    url = config.get("api", {}).get("meta", "") + "/attachments/test/upload"
    
    try:
        response = requests.post(url, files=files)
        if response.status_code == 200:
            return "success"
        else:
            return str(response.status_code) + str(response.content)
    except Exception as e:
        return str(e)


def downloadReferenceData(fileName: str) -> pd.DataFrame:
    """Download reference data file from API."""
    url = config.get("api", {}).get("meta", "") + f"/attachments/test/download/{fileName}"
    
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(fileName + "_read", "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        
        with open(fileName + "_read", "rb") as f1:
            return pd.read_csv(f1)
    except Exception as e:
        print(f"Error downloading reference data: {e}")
        return pd.DataFrame()


def process_dataframe(df: pd.DataFrame, weighted_avg_coal_cost: float, displayList: List) -> List:
    """Process DataFrame for display."""
    df.reset_index(drop=True, inplace=True)
    df["time"] = pd.to_datetime(df["time"]).dt.strftime("%d-%m-%Y %H:%M:%S")
    
    df["NetTgLoad"] = (df["TgLoad"] - (df["aux power"] / 24))
    df["DirectCost/KWh"] = (df["weightedLandingCost"] * df["directCoalflow"]) / (df["TgLoad"] * 1000)
    df["NetDirectCost/KWh"] = (df["weightedLandingCost"] * df["directCoalflow"]) / (df["NetTgLoad"] * 1000)
    df["InDirectCost/KWh"] = (df["weightedLandingCost"] * df["coalFlow"]) / (df["TgLoad"] * 1000)
    df["NetInDirectCost/KWh"] = (df["weightedLandingCost"] * df["coalFlow"]) / (df["NetTgLoad"] * 1000)
    
    df["correctedIndirectSteamCost"] = (weighted_avg_coal_cost * df["coalFlow"]) / df["boilerSteamFlow"]
    df["correctedSteamCost"] = (weighted_avg_coal_cost * df["directCoalflow"]) / df["boilerSteamFlow"]
    df["correctedDirectCost/KWh"] = (weighted_avg_coal_cost * df["directCoalflow"]) / (df["TgLoad"] * 1000)
    df["correctedNetDirectCost/KWh"] = (weighted_avg_coal_cost * df["directCoalflow"]) / (df["NetTgLoad"] * 1000)
    df["correctedInDirectCost/KWh"] = (weighted_avg_coal_cost * df["coalFlow"]) / (df["TgLoad"] * 1000)
    df["correctedNetInDirectCost/KWh"] = (weighted_avg_coal_cost * df["coalFlow"]) / (df["NetTgLoad"] * 1000)
    
    df.rename(columns={"time": "Date"}, inplace=True)
    columns_to_round = [col for col in df.columns if col != "Date"]
    df[columns_to_round] = df[columns_to_round].round(2)
    
    remaining_columns = [col for col in df.columns if col not in displayList]
    new_columns_order = displayList + remaining_columns
    df = df[new_columns_order]
    
    prefix = "inDirect"
    columns_to_check = ["coalFlow", "costOfFuel", "costPerUnitSteam"]
    column_mapping = {col: prefix + col if col in columns_to_check else col for col in df.columns}
    df.rename(columns=column_mapping, inplace=True)
    
    columns = df.columns.tolist()
    data_values = [columns] + df.values.tolist()
    
    return data_values


def get_relationship_between_input_output(function_name, boiler_eff_calcs: Dict) -> Dict:
    """Build relationship graph between input and output variables."""
    try:
        import inspect
        funcString = inspect.getsource(function_name)
        to_reverse_string = []
        
        for line in funcString.splitlines():
            if line and line.strip() and "def" not in line and line.strip()[0] != "#":
                pLine = line.replace("result", "res")
                to_reverse_string.append(pLine.strip())
        
        graph = {}
        reversed_function = to_reverse_string[::-1]
        
        for line in reversed_function:
            if "=" in line:
                lhs = line.split("=")[0]
                rhs = line.split("=")[1]
                depends = rhs.split('"')
                notDepends = lhs.split('"')
                depends = list(set([dep for dep in depends if dep]))
                notDepends = list(set([dep for dep in notDepends if dep]))
                
                for nd in notDepends:
                    if ("oss" in nd) and ("otal" not in nd):
                        if nd not in graph.keys():
                            if depends:
                                graph[nd] = depends
                    else:
                        for k, v in graph.items():
                            if nd in v:
                                graph[k] = graph[k] + depends
                                graph[k] = list(set(graph[k]))
        
        return graph
    except Exception as e:
        print(f"Error in get_relationship_between_input_output: {e}")
        return {}


def coalFlowCalculationNoRequest(res: Dict) -> Dict:
    """Calculate coal flow without API request."""
    required_fields = ["boilerSteamFlow", "msTemp", "msPres", "fwTemp", "coalGCV", "boilerEfficiency"]
    for field in required_fields:
        if field not in res or res.get(field) in [0, None, ""]:
            return {"error": f"{field} missing or '0' found"}
    
    result = {"coalFlow": 0, "costOfFuel": 0}
    
    try:
        from IAPWS import IAPWS97
        mssteam = IAPWS97(T=(res["msTemp"] + 273), P=(res["msPres"] * 0.0980665))
        fwsteam = IAPWS97(T=(res["fwTemp"] + 273), x=0)
        entDiff = (mssteam.h / 4.1868) - (fwsteam.h / 4.1868)
        result["entDiff"] = entDiff
        
        landingCost = res.get("landingCost", 2500)
        if res.get("boilerSteamFlow") != 0 and res.get("boilerEfficiency") != 0:
            coalFlow = (res["boilerSteamFlow"] * entDiff) / (res["boilerEfficiency"] * res["coalGCV"])
            result["coalFlow"] = round(coalFlow, 4)
            result["costOfFuel"] = landingCost * result["coalFlow"]
            result["costPerUnitSteam"] = result["costOfFuel"] / res["boilerSteamFlow"]
    except Exception as e:
        result["error"] = str(e)
    
    return result
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


def validate_json(data: Dict) -> tuple:
    required_fields = ["coalFC", "coalVM", "coalAsh", "coalMoist"]
    for field in required_fields:
        if field not in data:
            return {"error": f"{field} missing"}, 400
        if data.get(field) in [None, ""]:
            return {"error": f"{field} is empty"}, 400
    return {"valid": True}, 200


def get_year_start_time_in_epoch(year: int) -> int:
    dt = datetime(year, 1, 1)
    return int(dt.timestamp() * 1000)


def create_tag_description_dict(tagmeta_list: List[Dict]) -> Dict:
    desc_dict = {}
    for tag in tagmeta_list:
        tag_id = tag.get("dataTagId", "")
        desc = tag.get("description", "")
        if tag_id and desc:
            desc_dict[tag_id] = desc
    return desc_dict


def jsjw_specific_thr_dev_calculations(res: Dict) -> Dict:
    result = {}
    wgh_thr = res.get("weightedGrossHeatRate", 0)
    gross_heat = res.get("grossHeatRate", 0)
    
    if gross_heat and gross_heat != 0:
        result["thr_dev"] = ((wgh_thr / gross_heat) - 1) * 100
    
    corr_thr = res.get("corrected THR", 0)
    if corr_thr and corr_thr != 0:
        result["thr_dev_corrected"] = ((wgh_thr / corr_thr) - 1) * 100
    
    return result


def get_relationship_between_input_output_jsw_specific(function_name, response_body: Dict) -> Dict:
    rel = {}
    for k, v in response_body.items():
        if "thr_dev" in k:
            rel[k] = [k]
    return rel


def get_thr_dev_tags(unit_id: str) -> List[str]:
    return [
        f"u/{unit_id}/turbineHeatRate_dev",
        f"u/{unit_id}/grossHeatRate_dev"
    ]


def lastvalue(taglist: List[str]) -> pd.DataFrame:
    end_time = int(time.time() * 1000)
    query = {"metrics": [], "start_absolute": 1, "end_absolute": end_time}
    for tag in taglist:
        query["metrics"].append({"name": tag, "order": "desc", "limit": 1})
    try:
        res = requests.post(config.get('api', {}).get('query', ''), json=query).json()
        if res.get("queries"):
            df = pd.DataFrame([{"time": res["queries"][0]["results"][0]["values"][0][0]}])
            for qr in res["queries"]:
                try:
                    df.loc[0, qr["results"][0]["name"]] = qr["results"][0]["values"][0][1]
                except:
                    pass
            return df
    except:
        pass
    return pd.DataFrame()


def applyUltimateConfig(data: pd.DataFrame, fuel_config: dict) -> pd.DataFrame:
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
                total_fuel = data[fuel_flow].sum(axis=1).values[0]
                if total_fuel > 0:
                    data["coalFlow"] = total_fuel
            except:
                pass
    return data


def coalFlowCalculation(res: Dict) -> Dict:
    required = ["boilerSteamFlow", "msTemp", "msPres", "fwTemp", "coalGCV", "boilerEfficiency"]
    for f in required:
        if f not in res or res.get(f) in [0, None, ""]:
            return {"error": f"{f} missing or zero"}
    
    try:
        from IAPWS import IAPWS97
        mssteam = IAPWS97(T=(res["msTemp"] + 273), P=(res["msPres"] * 0.0980665))
        fwsteam = IAPWS97(T=(res["fwTemp"] + 273), x=0)
        ent_diff = (mssteam.h / 4.1868) - (fwsteam.h / 4.1868)
        
        coal_flow = (res["boilerSteamFlow"] * ent_diff) / (res["boilerEfficiency"] * res["coalGCV"])
        landing_cost = res.get("landingCost", 2500)
        
        return {
            "coalFlow": round(coal_flow, 4),
            "costOfFuel": round(landing_cost * coal_flow, 2),
            "costPerUnitSteam": round((landing_cost * coal_flow) / res["boilerSteamFlow"], 4),
            "entDiff": round(ent_diff, 4)
        }
    except Exception as e:
        return {"error": str(e)}


def get_thr_dev_tags(unit_id: str, system_name: str) -> List[str]:
    return [
        f"u/{unit_id}/{system_name}_turbineHeatRate_dev",
        f"u/{unit_id}/{system_name}_grossHeatRate_dev",
        f"u/{unit_id}/{system_name}_thr_dev",
        f"u/{unit_id}/{system_name}_weightedGrossHeatRate_dev"
    ]


def jsw_specific_thr_dev_calculations(res: Dict) -> Dict:
    result = {}
    wgh_thr = res.get("weightedGrossHeatRate", 0)
    gross_heat = res.get("grossHeatRate", 0)
    corr_thr = res.get("correctedTHR", 0)
    design_thr = res.get("designTHR", 0)
    
    if gross_heat and gross_heat != 0:
        result["thr_dev"] = ((wgh_thr / gross_heat) - 1) * 100
    
    if corr_thr and corr_thr != 0:
        result["thr_dev_corrected"] = ((wgh_thr / corr_thr) - 1) * 100
    
    if design_thr and design_thr != 0:
        result["thr_dev_design"] = ((wgh_thr / design_thr) - 1) * 100
    
    result["gross_heat_rate"] = wgh_thr / gross_heat if gross_heat else 0
    result["corrected_heat_rate"] = wgh_thr / corr_thr if corr_thr else 0
    result["design_heat_rate"] = wgh_thr / design_thr if design_thr else 0
    
    return result


def THRCalculation(res: Dict) -> Dict:
    return turbine_heat_rate(res)


def PHRCalculation(res: Dict) -> Dict:
    return plant_heat_rate_calc(res)


def fetchDesign1(realtime: Dict, unitId: str) -> Dict:
    fields = ["designValues", "dataTagId"]
    api_meta = config.get("api", {}).get("meta", "")
    tagmeta_uri = f"{api_meta}/units/{unitId}/tagmeta?filter={{\"where\":"
    
    designIndex = {}
    for k, v in realtime.items():
        url = f'{tagmeta_uri}{{\"dataTagId\":\"{v[0] if isinstance(v, list) else v}\"}},\"fields\":{json.dumps(fields)}}}'
        try:
            res = requests.get(url)
            if res.status_code == 200 and res.json():
                des = res.json()[0].get("designValues")
                designIndex[str(res.json()[0].get("dataTagId"))] = des
        except:
            pass
    
    for k, v in realtime.items():
        lr = designIndex.get(str(v[0]) if isinstance(v, list) else designIndex.get(str(v))
        if lr:
            realtime[k] = realtime.get("realtimeData", {}).get(str(k))
    
    return realtime


def updateform(form_data: Dict) -> int:
    form_id = form_data.get("id", "")
    if not form_id:
        return 400
    api_meta = config.get("api", {}).get("meta", "")
    update_url = f'{api_meta}/forms/update?where={{"id":"{form_id}"}}'
    try:
        res = requests.post(update_url, json=form_data)
        return res.status_code
    except:
        return 500


def getcsum(tag: str, start_time: int, end_time: int) -> float:
    query = {
        "metrics": [{"name": tag, "aggregators": [{"name": "sum"}]}],
        "start_absolute": start_time,
        "end_absolute": end_time
    }
    try:
        res = requests.post(config.get("api", {}).get("query", ""), json=query).json()
        if res.get("queries"):
            values = res["queries"][0].get("results", [{}])[0].get("values", [])
            if values:
                return values[0][1]
    except:
        pass
    return 0.0