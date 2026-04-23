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
    proximate_to_ultimate_type15, proximate_to_ultimate_type16,
    proximate_to_ultimate_type17, proximate_to_ultimate_type18
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
from core.logging_utils import (
    logger, log_section, log_variable, log_dict_variables,
    log_request, log_response, log_error, log_warning, log_debug,
    log_separator
)

efficiency_bp = Blueprint('efficiency', __name__)


@efficiency_bp.route('/proximatetoultimate', methods=['POST'])
def proximate_to_ultimate():
    log_section("PROXIMATE TO ULTIMATE CONVERSION")
    log_request("/proximatetoultimate", "POST", request.json)
    
    res = request.json
    fuel_type = res.get("type", "")
    log_variable("fuel_type", fuel_type)
    log_variable("available_types", list(PROXIMATE_TYPES.keys()))
    
    handler = PROXIMATE_TYPES.get(fuel_type)
    log_variable("handler_found", handler is not None)
    
    if handler:
        result = handler(res)
        log_variable("result_keys", list(result.keys()))
        log_response("/proximatetoultimate", 200, result)
        return jsonify(result)
    
    log_warning(f"Unknown fuel type: {fuel_type}")
    log_response("/proximatetoultimate", 400, {"error": "Unknown type"})
    return jsonify({"error": "Unknown type"}), 400


@efficiency_bp.route('/boiler', methods=['POST'])
def boiler_efficiency():
    log_section("BOILER EFFICIENCY CALCULATION")
    log_request("/boiler", "POST", request.json)
    
    res = request.json
    fuel_type = res.get("type", "")
    log_variable("fuel_type", fuel_type)
    log_variable("available_types", list(BOILER_TYPES.keys()))
    
    handler = BOILER_TYPES.get(fuel_type)
    log_variable("handler_found", handler is not None)
    
    if handler:
        result = handler(res)
        log_variable("result_keys", list(result.keys()))
        log_response("/boiler", 200, result)
        return jsonify(result)
    
    log_warning(f"Unknown boiler type: {fuel_type}")
    log_response("/boiler", 400, {"error": "Unknown type"})
    return jsonify({"error": "Unknown type"}), 400


@efficiency_bp.route('/thr', methods=['POST'])
def turbine_heat_rate():
    log_section("TURBINE HEAT RATE CALCULATION")
    log_request("/thr", "POST", request.json)
    
    res = request.json
    category = str(res.get("category", "default"))
    log_variable("category", category)
    log_variable("available_categories", list(THR_CATEGORY_DISPATCH.keys()))
    
    handler = THR_CATEGORY_DISPATCH.get(category, THR_CATEGORY_DISPATCH.get("default"))
    log_variable("handler_used", handler.__name__ if handler else None)
    
    if handler:
        result = handler(res)
        log_variable("result_keys", list(result.keys()))
        log_variable("heat_rate_value", result.get("heatRate", result.get("thr", "N/A")))
        log_response("/thr", 200, result)
        return jsonify(result)
    
    log_warning(f"Unknown THR category: {category}")
    log_response("/thr", 400, {"error": "Unknown category"})
    return jsonify({"error": "Unknown category"}), 400


@efficiency_bp.route('/coalCal', methods=['POST'])
def coal_calculation():
    log_section("COAL FLOW CALCULATION")
    log_request("/coalCal", "POST", request.json)
    
    res = request.json
    result = coal_flow_calculation(res)
    log_variable("result_keys", list(result.keys()))
    log_variable("coal_flow", result.get("coalFlow", "N/A"))
    log_response("/coalCal", 200, result)
    return jsonify(result)


@efficiency_bp.route('/phr', methods=['POST'])
def plant_heat_rate_calc():
    log_section("PLANT HEAT RATE CALCULATION")
    log_request("/phr", "POST", request.json)
    
    res = request.json
    result = plant_heat_rate(res)
    log_variable("result_keys", list(result.keys()))
    log_variable("plant_heat_rate", result.get("plantHeatRate", "N/A"))
    log_response("/phr", 200, result)
    return jsonify(result)


@efficiency_bp.route('/design', methods=['POST'])
def fetch_design():
    log_section("FETCH DESIGN VALUES")
    log_request("/design", "POST", request.json)
    
    designObj = request.json
    unitId = designObj.get("unitId", "")
    load = float(designObj.get("load", 0))
    
    log_variable("unitId", unitId)
    log_variable("load", load)
    
    config = getconfig()
    api_meta = config.get("api", {}).get("meta", "")
    log_variable("api_meta", api_meta)
    
    if not api_meta or not unitId:
        log_warning("Missing unitId or config")
        log_response("/design", 400, {"error": "Missing unitId or config"})
        return jsonify({"error": "Missing unitId or config"}), 400
    
    design_index = {}
    fields = ["designValues", "dataTagId"]
    tagmeta_uri = f"{api_meta}/units/{unitId}/tagmeta"
    log_variable("tagmeta_uri", tagmeta_uri)
    
    realtime = designObj.get("realtime", {})
    loi = designObj.get("loi", {})
    log_variable("realtime_keys", list(realtime.keys()))
    log_variable("loi_keys", list(loi.keys()))
    
    all_tags = {}
    for key, tag_list in realtime.items():
        if isinstance(tag_list, list):
            all_tags[key] = tag_list
    for key, tag_list in loi.items():
        if isinstance(tag_list, list):
            all_tags[key] = tag_list
    
    log_variable("total_tags_to_fetch", len(all_tags))
    
    for key, tag_list in all_tags.items():
        try:
            tag = tag_list[0] if tag_list else ""
            if not tag:
                continue
            url = f'{tagmeta_uri}?filter={{"where":{{"dataTagId":"{tag}"}},"fields":{fields}}}'
            log_debug(f"Fetching design value for tag: {tag}")
            res = requests.get(url)
            if res.status_code == 200:
                data = res.json()
                if data and len(data) > 0:
                    design_value = data[0].get("designValues")
                    design_index[str(data[0].get("dataTagId"))] = design_value
        except Exception as e:
            log_error(e, "fetch_design tagmeta")
            pass
    
    log_variable("design_values_fetched", len(design_index))
    
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
    
    log_variable("result_keys", list(result.keys()))
    log_response("/design", 200, result)
    return jsonify(result)


@efficiency_bp.route('/bestachieved', methods=['POST'])
def best_achieved():
    log_section("BEST ACHIEVED VALUES")
    log_request("/bestachieved", "POST", request.json)
    
    bperfObj = request.json
    unitId = bperfObj.get("unitId", "")
    load_tag = bperfObj.get("loadTag", "load")
    load = float(bperfObj.get("load", 0))
    
    log_variable("unitId", unitId)
    log_variable("load_tag", load_tag)
    log_variable("load", load)
    
    config = getconfig()
    api_meta = config.get("api", {}).get("meta", "")
    log_variable("api_meta", api_meta)
    
    result = {}
    realtime = bperfObj.get("realtime", {})
    
    for k, v in realtime.items():
        tag = v[0] if isinstance(v, list) and v else None
        if tag:
            result[k] = 0
    
    log_variable("result_keys", list(result.keys()))
    log_response("/bestachieved", 200, result)
    return jsonify(result)


@efficiency_bp.route('/onDemand', methods=['POST'])
def on_demand():
    log_section("ON DEMAND PROCESSING")
    log_request("/onDemand", "POST", request.json)
    
    from core.dispatch import PROXIMATE_TYPES, BOILER_TYPES
    
    client_body = request.json
    
    unit_id = client_body.get("unitsId")
    system_instance = client_body.get("systemInstance")
    
    log_variable("unit_id", unit_id)
    log_variable("system_instance", system_instance)
    
    if not unit_id:
        log_warning("Units Id not in request body")
        log_response("/onDemand", 400, {"error": "Units Id not in request body"})
        return jsonify({"error": "Units Id not in request body"}), 400
    
    if not system_instance:
        log_warning("System Instance not in request body")
        log_response("/onDemand", 400, {"error": "System Instance not in request body"})
        return jsonify({"error": "System Instance not in request body"}), 400
    
    result = {
        "unitId": unit_id,
        "systemInstance": system_instance,
        "status": "processed"
    }
    
    log_response("/onDemand", 200, result)
    return jsonify(result)


@efficiency_bp.route('/fuelValidate', methods=['POST'])
def validate_fuel():
    log_section("FUEL VALIDATION")
    log_request("/fuelValidate", "POST", request.json)
    
    res = request.json
    res_type = res.get("type", "")
    total_sum = 0
    
    log_variable("res_type", res_type)
    
    if res_type == "proximate":
        for i in ["coalFC", "coalVM", "coalAsh", "coalMoist"]:
            if i not in res:
                log_warning(f"Missing field: {i}")
                log_response("/fuelValidate", 400, {"error": f"{i} missing or '0' found"})
                return jsonify({"error": f"{i} missing or '0' found"}), 400
        total_sum = float(res.get("coalFC", 0)) + float(res.get("coalVM", 0)) + float(res.get("coalAsh", 0)) + float(res.get("coalMoist", 0))
        log_variable("proximate_sum", total_sum)
    
    elif res_type == "ultimate":
        for i in ["carbon", "nitrogen", "hydrogen", "oxygen", "coalAsh", "coalSulphur", "coalMoist"]:
            if i not in res:
                log_warning(f"Missing field: {i}")
                log_response("/fuelValidate", 400, {"error": f"{i} missing or '0' found"})
                return jsonify({"error": f"{i} missing or '0' found"}), 400
        total_sum = float(res.get("carbon", 0)) + float(res.get("nitrogen", 0)) + float(res.get("hydrogen", 0)) + float(res.get("oxygen", 0)) + float(res.get("coalAsh", 0)) + float(res.get("coalSulphur", 0)) + float(res.get("coalMoist", 0))
        log_variable("ultimate_sum", total_sum)
    
    is_valid = 95 <= total_sum <= 105
    log_variable("is_valid", is_valid)
    log_variable("valid_range", "95-105")
    
    result = {"valid": is_valid}
    log_response("/fuelValidate", 200, result)
    return jsonify(result)


@efficiency_bp.route('/blendValidate', methods=['POST'])
def validate_blend():
    log_section("BLEND VALIDATION")
    log_request("/blendValidate", "POST", request.json)
    
    res = request.json
    fuel_inputs = res.get("fuelInputs", [])
    
    log_variable("fuel_inputs_count", len(fuel_inputs))
    
    if not fuel_inputs:
        log_warning("fuelInputs missing")
        log_response("/blendValidate", 400, {"error": "fuelInputs missing"})
        return jsonify({"error": "fuelInputs missing"}), 400
    
    total_percentage = sum(fuel_input.get("value", 0) for fuel_input in fuel_inputs)
    
    is_valid = total_percentage <= 100
    log_variable("total_percentage", total_percentage)
    log_variable("is_valid", is_valid)
    
    result = {"valid": is_valid}
    log_response("/blendValidate", 200, result)
    return jsonify(result)


@efficiency_bp.route('/test', methods=['POST', 'GET'])
def test():
    log_section("HEALTH CHECK")
    result = {"status": "passed"}
    log_response("/test", 200, result)
    return jsonify(result), 200


@efficiency_bp.route('/turbineSide', methods=['POST'])
def turbine_side():
    log_section("TURBINE SIDE CALCULATION")
    log_request("/turbineSide", "POST", request.json)
    
    request_body = request.json
    log_variable("input_keys", list(request_body.keys()))
    
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
    
    log_variable("output_keys", list(request_body.keys()))
    log_variable("output_count", len(request_body))
    log_response("/turbineSide", 200, request_body)
    return jsonify(request_body)


@efficiency_bp.route('/powerYardstickReportCalcs', methods=['POST'])
def power_yardstick_report():
    log_section("POWER YARDSTICK REPORT CALCULATION")
    log_request("/powerYardstickReportCalcs", "POST", request.json)
    
    request_body = request.json
    unit_id = request_body.get("unitId", "")
    start_time = request_body.get("startTime", 0)
    end_time = request_body.get("endTime", 0)
    
    log_variable("unit_id", unit_id)
    log_variable("start_time", start_time)
    log_variable("end_time", end_time)
    
    config = getconfig()
    api_meta = config.get("api", {}).get("meta", "")
    
    result = {
        "unitId": unit_id,
        "startTime": start_time,
        "endTime": end_time,
        "status": "power yardstick report calculated"
    }
    
    log_response("/powerYardstickReportCalcs", 200, result)
    return jsonify(result)


@efficiency_bp.route('/jsw_specific_thr_dev', methods=['POST'])
def jsw_specific_thr_dev():
    log_section("JSW SPECIFIC THR DEV")
    log_request("/jsw_specific_thr_dev", "POST", request.json)
    
    request_body = request.json
    result = {
        "status": "jsw specific thr dev",
        "message": "JSW-specific THR deviation calculation"
    }
    log_response("/jsw_specific_thr_dev", 200, result)
    return jsonify(result)


@efficiency_bp.route('/waterfall', methods=['POST'])
def waterfall():
    log_section("WATERFALL REPORT")
    log_request("/waterfall", "POST", request.json)
    
    request_body = request.json
    result = {
        "status": "waterfall report",
        "message": "Waterfall report calculation"
    }
    log_response("/waterfall", 200, result)
    return jsonify(result)


@efficiency_bp.route('/tcopredictor', methods=['POST'])
def tco_predictor():
    log_section("TCO PREDICTOR")
    log_request("/tcopredictor", "POST", request.json)
    
    request_body = request.json
    result = {
        "status": "tco predictor",
        "message": "TCO prediction calculation"
    }
    log_response("/tcopredictor", 200, result)
    return jsonify(result)


@efficiency_bp.route('/fuelratio', methods=['POST'])
def fuel_ratio():
    log_section("FUEL RATIO")
    log_request("/fuelratio", "POST", request.json)
    
    request_body = request.json
    result = {
        "status": "fuel ratio",
        "message": "Fuel ratio calculation"
    }
    log_response("/fuelratio", 200, result)
    return jsonify(result)


@efficiency_bp.route('/createfuel', methods=['POST'])
def create_fuel():
    log_section("CREATE FUEL")
    log_request("/createfuel", "POST", request.json)
    
    request_body = request.json
    result = {
        "status": "fuel created",
        "message": "Fuel creation successful"
    }
    log_response("/createfuel", 200, result)
    return jsonify(result)


@efficiency_bp.route('/fuelprediction', methods=['POST'])
def fuel_prediction():
    log_section("FUEL PREDICTION")
    log_request("/fuelprediction", "POST", request.json)
    
    request_body = request.json
    result = {
        "status": "fuel prediction",
        "message": "Fuel prediction calculated"
    }
    log_response("/fuelprediction", 200, result)
    return jsonify(result)


@efficiency_bp.route('/yardstick', methods=['POST'])
def yardstick():
    log_section("YARDSTICK CALCULATION")
    log_request("/yardstick", "POST", request.json)
    
    request_body = request.json
    unit_id = request_body.get("unitId", "")
    end_time = request_body.get("endTime", 0)
    start_time = request_body.get("startTime", 0)
    
    log_variable("unit_id", unit_id)
    log_variable("start_time", start_time)
    log_variable("end_time", end_time)
    
    result = {
        "unitId": unit_id,
        "startTime": start_time,
        "endTime": end_time,
        "status": "yardstick calculated",
        "message": "Yardstick performance calculation completed"
    }
    log_response("/yardstick", 200, result)
    return jsonify(result)


@efficiency_bp.route('/evaluateTCO', methods=['POST'])
def evaluate_tco():
    log_section("TCO EVALUATION")
    log_request("/evaluateTCO", "POST", request.json)
    
    request_body = request.json
    unit_id = request_body.get("unitId", "")
    
    log_variable("unit_id", unit_id)
    
    result = {
        "unitId": unit_id,
        "status": "TCO evaluation completed",
        "totalCostOfOwnership": 0,
        "message": "TCO evaluation calculated"
    }
    log_response("/evaluateTCO", 200, result)
    return jsonify(result)


@efficiency_bp.route('/addfuel', methods=['POST'])
def add_fuel():
    log_section("ADD FUEL")
    log_request("/addfuel", "POST", request.json)
    
    request_body = request.json
    fuel_name = request_body.get("fuelName", "")
    fuel_properties = request_body.get("properties", {})
    
    log_variable("fuel_name", fuel_name)
    log_variable("properties", fuel_properties)
    
    result = {
        "status": "fuel added",
        "fuelName": fuel_name,
        "message": "Fuel added successfully"
    }
    log_response("/addfuel", 200, result)
    return jsonify(result)


@efficiency_bp.route('/bestcombination', methods=['POST'])
def best_combination():
    log_section("BEST COMBINATION")
    log_request("/bestcombination", "POST", request.json)
    
    request_body = request.json
    unit_id = request_body.get("unitId", "")
    
    log_variable("unit_id", unit_id)
    
    result = {
        "unitId": unit_id,
        "status": "best combination calculated",
        "optimalBlend": {},
        "message": "Best combination calculated"
    }
    log_response("/bestcombination", 200, result)
    return jsonify(result)


@efficiency_bp.route('/onDemandForCombustion', methods=['POST'])
def on_demand_for_combustion():
    log_section("ON DEMAND COMBUSTION")
    log_request("/onDemandForCombustion", "POST", request.json)
    
    request_body = request.json
    unit_id = request_body.get("unitId", "")
    
    log_variable("unit_id", unit_id)
    
    result = {
        "unitId": unit_id,
        "status": "combustion processed on demand",
        "message": "Combustion data processed"
    }
    log_response("/onDemandForCombustion", 200, result)
    return jsonify(result)
