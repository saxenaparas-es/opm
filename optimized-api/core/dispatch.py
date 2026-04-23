from calculations.proximate import (
    proximate_to_ultimate_type1,
    proximate_to_ultimate_type2,
    proximate_to_ultimate_type3,
    proximate_to_ultimate_type4,
    proximate_to_ultimate_type5,
    proximate_to_ultimate_type6,
    proximate_to_ultimate_type7,
    proximate_to_ultimate_type8,
    proximate_to_ultimate_type9,
    proximate_to_ultimate_type10,
    proximate_to_ultimate_type11,
    proximate_to_ultimate_type12,
    proximate_to_ultimate_type13,
    proximate_to_ultimate_type14,
    proximate_to_ultimate_type15,
    proximate_to_ultimate_type16,
    proximate_to_ultimate_type17,
    proximate_to_ultimate_type18,
)
from core.logging_utils import logger, log_section, log_variable, log_info

log_section("INITIALIZING DISPATCH TABLES")

PROXIMATE_TYPES = {
    "type1": proximate_to_ultimate_type1,
    "type2": proximate_to_ultimate_type2,
    "type3": proximate_to_ultimate_type3,
    "type4": proximate_to_ultimate_type4,
    "type5": proximate_to_ultimate_type5,
    "type6": proximate_to_ultimate_type6,
    "type7": proximate_to_ultimate_type7,
    "type8": proximate_to_ultimate_type8,
    "type9": proximate_to_ultimate_type9,
    "type10": proximate_to_ultimate_type10,
    "type11": proximate_to_ultimate_type11,
    "type12": proximate_to_ultimate_type12,
    "type13": proximate_to_ultimate_type13,
    "type14": proximate_to_ultimate_type14,
    "type15": proximate_to_ultimate_type15,
    "type16": proximate_to_ultimate_type16,
    "type17": proximate_to_ultimate_type17,
    "type18": proximate_to_ultimate_type18,
}

log_variable("PROXIMATE_TYPES", list(PROXIMATE_TYPES.keys()))

BOILER_TYPES = {
    "type1": None,
    "type2": None,
    "type3": None,
    "type4": None,
    "type5": None,
    "type6": None,
    "type7": None,
    "type8": None,
    "type9": None,
    "type10": None,
    "type11": None,
    "type12": None,
    "type13": None,
    "type14": None,
    "type15": None,
    "type16": None,
    "type17": None,
    "type18": None,
}

log_variable("BOILER_TYPES (initial)", list(BOILER_TYPES.keys()))

THR_CATEGORY_DISPATCH = {
    "cogent": None,
    "cogent2": None,
    "cogent3": None,
    "cogent4": None,
    "cogent5": None,
    "cogent6": None,
    "cogent7": None,
    "cogent8": None,
    "ingest": None,
    "ingest2": None,
    "pressureInMpa": None,
    "pressureInKsc": None,
    "pressureInKsc1": None,
    "lpg_type": None,
    "DBPower": None,
    "default": None,
}

log_variable("THR_CATEGORY_DISPATCH (initial)", list(THR_CATEGORY_DISPATCH.keys()))


def init_dispatch():
    log_section("INITIALIZING DISPATCH HANDLERS")
    log_info("Loading boiler efficiency handlers...")
    
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
    BOILER_TYPES.update({
        "type1": boiler_efficiency_type1,
        "type2": boiler_efficiency_type2,
        "type3": boiler_efficiency_type3,
        "type4": boiler_efficiency_type4,
        "type5": boiler_efficiency_type5,
        "type6": boiler_efficiency_type6,
        "type7": boiler_efficiency_type7,
        "type8": boiler_efficiency_type8,
        "type9": boiler_efficiency_type9,
        "type10": boiler_efficiency_type10,
        "type11": boiler_efficiency_type11,
        "type12": boiler_efficiency_type12,
        "type13": boiler_efficiency_type13,
        "type14": boiler_efficiency_type14,
        "type15": boiler_efficiency_type15,
        "type16": boiler_efficiency_type16,
        "type17": boiler_efficiency_type17,
        "type18": boiler_efficiency_type18,
    })
    log_variable("BOILER_TYPES (loaded)", list(BOILER_TYPES.keys()))
    
    log_info("Loading turbine heat rate handlers...")
    from calculations.turbine import (
        thr_cogent, thr_cogent2, thr_cogent3, thr_cogent4,
        thr_cogent5, thr_cogent6, thr_cogent7, thr_cogent8,
        thr_ingest, thr_ingest2, thr_default, thr_pressureInMpa_calcs
    )
    THR_CATEGORY_DISPATCH.update({
        "cogent": thr_cogent,
        "cogent2": thr_cogent2,
        "cogent3": thr_cogent3,
        "cogent4": thr_cogent4,
        "cogent5": thr_cogent5,
        "cogent6": thr_cogent6,
        "cogent7": thr_cogent7,
        "cogent8": thr_cogent8,
        "pressureInMpa": thr_pressureInMpa_calcs,
        "pressureInKsc": thr_pressureInMpa_calcs,
        "pressureInKsc1": thr_pressureInMpa_calcs,
        "lpg_type": thr_default,
        "ingest": thr_ingest,
        "ingest2": thr_ingest2,
        "default": thr_default,
        "pressureInMpa": thr_default,
        "pressureInKsc": thr_default,
        "pressureInKsc1": thr_default,
        "lpg_type": thr_default,
        "DBPower": thr_default,
    })
    log_variable("THR_CATEGORY_DISPATCH (loaded)", list(THR_CATEGORY_DISPATCH.keys()))
    
    log_info("DISPATCH INITIALIZATION COMPLETE")