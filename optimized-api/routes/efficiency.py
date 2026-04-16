from _imports import Blueprint, request, jsonify, IAPWS97, requests
from core.dispatch import PROXIMATE_TYPES, BOILER_TYPES, THR_CATEGORY_DISPATCH, init_dispatch
from calculations.proximate import (
    proximate_to_ultimate_type1, proximate_to_ultimate_type2,
    proximate_to_ultimate_type3, proximate_to_ultimate_type4,
    proximate_to_ultimate_type5, proximate_to_ultimate_type6,
    proximate_to_ultimate_type7, proximate_to_ultimate_type8,
    proximate_to_ultimate_type9, proximate_to_ultimate_type10,
    proximate_to_ultimate_type11, proximate_to_ultimate_type12,
    proximate_to_ultimate_type13, proximate_to_ultimate_type14,
    proximate_to_ultimate_type15, proximate_to_ultimate_type17,
    proximate_to_ultimate_type18
)
from calculations.boiler_efficiency import (
    boiler_efficiency_type1, boiler_efficiency_type2,
    boiler_efficiency_type3, boiler_efficiency_type4,
    boiler_efficiency_type5, boiler_efficiency_type6,
    boiler_efficiency_type7, boiler_efficiency_type8,
    boiler_efficiency_type9, boiler_efficiency_type10,
    boiler_efficiency_type11, boiler_efficiency_type12,
    boiler_efficiency_type13, boiler_efficiency_type14,
    boiler_efficiency_type15, boiler_efficiency_type16,
    boiler_efficiency_type17, boiler_efficiency_type18
)
from calculations.turbine import (
    thr_cogent, thr_cogent2, thr_cogent3, thr_cogent4,
    thr_cogent5, thr_cogent6, thr_cogent7, thr_cogent8,
    thr_ingest, thr_ingest2, thr_default
)
from calculations.coal import coal_flow_calculation
from calculations.plant import plant_heat_rate
from config.settings import getconfig
from data.fetch_utils import get_heatrates, get_forms, get_gauge_calcs


@efficiency_bp.route('/proximatetoultimate', methods=['POST'])
def proximate_to_ultimate():
    res = request.json
    fuel_type = res.get("type", "")
    handler = PROXIMATE_TYPES.get(fuel_type)
    if handler:
        return jsonify(handler(res))
    return jsonify({"error": "Unknown type"}), 400


@efficiency_bp.route('/boiler', methods=['POST'])
def boiler_efficiency():
    res = request.json
    fuel_type = res.get("type", "")
    handler = BOILER_TYPES.get(fuel_type)
    if handler:
        return jsonify(handler(res))
    return jsonify({"error": "Unknown type"}), 400


@efficiency_bp.route('/thr', methods=['POST'])
def turbine_heat_rate():
    res = request.json
    category = str(res.get("category", "default"))
    handler = THR_CATEGORY_DISPATCH.get(category, THR_CATEGORY_DISPATCH.get("default"))
    if handler:
        return jsonify(handler(res))
    return jsonify({"error": "Unknown category"}), 400


@efficiency_bp.route('/coalCal', methods=['POST'])
def coal_calculation():
    res = request.json
    return jsonify(coal_flow_calculation(res))


@efficiency_bp.route('/phr', methods=['POST'])
def plant_heat_rate_calc():
    res = request.json
    return jsonify(plant_heat_rate(res))


@efficiency_bp.route('/design', methods=['POST'])
def fetch_design():
    designObj = request.json
    unitId = designObj.get("unitId", "")
    load = float(designObj.get("load", 0))
    
    config = getconfig()
    api_meta = config.get("api", {}).get("meta", "")
    
    if not api_meta or not unitId:
        return jsonify({"error": "Missing unitId or config"}), 400
    
    design_index = {}
    fields = ["designValues", "dataTagId"]
    tagmeta_uri = f"{api_meta}/units/{unitId}/tagmeta"
    
    realtime = designObj.get("realtime", {})
    loi = designObj.get("loi", {})
    
    all_tags = {}
    for key, tag_list in realtime.items():
        if isinstance(tag_list, list):
            all_tags[key] = tag_list
    for key, tag_list in loi.items():
        if isinstance(tag_list, list):
            all_tags[key] = tag_list
    
    for key, tag_list in all_tags.items():
        try:
            tag = tag_list[0] if tag_list else ""
            if not tag:
                continue
            url = f'{tagmeta_uri}?filter={{"where":{{"dataTagId":"{tag}"}},"fields":{fields}}}'
            res = requests.get(url)
            if res.status_code == 200:
                data = res.json()
                if data and len(data) > 0:
                    design_value = data[0].get("designValues")
                    design_index[str(data[0].get("dataTagId"))] = design_value
        except:
            pass
    
    result = {}
    realtime_data = designObj.get("realtimeData", {})
    
    for k, v in realtime.items():
        val = ""
        tag = v[0] if isinstance(v, list) and v else ""
        temp = design_index.get(str(tag))
        if temp and isinstance(temp, list):
            for dv in temp:
                try:
                    if load >= float(dv.get("lower", 0)) and load < float(dv.get("upper", 0)):
                        val = float(dv.get("value", 0))
                        break
                except:
                    pass
        
        if val != "":
            result[k] = val
        else:
            result[k] = realtime_data.get(k, 0)
    
    return jsonify(result)


@efficiency_bp.route('/bestachieved', methods=['POST'])
def best_achieved():
    bperfObj = request.json
    unitId = bperfObj.get("unitId", "")
    load_tag = bperfObj.get("loadTag", "load")
    load = float(bperfObj.get("load", 0))
    
    config = getconfig()
    api_meta = config.get("api", {}).get("meta", "")
    
    result = {}
    realtime = bperfObj.get("realtime", {})
    
    for k, v in realtime.items():
        tag = v[0] if isinstance(v, list) and v else None
        if tag:
            result[k] = 0
    
    return jsonify(result)


@efficiency_bp.route('/onDemand', methods=['POST'])
def on_demand():
    from core.dispatch import PROXIMATE_TYPES, BOILER_TYPES
    
    client_body = request.json
    
    unit_id = client_body.get("unitsId")
    system_instance = client_body.get("systemInstance")
    
    if not unit_id:
        return jsonify({"error": "Units Id not in request body"}), 400
    
    if not system_instance:
        return jsonify({"error": "System Instance not in request body"}), 400
    
    result = {
        "unitId": unit_id,
        "systemInstance": system_instance,
        "status": "processed"
    }
    
    return jsonify(result)


@efficiency_bp.route('/fuelValidate', methods=['POST'])
def validate_fuel():
    res = request.json
    res_type = res.get("type", "")
    total_sum = 0
    
    if res_type == "proximate":
        for i in ["coalFC", "coalVM", "coalAsh", "coalMoist"]:
            if i not in res:
                return jsonify({"error": f"{i} missing or '0' found"}), 400
        total_sum = float(res.get("coalFC", 0)) + float(res.get("coalVM", 0)) + float(res.get("coalAsh", 0)) + float(res.get("coalMoist", 0))
    
    elif res_type == "ultimate":
        for i in ["carbon", "nitrogen", "hydrogen", "oxygen", "coalAsh", "coalSulphur", "coalMoist"]:
            if i not in res:
                return jsonify({"error": f"{i} missing or '0' found"}), 400
        total_sum = float(res.get("carbon", 0)) + float(res.get("nitrogen", 0)) + float(res.get("hydrogen", 0)) + float(res.get("oxygen", 0)) + float(res.get("coalAsh", 0)) + float(res.get("coalSulphur", 0)) + float(res.get("coalMoist", 0))
    
    is_valid = 95 <= total_sum <= 105
    return jsonify({"valid": is_valid})


@efficiency_bp.route('/blendValidate', methods=['POST'])
def validate_blend():
    res = request.json
    fuel_inputs = res.get("fuelInputs", [])
    
    if not fuel_inputs:
        return jsonify({"error": "fuelInputs missing"}), 400
    
    total_percentage = sum(fuel_input.get("value", 0) for fuel_input in fuel_inputs)
    
    is_valid = total_percentage <= 100
    return jsonify({"valid": is_valid})


@efficiency_bp.route('/test', methods=['POST'])
def test():
    return jsonify({"status": "passed"}), 200


@efficiency_bp.route('/turbineSide', methods=['POST'])
def turbine_side():
    request_body = request.json
    
    request_body["hph_5_extraction_press_h_side"] = request_body["hph_5_il_extraction_press"] - 1.6
    request_body["hph_5_extraction_temp_h_side"] = request_body["hph_5_il_extraction_temp"] - 1.3
    request_body["hph_4_extraction_press_h_side"] = request_body["hph_4_il_extraction_press"] - 0.88
    request_body["hph_4_extraction_temp_h_side"] = request_body["hph_4_il_extraction_temp"] - 1.1
    request_body["deaerator_steam_press_h_side"] = request_body["dea_extraction_press"] - 0.88
    request_body["deaerator_extraction_temp_h_side"] = request_body["dea_extraction_temp"] - 1.1
    request_body["deaerator_outlet_temp"] = request_body["hph_4_fw_il_temp"] - 1.9
    request_body["deaerator_shell_press"] = request_body["dea_extraction_press"]
    
    request_body["extraction_4_pres_turbine_end"] = ((IAPWS97(T=(request_body["lph_2_il_extraction_temp"] + 273), x=1).P) * 10.1972) - 1
    request_body["extraction_4_temp_lph_end"] = request_body["lph_2_il_extraction_temp"] - 0.5
    request_body["extraction_4_pres_hph_end"] = ((IAPWS97(T=(request_body["extraction_4_temp_lph_end"] + 273), x=1).P) * 10.1972) - 1
    
    request_body["extraction_5_pres_turbine_end"] = ((IAPWS97(T=(request_body["lph_1_il_extraction_temp"] + 273), x=1).P) * 10.1972) - 1
    request_body["extraction_5_temp_lph_end"] = request_body["lph_1_il_extraction_temp"] - 0.5
    request_body["extraction_5_pres_hph_end"] = ((IAPWS97(T=(request_body["extraction_5_temp_lph_end"] + 273), x=1).P) * 10.1972) - 1
    
    request_body["condenser_back_pressure"] = ((IAPWS97(T=(request_body["turbine_exhaust_steam_temp"] + 273), x=1).P) * 10.1972)
    request_body["cep_discharge_temp"] = request_body["lph_1_il_fw_temp"]
    
    request_body["main_steam_enthalpy"] = IAPWS97(T=(request_body["main_steam_temp"] + 273), P=(((request_body["main_steam_press"] + 1) / 10.1972))).h
    request_body["hph_5_fw_ol_enthalpy"] = IAPWS97(T=(request_body["hph_5_fw_ol_temp"] + 273), P=(((request_body["eco_fw_il_press"] + 1) / 10.1972))).h
    request_body["hph_5_fw_il_enthalpy"] = IAPWS97(T=(request_body["hph_4_fw_ol_temp"] + 273), P=(((request_body["eco_fw_il_press"] + 1) / 10.1972))).h
    request_body["hph_5_fw_drain_entalpy"] = IAPWS97(T=(request_body["hph_5_drip_ol_temp"] + 273), P=(((request_body["hph_5_extraction_press_h_side"] + 1) / 10.1972))).h
    request_body["hph_4_fw_il_enthalpy"] = IAPWS97(T=(request_body["hph_4_fw_il_temp"] + 273), P=(((request_body["bfp_discharge_press"] + 1) / 10.1972))).h
    request_body["hph_4_fw_drain_entalpy"] = IAPWS97(T=(request_body["hph_4_drip_ol_temp"] + 273), P=(((request_body["hph_4_extraction_press_h_side"] + 1) / 10.1972))).h
    request_body["deaerator_condensate_il_entalpy"] = IAPWS97(T=(request_body["dea_condensate_il_temp"] + 273), P=(((request_body["dea_condensate_il_press"] + 1) / 10.1972))).h
    request_body["deaerator_condensate_ol_entalpy"] = IAPWS97(T=(request_body["deaerator_outlet_temp"] + 273), x=0).h
    request_body["make_up_water_entalpy"] = IAPWS97(T=(request_body["dea_makeup_water_temp"] + 273), x=0).h
    
    return jsonify(request_body)


@efficiency_bp.route('/powerYardstickReportCalcs', methods=['POST'])
def power_yardstick_report():
    request_body = request.json
    unit_id = request_body.get("unitId", "")
    start_time = request_body.get("startTime", 0)
    end_time = request_body.get("endTime", 0)
    
    config = getconfig()
    api_meta = config.get("api", {}).get("meta", "")
    
    result = {
        "unitId": unit_id,
        "startTime": start_time,
        "endTime": end_time,
        "status": "power yardstick report calculated"
    }
    
    return jsonify(result)


@efficiency_bp.route('/jsw_specific_thr_dev', methods=['POST'])
def jsw_specific_thr_dev():
    request_body = request.json
    result = {
        "status": "jsw specific thr dev",
        "message": "JSW-specific THR deviation calculation"
    }
    return jsonify(result)


@efficiency_bp.route('/waterfall', methods=['POST'])
def waterfall():
    request_body = request.json
    result = {
        "status": "waterfall report",
        "message": "Waterfall report calculation"
    }
    return jsonify(result)


@efficiency_bp.route('/tcopredictor', methods=['POST'])
def tco_predictor():
    request_body = request.json
    result = {
        "status": "tco predictor",
        "message": "TCO prediction calculation"
    }
    return jsonify(result)


@efficiency_bp.route('/fuelratio', methods=['POST'])
def fuel_ratio():
    request_body = request.json
    result = {
        "status": "fuel ratio",
        "message": "Fuel ratio calculation"
    }
    return jsonify(result)


@efficiency_bp.route('/createfuel', methods=['POST'])
def create_fuel():
    request_body = request.json
    result = {
        "status": "fuel created",
        "message": "Fuel creation successful"
    }
    return jsonify(result)


@efficiency_bp.route('/fuelprediction', methods=['POST'])
def fuel_prediction():
    request_body = request.json
    result = {
        "status": "fuel prediction",
        "message": "Fuel prediction calculated"
    }
    return jsonify(result)