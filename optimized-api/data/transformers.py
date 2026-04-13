from typing import Dict, Any, List
import pandas as pd


def transform_proximate_to_ultimate(data: Dict[str, Any]) -> Dict[str, float]:
    return {
        "carbon": data.get("carbon", 0),
        "hydrogen": data.get("hydrogen", 0),
        "nitrogen": data.get("nitrogen", 0),
        "sulphur": data.get("sulphur", 0),
        "oxygen": data.get("oxygen", 0),
    }


def transform_boiler_result(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "efficiency": result.get("boilerEfficiency", 0),
        "theoAirRequired": result.get("TheoAirRequired", 0),
        "excessAir": result.get("ExcessAir", 0),
        "totalLoss": result.get("LossTotal", 0),
    }


def transform_thr_result(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "heatRate": result.get("turbineHeatRate", 0),
    }


def transform_plant_result(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "plantHeatRate": result.get("plantHeatRate", 0),
        "avgBoilerEfficiency": result.get("averageBoilerEfficiency", 0),
    }


def transform_batch_results(results: List[Dict[str, Any]], metric: str) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()
    return pd.DataFrame(results)


def normalize_column_names(data: Dict[str, Any]) -> Dict[str, Any]:
    return {k.lower().replace(" ", "_"): v for k, v in data.items()}