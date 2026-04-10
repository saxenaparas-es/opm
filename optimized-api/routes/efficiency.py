from optimized_api._imports import Blueprint, request, jsonify
from optimized_api.core.dispatch import PROXIMATE_TYPES, BOILER_TYPES, THR_CATEGORY_DISPATCH, init_dispatch
from optimized_api.calculations.proximate import (
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
from optimized_api.calculations.boiler_efficiency import (
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
from optimized_api.calculations.turbine import (
    thr_cogent, thr_cogent2, thr_cogent3, thr_cogent4,
    thr_cogent5, thr_cogent6, thr_cogent7, thr_cogent8,
    thr_ingest, thr_ingest2, thr_default
)
from optimized_api.calculations.coal import coal_flow_calculation
from optimized_api.calculations.plant import plant_heat_rate

init_dispatch()

efficiency_bp = Blueprint('efficiency', __name__)


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


@efficiency_bp.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "passed"}), 200