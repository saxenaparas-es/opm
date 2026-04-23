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


def thr_pressureInMpa_calcs(res):
    from _imports import IAPWS97
    
    res["totalShSprayWater"] = res.get("ShSprayWater01", 0) + res.get("ShSprayWater02", 0)
    res["enthalpyMS"] = IAPWS97(T=(res["steamTempMS"] + 273), P=(res["steamPressureMS"])).h
    res["enthalpyFW"] = IAPWS97(T=(res["FWFinalTemp"] + 273), P=(res["FWFinalPress"])).h
    
    res["HptSteamExhaustEnthalpy"] = IAPWS97(T=(res["HptExhaustTemp"] + 273), P=(res["HptExhaustPressure"])).h
    res["IptInletSteamEnthalpy"] = IAPWS97(T=(res["IptInletSteamTemp"] + 273), P=(res["IptInletSteamPress"])).h
    res["FeedWaterInletBeforeEcoEnthalpy"] = IAPWS97(T=(res["FWFinalTemp"] + 273), P=(res["FWFinalPress"])).h
    
    if res.get("totalShSprayWater", 0) > 0.0:
        res["ShSprayWaterEnthalpy"] = IAPWS97(T=(res.get("ShRhSprayWaterTemp", res["FWFinalTemp"]) + 273), P=(res["FWFinalPress"])).h + res.get("SprayWaterEnthalpyConstant", 0)
    else:
        res["ShSprayWaterEnthalpy"] = res.get("SprayWaterEnthalpyConstant", 0)
    
    if res.get("RhSprayWater", 0) > 0.0:
        res["RhSprayWaterEnthalpy"] = IAPWS97(T=(res.get("ShRhSprayWaterTemp", res["FWFinalTemp"]) + 273), P=(res["FWFinalPress"])).h + res.get("SprayWaterEnthalpyConstant", 0)
    else:
        res["RhSprayWaterEnthalpy"] = res.get("SprayWaterEnthalpyConstant", 0)
    
    res["FeedWaterInletToHph8Enthalpy"] = IAPWS97(T=(res["FeedWaterInletTempToHph8"] + 273), P=(res["FWFinalPress"])).h + res.get("FeedWaterInletToHph8EnthalpyConstant", 0)
    res["FeedWaterOutletToHph8Enthalpy"] = IAPWS97(T=(res["FeedWaterOutletTempToHph8"] + 273), P=(res["FWFinalPress"])).h + res.get("FeedWaterOutletToHph8EnthalpyConstant", 0)
    res["ExtractionSteamHph8Enthalpy"] = IAPWS97(T=(res["ExtractionSteamTempHph8"] + 273), P=(res["ExtractionSteamPressureHph8"])).h + res.get("ExtractionSteamHph8EnthalpyConstant", 0)
    res["DripHph8Enthalpy"] = IAPWS97(T=(res["DripTemperatureHph8"] + 273), P=(res["ExtractionSteamPressureHph8"])).h
    res["ExtractionSteamFlowHph8"] = res["FeedWaterFlow"] * (res["FeedWaterOutletToHph8Enthalpy"] - res["FeedWaterInletToHph8Enthalpy"]) / (res["ExtractionSteamHph8Enthalpy"] - res["DripHph8Enthalpy"])
    
    if res["ExtractionSteamPressureHph8"] < 1.0:
        res["ExtractionSteamFlowHph8"] = 0.0
    
    res["FeedWaterInletToHph7Enthalpy"] = IAPWS97(T=(res["FeedWaterInletTempToHph7"] + 273), P=(res["FWFinalPress"])).h + res.get("FeedWaterInletToHph7EnthalpyConstant", 0)
    res["FeedWaterOutletToHph7Enthalpy"] = res["FeedWaterInletToHph8Enthalpy"]
    res["ExtractionSteamHph7Enthalpy"] = IAPWS97(T=(res["ExtractionSteamTempHph7"] + 273), P=(res["ExtractionSteamPressureHph7"])).h + res.get("ExtractionSteamHph7EnthalpyConstant", 0)
    res["DripHph7Enthalpy"] = IAPWS97(T=(res["DripTemperatureHph7"] + 273), P=(res["ExtractionSteamPressureHph7"])).h + res.get("DripHph7EnthalpyConstant", 0)
    
    res["ExtractionSteamFlowHph7"] = (res["FeedWaterFlow"] * (res["FeedWaterOutletToHph7Enthalpy"] - res["FeedWaterInletToHph7Enthalpy"]) - res["ExtractionSteamFlowHph8"] * (res["DripHph8Enthalpy"] - res["DripHph7Enthalpy"])) / (res["ExtractionSteamHph7Enthalpy"] - res["DripHph7Enthalpy"]) - 0.08
    
    if res["ExtractionSteamPressureHph7"] < 0.5:
        res["ExtractionSteamFlowHph7"] = 0.0
    
    try:
        res["FeedWaterInletToHph6Enthalpy"] = IAPWS97(T=(res.get("FeedWaterInletTempToHph6", res["FeedWaterInletTempToHph7"]) + 273), P=(res["FWFinalPress"])).h - res.get("FeedWaterInletToHph6EnthalpyConstant", 0)
        res["FeedWaterOutletToHph6Enthalpy"] = IAPWS97(T=(res.get("FeedWaterInletTempToHph7", res["FeedWaterInletTempToHph7"]) + 273), P=(res["FWFinalPress"])).h - res.get("FeedWaterOutletToHph6EnthalpyConstant", 0)
        res["ExtractionSteamHph6Enthalpy"] = IAPWS97(T=(res.get("ExtractionSteamTempHph6", res["ExtractionSteamTempHph7"]) + 273), P=(res.get("ExtractionSteamPressureHph6", res["ExtractionSteamPressureHph7"]))).h + res.get("ExtractionSteamHph6EnthalpyConstant", 0)
        res["DripHph6Enthalpy"] = IAPWS97(T=(res.get("DripTemperatureHph6", res["DripTemperatureHph7"]) + 273), P=(res.get("ExtractionSteamPressureHph6", res["ExtractionSteamPressureHph7"]))).h + res.get("DripHph6EnthalpyConstant", 0)
        
        res["ExtractionSteamFlowHph6"] = (res["FeedWaterFlow"] * (res["FeedWaterOutletToHph6Enthalpy"] - res["FeedWaterInletToHph6Enthalpy"]) - (res["ExtractionSteamFlowHph8"] + res["ExtractionSteamFlowHph7"]) * (res["DripHph7Enthalpy"] - res["DripHph6Enthalpy"])) / (res["ExtractionSteamHph6Enthalpy"] - res["DripHph6Enthalpy"]) - 0.259
    except Exception as e:
        res["ExtractionSteamFlowHph6"] = 0.0
        res["FeedWaterInletToHph6Enthalpy"] = 0.0
        res["FeedWaterOutletToHph6Enthalpy"] = 0.0
        res["ExtractionSteamHph6Enthalpy"] = 0.0
        res["DripHph6Enthalpy"] = 0.0
    
    if res.get("ExtractionSteamPressureHph6", 1.0) < 0.5:
        res["ExtractionSteamFlowHph6"] = 0.0
    
    try:
        res["condensateInletHph5Enthalpy"] = IAPWS97(T=(res.get("condensateInletTempHph5", 80) + 273), P=(res.get("condensateInletWaterPress", 12.74))).h
        res["condensateOutletHph5Enthalpy"] = IAPWS97(T=(res.get("FeedWaterInletTempToHph6", res.get("FeedWaterInletTempToHph7", 100)) + 273), P=12.74).h
        res["ExtractionSteamHph5Enthalpy"] = IAPWS97(T=(res.get("extractionSteamTempHph5", 150) + 273), P=(res.get("extractionSteamPressureHph5", 1.0))).h
        
        res["extractionSteamFlowHph5"] = (res.get("condensateFlow", 0) * (res["condensateOutletHph5Enthalpy"] - res["condensateInletHph5Enthalpy"]) - (res["ExtractionSteamFlowHph8"] + res["ExtractionSteamFlowHph7"] + res["ExtractionSteamFlowHph6"] + 0.834 + 3.81) * (res["DripHph6Enthalpy"] - res["condensateOutletHph5Enthalpy"])) / (res["ExtractionSteamHph5Enthalpy"] - res["condensateOutletHph5Enthalpy"]) - 0.02
    except Exception as e:
        res["extractionSteamFlowHph5"] = 0.0
        res["condensateInletHph5Enthalpy"] = 0.0
        res["condensateOutletHph5Enthalpy"] = 0.0
        res["ExtractionSteamHph5Enthalpy"] = 0.0
    
    if res.get("extractionSteamPressureHph5", 0.5) < 0.3:
        res["extractionSteamFlowHph5"] = 0.0
    
    res["finalFeedWaterFlow_CalculatedFromCondensateFlow"] = res.get("extractionSteamFlowHph5", 0) + res.get("condensateFlow", 0) + res["ExtractionSteamFlowHph6"] + res["ExtractionSteamFlowHph7"] + res["ExtractionSteamFlowHph8"] - res.get("RhSprayWater", 0) - res["totalShSprayWater"] + 0.011
    
    res["computedMainSteamFlow_computedFWFlow"] = res["finalFeedWaterFlow_CalculatedFromCondensateFlow"] + res["totalShSprayWater"]
    
    res["HrhSteamFlow"] = res["steamFlowMS"] - res["ExtractionSteamFlowHph7"] - res["ExtractionSteamFlowHph8"] - res.get("GlandSteamFlow_LeakOff_InterStageLeakage", 0)
    
    res["turbineHeatRate"] = ((res["steamFlowMS"] * (res["enthalpyMS"] - res["enthalpyFW"]) + res["HrhSteamFlow"] * (res["IptInletSteamEnthalpy"] - res["HptSteamExhaustEnthalpy"]) + res["totalShSprayWater"] * (res["enthalpyFW"] - res["ShSprayWaterEnthalpy"]) + res.get("RhSprayWater", 0) * (res["IptInletSteamEnthalpy"] - res["RhSprayWaterEnthalpy"])) / res["load"]) / 4.186
    
    return {"turbineHeatRate": res["turbineHeatRate"]}