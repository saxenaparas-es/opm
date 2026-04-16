from _imports import get_steam_enthalpy


def thr_cogent(res):
    enthalpyMS = get_steam_enthalpy(res["steamTempMS"], res["steamPressureMS"])
    enthalpyFW = get_steam_enthalpy(res["FWFinalTemp"], res["FWFinalPress"])
    enthalpyProSteam = get_steam_enthalpy(res["ProSteamTemp"], res["ProSteamPress"])
    enthalpyMakeup = get_steam_enthalpy(68, 10)
    
    make = {}
    make["steamFlowMS"] = res["steamFlowMS"]
    make["enthalpyMS"] = enthalpyMS
    make["enthalpyFW"] = enthalpyFW
    make["FWFlow"] = res["FWFlow"]
    
    if "processFlow" in res:
        make["processFlow"] = res["processFlow"]
    else:
        res["processFlow"] = res["makeUpFlow"]
    
    make["enthalpyProSteam"] = enthalpyProSteam
    make["enthalpyMakeup"] = enthalpyMakeup
    
    if "processFlow" in res:
        thr = (res["steamFlowMS"] * enthalpyMS) - (res["FWFlow"] * enthalpyFW) - (res["processFlow"] * enthalpyProSteam) + (res["makeUpFlow"] * enthalpyMakeup)
    else:
        thrEntSum1 = enthalpyMS + enthalpyMakeup
        thrEntSum2 = enthalpyFW + enthalpyProSteam
        thr = thrEntSum1 - thrEntSum2
    
    thr = thr / (res["load"])
    return {"turbineHeatRate": thr}


def thr_cogent2(res):
    enthalpyMS = get_steam_enthalpy(res["steamTempMS"], res["steamPressureMS"])
    enthalpyFW = get_steam_enthalpy(res["FWFinalTemp"], res["FWFinalPress"])
    enthalpyMakeupFlw = get_steam_enthalpy(35, 10.135)
    return {"turbineHeatRate": ((res["steamFlowMS"] * enthalpyMS) + (res["makeUpFlow"] * enthalpyMakeupFlw) - (res["steamFlowMS"] * enthalpyFW)) / res["load"]}


def thr_cogent3(res):
    stgSteamEnthalpy = (res["steamFlowMS"]) * get_steam_enthalpy(res["stgIlTemp"], res["stgIlPres"]) / 4.1868
    hpProSteamEnthalpy = (res["hpProIlFlow"]) * get_steam_enthalpy(res["hpProIlTemp"], res["hpProIlPres"]) / 4.1868
    lp1ProSteamEnthalpy = (res["lpPro1IlFlow"]) * get_steam_enthalpy(res["lpPro1IlTemp"], 10.2) / 4.1868
    lp2ProSteamEnthalpy = (res["lpPro2IlFlow"]) * get_steam_enthalpy(res["lpPro2IlTemp"], 9.7) / 4.1868
    fwSteamEnthalpy = (res["fwFlow"]) * get_steam_enthalpy(res["fwTemp"], res["fwPres"]) / 4.1868
    hpLpConSteamEnthalpy = (res["hpLpConReturnFlow"]) * get_steam_enthalpy(res["hpLpConReturnTemp"], 10.0) / 4.1868
    mkpSteamEnthalpy = (res["makeupIlFlow"]) * get_steam_enthalpy(35.0, 10.0) / 4.1868
    thrEntSum1 = stgSteamEnthalpy + hpLpConSteamEnthalpy + mkpSteamEnthalpy
    thrEntSum2 = hpProSteamEnthalpy + lp1ProSteamEnthalpy + lp2ProSteamEnthalpy + fwSteamEnthalpy
    thr = (thrEntSum1 - thrEntSum2) / res["load"]
    return {"turbineHeatRate": thr}


def thr_cogent4(res):
    stgSteamEnthalpy = (res["steamFlowMS"]) * get_steam_enthalpy(res["stgIlTemp"], res["stgIlPres"]) / 4.1868
    
    if "hpProIlTemp" in res:
        hpProSteamEnthalpy = (res.get("hpProIlFlow", res["steamFlowMS"])) * get_steam_enthalpy(res["hpProIlTemp"], res["hpProIlPres"]) / 4.1868
        lpProSteamEnthalpy = (res["lpPro1IlFlow"]) * get_steam_enthalpy(res.get("lpPro1IlTemp", 80), res.get("lpPro1IlPres", 9.8)) / 4.1868
    else:
        hpProSteamEnthalpy = 0
        lpProSteamEnthalpy = 0
    
    fwSteamEnthalpy = (res["fwFlow"]) * get_steam_enthalpy(res["fwTemp"], res["fwPres"]) / 4.1868
    
    if "makeupIlTemp" in res:
        mkpSteamEnthalpy = (res["makeupIlFlow"]) * get_steam_enthalpy(res["makeupIlTemp"], 9.8) / 4.1868
    else:
        mkpSteamEnthalpy = 0
    
    if "hpProIlTemp" in res:
        thrEntSum1 = stgSteamEnthalpy + lpProSteamEnthalpy + mkpSteamEnthalpy
        thrEntSum2 = hpProSteamEnthalpy + fwSteamEnthalpy
    else:
        thrEntSum1 = stgSteamEnthalpy + mkpSteamEnthalpy
        thrEntSum2 = fwSteamEnthalpy
    
    thr = (thrEntSum1 - thrEntSum2) / res["load"]
    return {"turbineHeatRate": thr}


def thr_cogent5(res):
    stgSteamEnthalpy = (res["steamFlowMS"]) * get_steam_enthalpy(res["stgIlTemp"], res["stgIlPres"]) / 4.1868
    mkpSteamEnthalpy = (res["makeupIlFlow"]) * get_steam_enthalpy(res["makeupIlTemp"], 9.8) / 4.1868
    
    if "hpProIlTemp" in res:
        hpProSteamEnthalpy = (res.get("hpProIlFlow", res["steamFlowMS"])) * get_steam_enthalpy(res["hpProIlTemp"], res["hpProIlPres"]) / 4.1868
        lpProSteamEnthalpy = (res["lpPro1IlFlow"]) * get_steam_enthalpy(res["lpProIlTemp"], 9.8) / 4.1868
        thrEntSum1 = stgSteamEnthalpy + lpProSteamEnthalpy + mkpSteamEnthalpy
        thrEntSum2 = hpProSteamEnthalpy
    else:
        thrEntSum1 = stgSteamEnthalpy + mkpSteamEnthalpy
        thrEntSum2 = 0
    
    thr = (thrEntSum1 - thrEntSum2) / res["load"]
    return {"turbineHeatRate": thr}


def thr_cogent6(res):
    stgSteamEnthalpy = (res["steamFlowMS"]) * get_steam_enthalpy(res["stgIlTemp"], res["stgIlPres"]) / 4.1868
    turbineExhaustSteamEnthalpy = (res["steamFlowMS"]) * get_steam_enthalpy(res["turbineExhaustSteamTemp"], res["turbineExhaustSteamPressure"]) / 4.1868
    
    if "makeupIlTemp" in res:
        mkpSteamEnthalpy = (res["makeupIlFlow"]) * get_steam_enthalpy(res["makeupIlTemp"], res['makeupIlPressure']) / 4.1868
        thrEntSum1 = stgSteamEnthalpy + mkpSteamEnthalpy
        thrEntSum2 = turbineExhaustSteamEnthalpy
    else:
        thrEntSum1 = stgSteamEnthalpy
        thrEntSum2 = turbineExhaustSteamEnthalpy
    
    thr = (thrEntSum1 - thrEntSum2) / res["load"]
    return {"turbineHeatRate": thr}


def thr_cogent7(res):
    stgSteamEnthalpy = (res["steamFlowMS"]) * get_steam_enthalpy(res["stgIlTemp"], res["stgIlPres"]) / 4.1868
    hpProSteamEnthalpy = (res["hpProIlFlow"]) * get_steam_enthalpy(res["hpProIlTemp"], res["hpProIlPres"]) / 4.1868
    mkpDeaeratorSteamEnthalpy = (res["MakeupDeaeratorFlow"]) * get_steam_enthalpy(res["MakeupDeaeratorIlTemp"], res["MakeupDeaeratorPres"]) / 4.1868
    mkpHotwellSteamEnthalpy = (res["makeupHotwellFlow"]) * get_steam_enthalpy(res["MakeupDeaeratorIlTemp"], res["MakeupDeaeratorPres"]) / 4.1868
    fwSteamEnthalpy = (res["fwFlow"]) * get_steam_enthalpy(res["fwTemp"], res["fwPres"]) / 4.1868
    thrEntSum1 = stgSteamEnthalpy + mkpDeaeratorSteamEnthalpy + mkpHotwellSteamEnthalpy
    thrEntSum2 = fwSteamEnthalpy
    thr = (thrEntSum1 - thrEntSum2) / res["load"]
    return {"turbineHeatRate": thr}


def thr_cogent8(res):
    stgSteamEnthalpy = (res["steamFlowMS"]) * get_steam_enthalpy(res["stgIlTemp"], res["stgIlPres"]) / 4.1868
    
    try:
        Process1SteamEnthalpy = (res["ProcessFlow1"]) * get_steam_enthalpy(res["Process1Temp"], res["Process1Pres"]) / 4.1868
    except:
        Process1SteamEnthalpy = 0
    
    try:
        Process2SteamEnthalpy = (res["ProcessFlow2"]) * get_steam_enthalpy(res["Process2Temp"], res["Process2Pres"]) / 4.1868
    except:
        Process2SteamEnthalpy = 0
    
    fwSteamEnthalpy = (res["fwFlow"]) * get_steam_enthalpy(res["fwTemp"], res["fwPres"]) / 4.1868
    ConDearatorSteamEnthalpy = (res["CondDearatorFlow"]) * get_steam_enthalpy(res["CondDearatorTemp"], res["CondDearatorPres"]) / 4.1868
    mkpSteamEnthalpy = (res["makeupIlFlow"]) * get_steam_enthalpy(res["makeupTemp"], res["makeupPres"]) / 4.1868
    
    thrEntSum1 = stgSteamEnthalpy + ConDearatorSteamEnthalpy + mkpSteamEnthalpy
    thrEntSum2 = fwSteamEnthalpy + Process1SteamEnthalpy + Process2SteamEnthalpy
    thr = (thrEntSum1 - thrEntSum2) / res["load"]
    return {"turbineHeatRate": thr}


def thr_ingest(res):
    enthalpyMS = get_steam_enthalpy(res["steamTempMS"], res["steamPressureMS"])
    enthalpyIG = get_steam_enthalpy(res["ingestSteamTemp"], res["ingestSteamPressure"])
    enthalpyDisSteam = get_steam_enthalpy(res["dischargeSteamTemp"], 11.5)
    enthalpyMakeup = get_steam_enthalpy(40, 10)
    
    make = {}
    make["steamFlowMS"] = res["steamFlowMS"]
    make["ingestSteamFlow"] = res["ingestSteamFlow"]
    make["enthalpyMS"] = enthalpyMS
    make["enthalpyIG"] = enthalpyIG
    make["enthalpyDisSteam"] = enthalpyDisSteam
    make["enthalpyMakeup"] = enthalpyMakeup
    
    thr = ((make["steamFlowMS"] * (enthalpyMS - enthalpyDisSteam)) + (make["ingestSteamFlow"] * (enthalpyIG - enthalpyDisSteam)))
    thr = thr / (res["load"])
    return {"turbineHeatRate": thr}


def thr_ingest2(res):
    enthalpyMS = get_steam_enthalpy(res["steamTempMS"], res["steamPressureMS"])
    enthalpyIG = get_steam_enthalpy(res["ingestSteamTemp"], res["ingestSteamPressure"])
    enthalpycondenseSteam = get_steam_enthalpy(res["condensateSteamTemp"], res["condensateteamPressure"])
    enthalpyMakeup = get_steam_enthalpy(35, 2.1)
    
    make = {}
    make["steamFlowMS"] = res["steamFlowMS"]
    make["ingestSteamFlow"] = res["ingestSteamFlow"]
    make["enthalpyMS"] = enthalpyMS
    make["enthalpyIG"] = enthalpyIG
    make["enthalpyDisSteam"] = enthalpycondenseSteam
    make["enthalpyMakeup"] = enthalpyMakeup
    
    thr = ((make["steamFlowMS"] * (enthalpyMS - enthalpycondenseSteam)) + (make["ingestSteamFlow"] * (enthalpyIG - enthalpycondenseSteam)))
    thr = thr / (res["load"])
    return {"turbineHeatRate": thr}


def thr_default(res):
    enthalpyMS = get_steam_enthalpy(res["steamTempMS"], res["steamPressureMS"])
    enthalpyFW = get_steam_enthalpy(res["FWFinalTemp"], res["FWFinalPress"])
    return {"turbineHeatRate": (res["steamFlowMS"] * (enthalpyMS - enthalpyFW)) / res["load"]}