from typing import Dict, Any, List, Optional


def validate_required_fields(data: Dict[str, Any], required: List[str]) -> Optional[str]:
    for field in required:
        if field not in data:
            return field
    return None


def validate_positiveNumeric(value: Any, field_name: str) -> Optional[str]:
    try:
        val = float(value)
        if val <= 0:
            return field_name
    except (TypeError, ValueError):
        return field_name
    return None


def validate_o2_range(o2: Any) -> Optional[str]:
    try:
        val = float(o2)
        if val < 0 or val >= 21:
            return "o2"
    except (TypeError, ValueError):
        return "o2"
    return None


def validate_temperature(temp: Any, field_name: str = "temp") -> Optional[str]:
    try:
        val = float(temp)
        if val < -273:
            return field_name
    except (TypeError, ValueError):
        return field_name
    return None


def validate_pressure(pressure: Any) -> Optional[str]:
    try:
        val = float(pressure)
        if val <= 0:
            return "pressure"
    except (TypeError, ValueError):
        return "pressure"
    return None


def validate_percentage(value: Any, field_name: str = "percent") -> Optional[str]:
    try:
        val = float(value)
        if val < 0 or val > 100:
            return field_name
    except (TypeError, ValueError):
        return field_name
    return None