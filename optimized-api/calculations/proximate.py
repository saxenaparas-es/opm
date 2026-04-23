from _imports import Dict, Any
from core.logging_utils import logger, log_section, log_variable, log_warning

def _validate_proximate_inputs(res: Dict[str, Any], required_keys: list) -> Dict[str, Any]:
    for key in required_keys:
        if key not in res:
            log_warning(f"Missing required input: {key}")
            return {"error": f"Missing required inputs", "status": 400}
    return None


def _proximate_core(
    coalFC: float,
    coalVM: float,
    coalAsh: float,
    coalMoist: float,
    fixed_sulphur: float = None,
    gcv_scaling: bool = False,
    coalGCV: float = None
) -> Dict[str, float]:
    log_section("PROXIMATE CORE CALCULATION")
    log_variable("coalFC", coalFC)
    log_variable("coalVM", coalVM)
    log_variable("coalAsh", coalAsh)
    log_variable("coalMoist", coalMoist)
    log_variable("fixed_sulphur", fixed_sulphur)
    log_variable("gcv_scaling", gcv_scaling)
    log_variable("coalGCV", coalGCV)
    
    carbon = 0.97 * coalFC + 0.7 * (coalVM + 0.1 * coalAsh) - (coalMoist * (0.6 - 0.01 * coalMoist))
    if gcv_scaling and coalGCV:
        carbon = carbon * (coalGCV / 100)
    
    hydrogen = 0.036 * coalFC + 0.086 * (coalVM - 0.1 * coalAsh) - 0.0035 * coalMoist ** 2 * (1 - 0.02 * coalMoist)
    nitrogen = 2.1 - 0.02 * coalVM
    
    if fixed_sulphur is not None:
        coalSulphur = fixed_sulphur
    else:
        coalSulphur = 0.009 * (coalFC + coalVM)
    
    oxygen = 100 - carbon - hydrogen - coalSulphur - nitrogen - coalAsh - coalMoist
    
    log_variable("result_carbon", carbon)
    log_variable("result_hydrogen", hydrogen)
    log_variable("result_nitrogen", nitrogen)
    log_variable("result_coalSulphur", coalSulphur)
    log_variable("result_oxygen", oxygen)
    
    return {
        "carbon": carbon,
        "hydrogen": hydrogen,
        "nitrogen": nitrogen,
        "coalSulphur": coalSulphur,
        "oxygen": oxygen
    }


def proximate_to_ultimate_type1(res):
    log_section("PROXIMATE TYPE1")
    log_variable("input_keys", list(res.keys()))
    err = _validate_proximate_inputs(res, ["coalFC", "coalVM", "coalAsh", "coalMoist"])
    if err:
        return err
    return _proximate_core(res["coalFC"], res["coalVM"], res["coalAsh"], res["coalMoist"])


def proximate_to_ultimate_type2(res):
    err = _validate_proximate_inputs(res, ["coalFC", "coalVM", "coalAsh", "coalMoist", "mineralMatter"])
    if err:
        return err
    return _proximate_core(res["coalFC"], res["coalVM"], res["coalAsh"], res["coalMoist"])


def proximate_to_ultimate_type3(res):
    err = _validate_proximate_inputs(res, ["coalFC", "coalVM", "coalAsh", "coalMoist"])
    if err:
        return err
    return _proximate_core(res["coalFC"], res["coalVM"], res["coalAsh"], res["coalMoist"])


def proximate_to_ultimate_type4(res):
    err = _validate_proximate_inputs(res, ["coalFC", "coalVM", "coalAsh", "coalMoist"])
    if err:
        return err
    return _proximate_core(res["coalFC"], res["coalVM"], res["coalAsh"], res["coalMoist"])


def proximate_to_ultimate_type5(res):
    err = _validate_proximate_inputs(res, ["coalFC", "coalVM", "coalAsh", "coalMoist"])
    if err:
        return err
    return _proximate_core(res["coalFC"], res["coalVM"], res["coalAsh"], res["coalMoist"])


def proximate_to_ultimate_type6(res):
    err = _validate_proximate_inputs(res, ["coalFC", "coalVM", "coalAsh", "coalMoist"])
    if err:
        return err
    return _proximate_core(res["coalFC"], res["coalVM"], res["coalAsh"], res["coalMoist"])


def proximate_to_ultimate_type7(res):
    err = _validate_proximate_inputs(res, ["coalFC", "coalVM", "coalAsh", "coalMoist"])
    if err:
        return err
    return _proximate_core(res["coalFC"], res["coalVM"], res["coalAsh"], res["coalMoist"])


def proximate_to_ultimate_type8(res):
    err = _validate_proximate_inputs(res, ["coalFC", "coalVM", "coalAsh", "coalMoist"])
    if err:
        return err
    return _proximate_core(res["coalFC"], res["coalVM"], res["coalAsh"], res["coalMoist"])


def proximate_to_ultimate_type9(res):
    err = _validate_proximate_inputs(res, ["coalFC", "coalVM", "coalAsh", "coalMoist"])
    if err:
        return err
    return _proximate_core(res["coalFC"], res["coalVM"], res["coalAsh"], res["coalMoist"])


def proximate_to_ultimate_type10(res):
    err = _validate_proximate_inputs(res, ["coalFC", "coalVM", "coalAsh", "coalMoist"])
    if err:
        return err
    return _proximate_core(res["coalFC"], res["coalVM"], res["coalAsh"], res["coalMoist"], fixed_sulphur=0.7)


def proximate_to_ultimate_type11(res):
    err = _validate_proximate_inputs(res, ["coalFC", "coalVM", "coalAsh", "coalMoist"])
    if err:
        return err
    return _proximate_core(res["coalFC"], res["coalVM"], res["coalAsh"], res["coalMoist"])


def proximate_to_ultimate_type12(res):
    err = _validate_proximate_inputs(res, ["coalFC", "coalVM", "coalAsh", "coalMoist"])
    if err:
        return err
    return _proximate_core(res["coalFC"], res["coalVM"], res["coalAsh"], res["coalMoist"])


def proximate_to_ultimate_type13(res):
    err = _validate_proximate_inputs(res, ["coalFC", "coalVM", "coalAsh", "coalMoist", "coalGCV"])
    if err:
        return err
    
    coalFC = res["coalFC"]
    coalVM = res["coalVM"]
    coalAsh = res["coalAsh"]
    coalMoist = res["coalMoist"]
    coalGCV_res = res["coalGCV"]
    
    S = 0.009 * (coalFC + coalVM)
    Z = coalMoist + 1.1 * coalAsh + 0.1 * S
    
    if Z >= 100:
        Z = 99.9
    
    Qp = (100 * coalGCV_res * 4.186) / (100 - Z)
    Vp = (100 * (coalVM - 0.1 * coalAsh - 0.1 * S)) / (100 - Z)
    
    if Vp < 0:
        Vp = 0
    
    Cp = 0.0015782 * Qp - 0.2226 * Vp + 37.69
    Hp = 0.0001707 * Qp + 0.0653 * Vp - 2.92
    
    carbon = (1 - 0.01 * Z) * Cp + 0.05 * coalAsh - 0.5 * S
    hydrogen = (1 - 0.01 * Z) * Hp + 0.01 * coalAsh - 0.015 * S
    nitrogen = 2.1 - 0.02 * coalVM
    
    coalSulphur = S
    oxygen = 100 - carbon - hydrogen - coalSulphur - nitrogen - coalAsh - coalMoist
    
    return {
        "carbon": round(carbon, 4),
        "hydrogen": round(hydrogen, 4),
        "nitrogen": round(nitrogen, 4),
        "coalSulphur": round(coalSulphur, 4),
        "oxygen": round(oxygen, 4)
    }


def proximate_to_ultimate_type14(res):
    err = _validate_proximate_inputs(res, ["coalFC", "coalVM", "coalAsh", "coalMoist"])
    if err:
        return err
    
    coalFC = res["coalFC"]
    coalVM = res["coalVM"]
    coalAsh = res["coalAsh"]
    coalMoist = res["coalMoist"]
    
    carbon = (0.97 * coalFC) + (0.7 * (coalVM + 0.1 * coalAsh)) - (coalMoist * (0.6 - 0.01 * coalMoist))
    hydrogen = (0.036 * coalFC) + (0.086 * (coalVM - 0.1 * coalAsh)) - (0.0035 * coalMoist * coalMoist * (1 - 0.02 * coalMoist))
    nitrogen = 2.1 - 0.02 * coalVM
    coalSulphur = 0.009 * (coalFC + coalVM)
    oxygen = 100 - carbon - hydrogen - coalSulphur - nitrogen - coalAsh - coalMoist
    
    return {
        "carbon": round(carbon, 4),
        "hydrogen": round(hydrogen, 4),
        "nitrogen": round(nitrogen, 4),
        "coalSulphur": round(coalSulphur, 4),
        "oxygen": round(oxygen, 4)
    }


def proximate_to_ultimate_type15(res):
    err = _validate_proximate_inputs(res, ["coalFC", "coalVM", "coalAsh", "coalMoist"])
    if err:
        return err
    return _proximate_core(res["coalFC"], res["coalVM"], res["coalAsh"], res["coalMoist"])


def proximate_to_ultimate_type16(res):
    err = _validate_proximate_inputs(res, ["coalFC", "coalVM", "coalAsh", "coalMoist"])
    if err:
        return err
    return _proximate_core(res["coalFC"], res["coalVM"], res["coalAsh"], res["coalMoist"])


def proximate_to_ultimate_type17(res):
    err = _validate_proximate_inputs(res, ["coalFC", "coalVM", "coalAsh", "coalMoist"])
    if err:
        return err
    return _proximate_core(res["coalFC"], res["coalVM"], res["coalAsh"], res["coalMoist"])


def proximate_to_ultimate_type18(res):
    err = _validate_proximate_inputs(res, ["coalFC", "coalVM", "coalAsh", "coalMoist"])
    if err:
        return err
    return _proximate_core(res["coalFC"], res["coalVM"], res["coalAsh"], res["coalMoist"])