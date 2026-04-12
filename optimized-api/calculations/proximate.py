from optimized_api._imports import Dict, Any


def _validate_proximate_inputs(res: Dict[str, Any], required_keys: list) -> Dict[str, Any]:
    for key in required_keys:
        if key not in res:
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
    
    return {
        "carbon": carbon,
        "hydrogen": hydrogen,
        "nitrogen": nitrogen,
        "coalSulphur": coalSulphur,
        "oxygen": oxygen
    }


def proximate_to_ultimate_type1(res):
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
    return _proximate_core(res["coalFC"], res["coalVM"], res["coalAsh"], res["coalMoist"], gcv_scaling=True, coalGCV=res["coalGCV"])


def proximate_to_ultimate_type14(res):
    err = _validate_proximate_inputs(res, ["coalFC", "coalVM", "coalAsh", "coalMoist"])
    if err:
        return err
    return _proximate_core(res["coalFC"], res["coalVM"], res["coalAsh"], res["coalMoist"])


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