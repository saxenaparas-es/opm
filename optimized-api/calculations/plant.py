def plant_heat_rate(res):
    ble, thr = 0.0, 0.0
    if (len(res["boilerEfficiency"]) != len(res["boilerSteamFlow"])) or (len(res["turbineHeatRate"]) != len(res["turbineSteamFlow"])):
        return {"error": "bad request"}, 400
    if (sum(res["boilerSteamFlow"]) == 0) or (sum(res["turbineSteamFlow"]) == 0):
        for i in range(len(res["boilerEfficiency"])):
            ble = ble + (res["boilerEfficiency"][i] * res["boilerSteamFlow"][i])
        ble /= sum(res["boilerSteamFlow"])
        return {"plantHeatRate": 0.0, "averageBoilerEfficiency": ble}
    ble, thr = 0.0, 0.0
    for i in range(len(res["boilerEfficiency"])):
        ble = ble + (res["boilerEfficiency"][i] * res["boilerSteamFlow"][i])
    ble /= sum(res["boilerSteamFlow"])
    for i in range(len(res["turbineHeatRate"])):
        thr = thr + (res["turbineHeatRate"][i] * res["turbineSteamFlow"][i])
    thr /= sum(res["turbineSteamFlow"])
    plantHeatRate = (thr * 100.0) / ble
    averageBoilerEfficiency = ble
    res["plantHeatRate"] = plantHeatRate
    res["averageBoilerEfficiency"] = averageBoilerEfficiency
    return res