def coal_flow_calculation(res):
    for i in ["boilerSteamFlow", "msTemp", "msPres", "fwTemp", "coalGCV", "boilerEfficiency"]:
        if str(i) not in res:
            return {"error": str(i) + " missing or '0' found"}, 400
    result = {'coalFlow': 0, 'costOfFuel': 0}
    mssteam = IAPWS97(T=(res["msTemp"] + 273), P=(res["msPres"] * 0.0980665))
    fwsteam = IAPWS97(T=(res["fwTemp"] + 273), x=0)
    entDiff = (mssteam.h / 4.1868) - (fwsteam.h / 4.1868)
    result["entDiff"] = entDiff
    landingCost = res.get("landingCost", 2500)
    if (res["boilerSteamFlow"] != 0) or (res["boilerEfficiency"] != 0):
        coalFlow = (res["boilerSteamFlow"] * entDiff) / (res["boilerEfficiency"] * res["coalGCV"])
        result['coalFlow'] = round(coalFlow, 4)
        result['costOfFuel'] = landingCost * result['coalFlow']
        result['costPerUnitSteam'] = result["costOfFuel"] / res["boilerSteamFlow"]
        return result
    else:
        return result