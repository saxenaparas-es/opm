from _imports import math


def _boiler_base_required(res, hydrogen_factor=0.348, oxygen_factor=0.0435):
    return 0.116 * res['carbon'] + hydrogen_factor * res['hydrogen'] + 0.0435 * res['coalSulphur'] - oxygen_factor * res['oxygen']


def _boiler_excess_air(o2):
    return (o2 * 100) / (21 - o2)


def _boiler_actual_air(theo_air, excess_air):
    return (1 + excess_air / 100) * theo_air


def _boiler_temp_diff(flue_temp, ambient_temp):
    return flue_temp - ambient_temp


def _boiler_loss_h2o_in_fuel(moist, temp_diff, gcv):
    return moist * (584 + 0.45 * temp_diff) / gcv


def _boiler_loss_h2_in_fuel(hydrogen, temp_diff, gcv):
    return 8.937 * (584 + 0.45 * temp_diff) * hydrogen / gcv


def _boiler_loss_h2_in_fuel_v2(hydrogen, temp_diff, gcv):
    return 9 * (584 + 0.45 * temp_diff) * hydrogen / gcv


def _boiler_mass_dry_flue_gas(carbon, sulphur, nitrogen, actual_air, theo_air):
    return (carbon * 44 / 12 + sulphur * 64 / 32 + nitrogen + actual_air * 77 + (actual_air - theo_air) * 23) / 100


def _boiler_loss_dry_flue_gas(mass, temp_diff, gcv, factor=0.23):
    return mass * factor * temp_diff * 100 / gcv


def _boiler_loss_ash_ubc(ash_ratio, ash, unburnt_carbon, gcv, unburnt_factor=8080):
    return ash_ratio * ash * unburnt_carbon * unburnt_factor / (100 * gcv)


def _boiler_loss_ash_ubc_v2(ash, ash_ratio, unburnt_carbon, gcv, unburnt_factor=8080):
    return (((ash / 100) * ash_ratio * unburnt_carbon * unburnt_factor) / (100 - unburnt_carbon)) * 100 / gcv


def _boiler_loss_sensible_ash(ash_ratio, ash, temp_diff, gcv, factor=0.22):
    return ((ash / 100) * ash_ratio * factor) * temp_diff * 100 / gcv


def _boiler_loss_h2o_in_air(humidity_factor, actual_air, temp_diff, gcv):
    return humidity_factor * actual_air * 0.45 * temp_diff * 100 / gcv


def boiler_efficiency_type1(res):
    required = ["carbon", "hydrogen", "coalSulphur", "oxygen", "aphFlueGasOutletO2", "coalMoist", "aphFlueGasOutletTemp", "ambientAirTemp", "coalGCV", "coalAsh", "airHumidityFactor", "LossUnaccounted", "LossDueToRadiation", "flyAshUnburntCarbon", "bedAshUnburntCarbon"]
    for i in required:
        if i not in res:
            return {"error": str(i) + " missing"}, 400
    
    temp_diff = _boiler_temp_diff(res['aphFlueGasOutletTemp'], res['ambientAirTemp'])
    theo_air = _boiler_base_required(res)
    excess_air = _boiler_excess_air(res['aphFlueGasOutletO2'])
    actual_air = _boiler_actual_air(theo_air, excess_air)
    mass_dry_flue_gas = _boiler_mass_dry_flue_gas(res['carbon'], res['coalSulphur'], res.get('nitrogen', 0), actual_air, theo_air)
    
    result = {
        'TheoAirRequired': theo_air,
        'ExcessAir': excess_air,
        'LossDueToH2OInFuel': _boiler_loss_h2o_in_fuel(res['coalMoist'], temp_diff, res['coalGCV']),
        'LossDueToH2InFuel': _boiler_loss_h2_in_fuel(res['hydrogen'], temp_diff, res['coalGCV']),
        'LossBedAshUBC': _boiler_loss_ash_ubc_v2(res['coalAsh'], 0.15, res['bedAshUnburntCarbon'], res['coalGCV']),
        'LossFlyAshUBC': _boiler_loss_ash_ubc_v2(res['coalAsh'], 0.85, res['flyAshUnburntCarbon'], res['coalGCV']),
        'LossSensibleBedAsh': _boiler_loss_sensible_ash(0.15, res['coalAsh'], temp_diff, res['coalGCV']),
        'LossSensibleFlyAsh': _boiler_loss_sensible_ash(0.85, res['coalAsh'], temp_diff, res['coalGCV']),
        'LossDueToRadiation': res['LossDueToRadiation'],
        'LossUnaccounted': res['LossUnaccounted'],
    }
    result['ActualAirSupplied'] = actual_air
    result['LossDueToH2OInAir'] = _boiler_loss_h2o_in_air(res['airHumidityFactor'], actual_air, temp_diff, res['coalGCV'])
    result['massofDryFlueGas'] = mass_dry_flue_gas
    result['LossDueToDryFlueGas'] = _boiler_loss_dry_flue_gas(mass_dry_flue_gas, temp_diff, res['coalGCV'])
    result['LossTotal'] = result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] + result['LossSensibleBedAsh'] + result['LossSensibleFlyAsh'] + result['LossUnaccounted'] + result['LossDueToRadiation']
    result['boilerEfficiency'] = 100 - result['LossTotal']
    return result


def boiler_efficiency_type2(res):
    result = {}
    temp_diff = _boiler_temp_diff(res['aphFlueGasOutletTemp'], res['ambientAirTemp'])
    theo_air = _boiler_base_required(res)
    o2_adjusted = res["aphFlueGasOutletO2"] + res["airIngressConstant"]
    excess_air = _boiler_excess_air(o2_adjusted)
    actual_air = _boiler_actual_air(theo_air, excess_air)
    mass_dry_flue_gas = _boiler_mass_dry_flue_gas(res['carbon'], res['coalSulphur'], res.get('nitrogen', 0), actual_air, theo_air)
    
    result["LossESPAshUBC"] = _boiler_loss_ash_ubc(0.65, res["coalAsh"], res["espAshUnburntCarbon"], res["coalGCV"])
    result["LossBottomAshUBC"] = _boiler_loss_ash_ubc(0.05, res["coalAsh"], res["bedAshUnburntCarbon"], res["coalGCV"])
    if "cycloneAshUnburntCarbon" in res:
        result["LossCycloneAshUBC"] = _boiler_loss_ash_ubc(0.25, res["coalAsh"], res["cycloneAshUnburntCarbon"], res["coalGCV"])
        result["LossAPHAshUBC"] = _boiler_loss_ash_ubc(0.05, res["coalAsh"], res["aphAshUnburntCarbon"], res["coalGCV"])
    result["LossESPAshSensible"] = _boiler_loss_sensible_ash(0.65, res["coalAsh"], temp_diff, res["coalGCV"], 0.23)
    result["LossBottomAshSensible"] = res["coalAsh"] * 5 / 10000 * 0.23 * (res["bedAshTemp"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
    result["LossCycloneAshSensible"] = res["coalAsh"] * 25 / 10000 * 0.23 * (res["cycloneAshTemp"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
    result["LossAPHAshSensible"] = res["coalAsh"] * 5 / 10000 * 0.23 * temp_diff * 100 / res["coalGCV"]
    result["LossDueToH2InFuel"] = _boiler_loss_h2_in_fuel(res["hydrogen"], temp_diff, res["coalGCV"])
    result["LossDueToH2OInFuel"] = _boiler_loss_h2o_in_fuel(res["coalMoist"], temp_diff, res["coalGCV"])
    result["LossDueToRadiation"] = res["lossDueToRadiation"]
    result["LossDueToPartialCombustion"] = res["partialCombustionLoss"]
    result["LossPlantSpecific"] = res["plantSpecificLoss"]
    result["TheoAirRequired"] = theo_air
    result["aphFlueGasOutletO2"] = o2_adjusted
    result["ExcessAir"] = excess_air
    result["ActualAirSupplied"] = actual_air
    result["massofDryFlueGas"] = mass_dry_flue_gas
    result["LossDueToH2OInAir"] = _boiler_loss_h2o_in_air(res["airHumidityFactor"], actual_air, temp_diff, res["coalGCV"])
    result["LossDueToDryFlueGas"] = _boiler_loss_dry_flue_gas(mass_dry_flue_gas, temp_diff, res["coalGCV"], 0.24)
    if "cycloneAshUnburntCarbon" in res:
        result["LossTotalUBC"] = result["LossESPAshUBC"] + result["LossBottomAshUBC"] + result["LossCycloneAshUBC"] + result["LossAPHAshUBC"]
    else:
        result["LossTotalUBC"] = result["LossESPAshUBC"] + result["LossBottomAshUBC"]
    result["LossTotalSensible"] = result["LossESPAshSensible"] + result["LossBottomAshSensible"] + result.get("LossCycloneAshSensible", 0) + result.get("LossAPHAshSensible", 0)
    result["LossTotal"] = result["LossTotalUBC"] + result["LossTotalSensible"] + result["LossDueToDryFlueGas"] + result["LossDueToH2OInFuel"] + result["LossDueToH2InFuel"] + result["LossDueToH2OInAir"] + result["LossDueToPartialCombustion"] + result["LossPlantSpecific"] + res["lossDueToRadiation"]
    result["boilerEfficiency"] = 100 - result["LossTotal"]
    return result


def boiler_efficiency_type3(res):
    required = ["carbon", "hydrogen", "coalSulphur", "oxygen", "aphFlueGasOutletO2", "coalMoist", "aphFlueGasOutletTemp", "ambientAirTemp", "coalGCV", "coalAsh", "airHumidityFactor", "LossUnaccounted", "LossDueToRadiation", "flyAshUnburntCarbon", "bedAshUnburntCarbon"]
    for i in required:
        if i not in res:
            return {"error": str(i) + " missing"}, 400
    
    temp_diff = _boiler_temp_diff(res['aphFlueGasOutletTemp'], res['ambientAirTemp'])
    theo_air = _boiler_base_required(res)
    excess_air = _boiler_excess_air(res['aphFlueGasOutletO2'])
    actual_air = _boiler_actual_air(theo_air, excess_air)
    mass_dry_flue_gas = _boiler_mass_dry_flue_gas(res['carbon'], res['coalSulphur'], res.get('nitrogen', 0), actual_air, theo_air)
    
    result = {
        'TheoAirRequired': theo_air,
        'ExcessAir': excess_air,
        'LossDueToH2OInFuel': _boiler_loss_h2o_in_fuel(res['coalMoist'], temp_diff, res['coalGCV']),
        'LossDueToH2InFuel': _boiler_loss_h2_in_fuel(res['hydrogen'], temp_diff, res['coalGCV']),
        'LossBedAshUBC': _boiler_loss_ash_ubc(0.10, res['coalAsh'], res['bedAshUnburntCarbon'], res['coalGCV']),
        'LossFlyAshUBC': _boiler_loss_ash_ubc(0.90, res['coalAsh'], res['flyAshUnburntCarbon'], res['coalGCV']),
        'LossDueToRadiation': res['LossDueToRadiation'],
        'LossUnaccounted': res['LossUnaccounted'],
    }
    result['LossFlueGasUBC'] = res['COInFlueGasPPM'] * 28 * 5654 * 100 / ((10 ** 6) * res['coalGCV'])
    result['ActualAirSupplied'] = actual_air
    result['LossDueToH2OInAir'] = _boiler_loss_h2o_in_air(res['airHumidityFactor'], actual_air, temp_diff, res['coalGCV'])
    result['massofDryFlueGas'] = mass_dry_flue_gas
    result['LossDueToDryFlueGas'] = _boiler_loss_dry_flue_gas(mass_dry_flue_gas, temp_diff, res['coalGCV'], 0.24)
    result['LossTotal'] = result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] + result['LossUnaccounted'] + result['LossDueToRadiation'] + result['LossFlueGasUBC']
    result['boilerEfficiency'] = 100 - result['LossTotal']
    return result


def boiler_efficiency_type4(res):
    temp_diff = _boiler_temp_diff(res['aphFlueGasOutletTemp'], res['ambientAirTemp'])
    theo_air = 0.116 * res['carbon'] + 0.03975 * res['hydrogen'] + 0.0435 * res['coalSulphur'] - 0.03975 * res['oxygen']
    excess_air = _boiler_excess_air(res['aphFlueGasOutletO2'])
    actual_air = _boiler_actual_air(theo_air, excess_air)
    mass_dry_flue_gas = _boiler_mass_dry_flue_gas(res['carbon'], 0, res.get('nitrogen', 0), actual_air, theo_air)
    
    result = {
        'TheoAirRequired': theo_air,
        'ExcessAir': excess_air,
        'LossDueToH2OInFuel': _boiler_loss_h2o_in_fuel(res['coalMoist'], temp_diff, res['coalGCV']),
        'LossDueToH2InFuel': _boiler_loss_h2_in_fuel_v2(res['hydrogen'], temp_diff, res['coalGCV']),
        'LossFlueGasUBC': (res["COPerInFlueGas"] * res['carbon'] / (res["COPerInFlueGas"] + res["CO2PerInFlueGas"])) * (5744 / res['coalGCV']) * 100,
        'LossDueToRadiation': res['LossDueToRadiation'],
        'LossBedAshUBC': _boiler_loss_ash_ubc(0.10, res['coalAsh'], res['bedAshUnburntCarbon'], res['coalGCV']),
        'LossFlyAshUBC': _boiler_loss_ash_ubc(0.90, res['coalAsh'], res['flyAshUnburntCarbon'], res['coalGCV'])
    }
    result['ActualAirSupplied'] = actual_air
    result['massofDryFlueGas'] = mass_dry_flue_gas
    result['LossDueToDryFlueGas'] = _boiler_loss_dry_flue_gas(mass_dry_flue_gas, temp_diff, res['coalGCV'])
    result['LossDueToH2OInAir'] = _boiler_loss_h2o_in_air(res['airHumidityFactor'], actual_air, temp_diff, res['coalGCV'])
    result['LossTotal'] = result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] + result['LossFlueGasUBC'] + result['LossDueToRadiation']
    result['boilerEfficiency'] = 100 - result['LossTotal']
    return result


def boiler_efficiency_type5(res):
    required = ['carbon', 'hydrogen', 'coalSulphur', 'oxygen', 'aphFlueGasOutletO2', 'aphFlueGasOutletO2', 'ambientAirTemp', 'coalGCV', 'partialCombustionLoss', 'lossDueToRadiation', 'espAshUnburntCarbon']
    for i in required:
        if i not in res:
            return {"error": str(i) + " missing"}, 400
    res['bedAshUnburntCarbon'] = 0.8
    
    temp_diff = _boiler_temp_diff(res['aphFlueGasOutletTemp'], res['ambientAirTemp'])
    theo_air = _boiler_base_required(res)
    excess_air = _boiler_excess_air(res['aphFlueGasOutletO2'])
    actual_air = _boiler_actual_air(theo_air, excess_air)
    
    result = {
        'TheoAirRequired': theo_air,
        'ExcessAir': excess_air,
        'LossDueToH2InFuel': _boiler_loss_h2_in_fuel_v2(res['hydrogen'], temp_diff, res['coalGCV']),
        'LossDueToH2OInFuel': _boiler_loss_h2o_in_fuel(res.get('coalMoist', 0), temp_diff, res['coalGCV']),
        'LossDueToPartialCombustion': res['partialCombustionLoss'],
        'LossDueToRadiation': res['lossDueToRadiation'],
        'LossESPAshUBC': _boiler_loss_ash_ubc(0.65, res['coalAsh'], res['espAshUnburntCarbon'], res['coalGCV']),
        'LossBottomAshUBC': _boiler_loss_ash_ubc(0.35, res['coalAsh'], res['bedAshUnburntCarbon'], res['coalGCV']),
        'LossESPAshSensible': _boiler_loss_sensible_ash(0.65, res['coalAsh'], temp_diff, res['coalGCV'], 0.23),
        'LossBottomAshSensible': _boiler_loss_sensible_ash(0.35, res['coalAsh'], res['bedAshTemp'] - res['ambientAirTemp'], res['coalGCV'], 0.23),
    }
    result['ActualAirSupplied'] = actual_air
    result['LossDueToH2OInAir'] = _boiler_loss_h2o_in_air(res['airHumidityFactor'], actual_air, temp_diff, res['coalGCV'])
    result["massofDryFlueGas"] = actual_air + 1 - ((res.get("coalMoist", 0) + res["coalAsh"] + res["hydrogen"]) / 100)
    result["LossDueToDryFlueGas"] = result['massofDryFlueGas'] * 0.24 * temp_diff * 100 / res['coalGCV']
    result['LossTotalUBC'] = result['LossESPAshUBC'] + result['LossBottomAshUBC']
    result['LossTotalSensible'] = result['LossESPAshSensible'] + result['LossBottomAshSensible']
    result['LossTotal'] = result["LossDueToDryFlueGas"] + result["LossDueToH2OInFuel"] + result["LossDueToH2InFuel"] + result["LossDueToH2OInAir"] + result["LossTotalUBC"] + result["LossTotalSensible"] + result["LossDueToPartialCombustion"] + result["LossDueToRadiation"]
    result['boilerEfficiency'] = 100 - result['LossTotal']
    return result


def boiler_efficiency_type6(res):
    temp_diff = _boiler_temp_diff(res['aphFlueGasOutletTemp'], res['ambientAirTemp'])
    theo_air = _boiler_base_required(res)
    excess_air = _boiler_excess_air(res['aphFlueGasOutletO2'])
    actual_air = _boiler_actual_air(theo_air, excess_air)
    mass_dry_flue_gas = _boiler_mass_dry_flue_gas(res['carbon'], res['coalSulphur'], res.get('nitrogen', 0), actual_air, theo_air)
    
    result = {}
    result["TheoAirRequired"] = theo_air
    result["ExcessAir"] = excess_air
    result["LossDueToH2OInFuel"] = _boiler_loss_h2o_in_fuel(res["coalMoist"], temp_diff, res["coalGCV"])
    result["LossDueToH2InFuel"] = _boiler_loss_h2_in_fuel(res["hydrogen"], temp_diff, res["coalGCV"])
    result["LossBedAshUBC"] = _boiler_loss_ash_ubc(0.10, res["coalAsh"], res["bedAshUnburntCarbon"], res["coalGCV"])
    result["LossFlyAshUBC"] = _boiler_loss_ash_ubc(0.90, res["coalAsh"], res["flyAshUnburntCarbon"], res["coalGCV"])
    result["LossDueToRadiation"] = res["LossDueToRadiation"]
    result["LossUnaccounted"] = res["LossUnaccounted"]
    result["LossFlueGasUBC"] = res["COInFlueGasPPM"] * 28 * 5654 * 100 / ((10 ** 6) * res["coalGCV"])
    result["ActualAirSupplied"] = actual_air
    result["LossDueToH2OInAir"] = _boiler_loss_h2o_in_air(res["airHumidityFactor"], actual_air, temp_diff, res["coalGCV"])
    result["massofDryFlueGas"] = mass_dry_flue_gas
    result["LossDueToNonDeSuph"] = res["LossDueToNonDeSuph"]
    result["LossDueToDryFlueGas"] = _boiler_loss_dry_flue_gas(mass_dry_flue_gas, temp_diff, res["coalGCV"], 0.24)
    result["LossTotal"] = result["LossDueToDryFlueGas"] + result["LossDueToH2OInFuel"] + result["LossDueToH2InFuel"] + result["LossDueToH2OInAir"] + result["LossBedAshUBC"] + result["LossFlyAshUBC"] + result["LossUnaccounted"] + result["LossDueToRadiation"] + result["LossFlueGasUBC"] + result["LossDueToNonDeSuph"]
    result["boilerEfficiency"] = 100 - result["LossTotal"]
    result["LossDueToDryFlueGas"] = _boiler_loss_dry_flue_gas(mass_dry_flue_gas, temp_diff, res["coalGCV"])
    result["LossFlyAshUBC"] = ((res["coalAsh"] / 100) * 0.9 * (res["flyAshUnburntCarbon"]) * 100) / res["coalGCV"]
    result["LossBedAshUBC"] = ((res["coalAsh"] / 100) * 0.1 * (res["bedAshUnburntCarbon"]) * 100) / res["coalGCV"]
    result["LossTotal"] = result["LossDueToDryFlueGas"] + result["LossDueToH2OInFuel"] + result["LossDueToH2InFuel"] + result["LossDueToH2OInAir"] + result["LossBedAshUBC"] + result["LossFlyAshUBC"] + result["LossUnaccounted"] + result["LossDueToRadiation"] + result["LossFlueGasUBC"] + result["LossDueToNonDeSuph"]
    result["boilerEfficiency"] = 100 - result["LossTotal"]
    return result


def boiler_efficiency_type7(res):
    result = boiler_efficiency_type1(res)
    temp_diff = _boiler_temp_diff(res['aphFlueGasOutletTemp'], res['ambientAirTemp'])
    result["LossDueToH2InFuel"] = _boiler_loss_h2_in_fuel_v2(res['hydrogen'], temp_diff, res['coalGCV'])
    result['LossBedAshUBC'] = _boiler_loss_ash_ubc_v2(res["coalAsh"], 0.20, res["bedAshUnburntCarbon"], res['coalGCV'])
    result['LossFlyAshUBC'] = _boiler_loss_ash_ubc_v2(res["coalAsh"], 0.80, res["flyAshUnburntCarbon"], res['coalGCV'])
    result['LossSensibleBedAsh'] = _boiler_loss_sensible_ash(0.20, res["coalAsh"], temp_diff, res['coalGCV'], 0.23)
    result['LossSensibleFlyAsh'] = _boiler_loss_sensible_ash(0.80, res["coalAsh"], temp_diff, res['coalGCV'], 0.23)
    result["LossFlueGasUBC"] = (res['COInFlueGasPPM'] * (10 ** (-4)) * res['carbon'] * 5654) / ((res['COInFlueGasPPM'] * (10 ** (-4)) + 2) * res['coalGCV'])
    if "COInFlueGasPPM" in res and "CO2InFlueGas" in res:
        result['LossDueToCO2'] = ((res['COInFlueGasPPM']/10000)*res['carbon']*5654)/((res['CO2InFlueGas']+(res['COInFlueGasPPM']/10000))*res['coalGCV'])
        result['LossTotal'] = result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] + result['LossSensibleBedAsh'] + result['LossSensibleFlyAsh'] + result['LossUnaccounted'] + result['LossDueToRadiation'] + result['LossDueToCO2']
    else:
        result['LossTotal'] = result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] + result['LossSensibleBedAsh'] + result['LossSensibleFlyAsh'] + result['LossUnaccounted'] + result['LossDueToRadiation'] + result["LossFlueGasUBC"]
    result['boilerEfficiency'] = 100 - result['LossTotal']
    return result


def boiler_efficiency_type8(res):
    result = boiler_efficiency_type1(res)
    temp_diff = _boiler_temp_diff(res['aphFlueGasOutletTemp'], res['ambientAirTemp'])
    result["LossDueToH2InFuel"] = _boiler_loss_h2_in_fuel_v2(res['hydrogen'], temp_diff, res['coalGCV'])
    result["LossFlyAshUBC"] = ((res["flyAshUnburntCarbon"] / (100 - res["flyAshUnburntCarbon"])) * res["coalAsh"] * 0.85 * 8080) / res['coalGCV']
    result["LossFlueGasUBC"] = (res['COInFlueGasPPM'] * (10 ** (-4)) * res['carbon'] * 5654) / ((res['COInFlueGasPPM'] * (10 ** (-4)) + 2) * res['coalGCV'])
    result['LossTotal'] = result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] + result['LossSensibleBedAsh'] + result['LossSensibleFlyAsh'] + result['LossUnaccounted'] + result['LossDueToRadiation'] + result["LossFlueGasUBC"]
    result['boilerEfficiency'] = 100 - result['LossTotal']
    return result


def boiler_efficiency_type9(res):
    result = boiler_efficiency_type1(res)
    result["LossFlyAshUBC"] = ((res["coalAsh"] * (80 * res["flyAshUnburntCarbon"]) / 100) / (100 - ((80 * res["flyAshUnburntCarbon"])/100)) * 8056) / res["coalGCV"]
    result["LossBedAshUBC"] = ((res["coalAsh"] * (20 * res["bedAshUnburntCarbon"]) / 100) / (100 - ((20 * res["bedAshUnburntCarbon"])/100)) * 8056) / res["coalGCV"]
    result['LossTotal'] = result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] + result['LossSensibleBedAsh'] + result['LossSensibleFlyAsh'] + result['LossUnaccounted'] + result['LossDueToRadiation']
    result['boilerEfficiency'] = 100 - result['LossTotal']
    return result


def boiler_efficiency_type10(res):
    result = boiler_efficiency_type1(res)
    temp_diff = _boiler_temp_diff(res['aphFlueGasOutletTemp'], res['ambientAirTemp'])
    result['LossDueToDryFlueGas'] = result['massofDryFlueGas'] * 0.24 * temp_diff * 100 / res['coalGCV']
    result["LossDueToH2InFuel"] = _boiler_loss_h2_in_fuel_v2(res['hydrogen'], temp_diff, res['coalGCV'])
    result["LossBedAshUBC"] = (0.2 * res["bedAshUnburntCarbon"]) / (100 - res["bedAshUnburntCarbon"]) * 8080 * res["coalAsh"] / res['coalGCV']
    result["LossFlyAshUBC"] = ((res["flyAshUnburntCarbon"] / (100 - res["flyAshUnburntCarbon"])) * res["coalAsh"] * 0.8 * 8080) / res['coalGCV']
    result["LossSensibleBedAsh"] = (res["coalAsh"] * (20/10000))*0.23*(res['bedAshTemp'] - res['ambientAirTemp'])*100 / res['coalGCV']
    result["LossSensibleFlyAsh"] = (res["coalAsh"] * (80/10000)) * 0.23 * temp_diff * 100 / res['coalGCV']
    result['LossTotal'] = result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] + result['LossSensibleBedAsh'] + result['LossSensibleFlyAsh'] + result['LossUnaccounted'] + result['LossDueToRadiation']
    result['boilerEfficiency'] = 100 - result['LossTotal']
    return result


def boiler_efficiency_type11(res):
    temp_diff = _boiler_temp_diff(res['aphFlueGasOutletTemp'], res['ambientAirTemp'])
    theo_air = _boiler_base_required(res)
    excess_air = _boiler_excess_air(res["aphFlueGasOutletO2"])
    actual_air = _boiler_actual_air(theo_air, excess_air)
    mass_dry_flue_gas = _boiler_mass_dry_flue_gas(res['carbon'], res['coalSulphur'], res.get('nitrogen', 0), actual_air, theo_air)
    
    result = {}
    result["TheoAirRequired"] = theo_air
    result["ExcessAir"] = excess_air
    result["ActualAirSupplied"] = actual_air
    result["LossDueToH2OInFuel"] = _boiler_loss_h2o_in_fuel(res["coalMoist"], temp_diff, res["coalGCV"])
    result["LossDueToH2InFuel"] = _boiler_loss_h2_in_fuel(res["hydrogen"], temp_diff, res["coalGCV"])
    result["LossBedAshUBC"] = _boiler_loss_ash_ubc_v2(res["coalAsh"], 0.15, res["bedAshUnburntCarbon"], res["coalGCV"])
    result["LossFlyAshUBC"] = _boiler_loss_ash_ubc_v2(res["coalAsh"], 0.85, res["flyAshUnburntCarbon"], res["coalGCV"])
    result["LossSensibleBedAsh"] = _boiler_loss_sensible_ash(0.15, res["coalAsh"], res["bedAshTemp"] - res["ambientAirTemp"], res["coalGCV"])
    result["LossSensibleFlyAsh"] = _boiler_loss_sensible_ash(0.85, res["coalAsh"], temp_diff, res["coalGCV"])
    result["LossDueToRadiation"] = res["LossDueToRadiation"]
    result["LossUnaccounted"] = res["LossUnaccounted"]
    result["LossDueToCO2"] = ((res["COInFlueGasPPM"] / 10000) * res["carbon"] * 5654) / ((res["Co2"] + (res["COInFlueGasPPM"] / 10000)) * res["coalGCV"])
    result["massofDryFlueGas"] = mass_dry_flue_gas
    result["LossDueToDryFlueGas"] = _boiler_loss_dry_flue_gas(mass_dry_flue_gas, temp_diff, res["coalGCV"])
    result["LossDueToH2OInAir"] = _boiler_loss_h2o_in_air(res["airHumidityFactor"], actual_air, temp_diff, res["coalGCV"])
    result["LossTotal"] = result["LossDueToDryFlueGas"] + result["LossDueToH2OInFuel"] + result["LossDueToH2InFuel"] + result["LossDueToH2OInAir"] + result["LossBedAshUBC"] + result["LossFlyAshUBC"] + result["LossSensibleBedAsh"] + result["LossSensibleFlyAsh"] + result["LossUnaccounted"] + result["LossDueToRadiation"] + result["LossDueToCO2"]
    result["boilerEfficiency"] = 100 - result["LossTotal"]
    return result


def boiler_efficiency_type12(res):
    result = {}
    result["ambientAirTemp"] = ((res["paFlow"] * res["paOLTemp"]) + (res["fdFlow"] * res["fdOLTemp"])) / (res["paFlow"] + res["fdFlow"])
    temp_diff = _boiler_temp_diff(res['aphFlueGasOutletTemp'], result["ambientAirTemp"])
    
    result["LossESPAshUBC"] = _boiler_loss_ash_ubc(0.65, res["coalAsh"], res["flyAshUnburntCarbon"], res["coalGCV"])
    result["LossBottomAshUBC"] = _boiler_loss_ash_ubc(0.05, res["coalAsh"], res["bedAshUnburntCarbon"], res["coalGCV"])
    result["LossESPAshSensible"] = _boiler_loss_sensible_ash(0.65, res["coalAsh"], temp_diff, res["coalGCV"], 0.23)
    result["LossBottomAshSensible"] = res["coalAsh"] * 5 / 10000 * 0.23 * (res["bedAshUnburntCarbon"] - result["ambientAirTemp"]) * 100 / res["coalGCV"]
    result["LossDueToH2InFuel"] = _boiler_loss_h2_in_fuel(res["hydrogen"], temp_diff, res["coalGCV"])
    result["LossDueToH2OInFuel"] = _boiler_loss_h2o_in_fuel(res["coalMoist"], temp_diff, res["coalGCV"])
    result["LossDueToRadiation"] = res["LossDueToRadiation"]
    result["LossDueToPartialCombustion"] = res["partialCombustionLoss"]
    result["Other_Losses_Plant_Specific_prc"] = res["Other_Losses_Plant_Specific_prc"]
    result["TheoAirRequired"] = _boiler_base_required(res)
    result["ExcessAir"] = _boiler_excess_air(res["aphFlueGasOutletO2"])
    result["ActualAirSupplied"] = _boiler_actual_air(result["TheoAirRequired"], result["ExcessAir"])
    result["massofDryFlueGas"] = _boiler_mass_dry_flue_gas(res["carbon"], res["coalSulphur"], res.get("nitrogen", 0), result["ActualAirSupplied"], result["TheoAirRequired"])
    result["LossDueToH2OInAir"] = _boiler_loss_h2o_in_air(res["airHumidityFactor"], result["ActualAirSupplied"], temp_diff, res["coalGCV"])
    result["LossDueToDryFlueGas"] = _boiler_loss_dry_flue_gas(result["massofDryFlueGas"], temp_diff, res["coalGCV"], 0.24)
    result["LossTotalUBC"] = result["LossESPAshUBC"] + result["LossBottomAshUBC"]
    result["LossTotalSensible"] = result["LossESPAshSensible"] + result["LossBottomAshSensible"]
    result["LossTotal"] = result["LossTotalUBC"] + result["LossTotalSensible"] + result["LossDueToDryFlueGas"] + result["LossDueToH2OInFuel"] + result["LossDueToH2InFuel"] + result["LossDueToH2OInAir"] + result["LossDueToPartialCombustion"] + result["Other_Losses_Plant_Specific_prc"]
    result["boilerEfficiency"] = 100 - result["LossTotal"]
    return result


def boiler_efficiency_type13(res):
    result = {}
    result["barometricPressurePSI"] = (res["barometricPressInMbar"] * 14.5038 / 1000.0)
    result["dryBulbTempAtFDInlet"] = (res["saInletTempAtAph"] - 3.0)
    result["dryBulbTempAtFDInletInFarenheit"] = ((result["dryBulbTempAtFDInlet"] * 1.8) + 32.0)
    result["saturationPressureOfWaterVaporAtDbtInPSI"] = (0.019257 + (1.289016 * (10**(-3)) * result["dryBulbTempAtFDInletInFarenheit"]) + (1.21122*(10**(-5))*(result["dryBulbTempAtFDInletInFarenheit"]**2)) + (4.534007*(10**(-7))*(result["dryBulbTempAtFDInletInFarenheit"]**3)) + (6.84188*(10**(-11))*(result["dryBulbTempAtFDInletInFarenheit"]**4)) + (2.197092*(10**(-11))*(result["dryBulbTempAtFDInletInFarenheit"]**5)))
    result["saturationPressureOfWaterVaporAtDbtInBar"] = result["saturationPressureOfWaterVaporAtDbtInPSI"] / 14.5038
    result["partialPressureOfWaterVaporInAirPsi"] = result["saturationPressureOfWaterVaporAtDbtInPSI"] * 0.01 * res["relativeHumidity"]
    result["partialPressureOfWaterVaporInAirMbar"] = result["partialPressureOfWaterVaporInAirPsi"] / 14.5038
    result["moistureInAirPerKgOfDryAir"] = 0.622 * (result["partialPressureOfWaterVaporInAirPsi"] / (result["barometricPressurePSI"] - result["partialPressureOfWaterVaporInAirPsi"]))
    result["airHumidityFactor"] = round(result["moistureInAirPerKgOfDryAir"],3)
    result["TheoAirRequired"] = (11.6*res["carbon"]/100)+34.8*(res["hydrogen"]-res["oxygen"]/8)/100+(4.35*res["coalSulphur"]/100)
    result["averageO2_dryBasis"] = res["aphFlueGasOutletO2"] + 0.5
    result["averageO2AtAphOutlet"] = ((20.9 * res["LeakageacrossAPH"]) + (90.0 * result["averageO2_dryBasis"])) / (90.0 + res["LeakageacrossAPH"])
    result["ExcessAir"] = (result["averageO2AtAphOutlet"] * 100) / (21 - result["averageO2AtAphOutlet"])
    result["ActualAirSupplied"] = (1 + result["ExcessAir"] / 100) * result["TheoAirRequired"]
    result["massofDryFlueGas"] = (res["carbon"] * 44 / 12 + res["coalSulphur"] * 64 / 32 + res.get("nitrogen", 0) + result["ActualAirSupplied"] * 77 + (result["ActualAirSupplied"] - result["TheoAirRequired"]) * 23) / 100
    result["weightedAirInletTempToAph"] = ((res["paFlow"] * res["paInletTempAtAph"]) + (res["fdFlow"] * res["saInletTempAtAph"])) / (res["paFlow"] + res["fdFlow"])
    temp_diff = res['aphFlueGasOutletTemp'] - result["weightedAirInletTempToAph"]
    result["LossDueToDryFlueGas"] = result["massofDryFlueGas"] * 0.24 * temp_diff * 100 / res["coalGCV"]
    result["LossDueToH2OInFuel"] = res["coalMoist"] * (584 + (0.45 * temp_diff)) / res["coalGCV"]
    result["LossDueToH2InFuel"] = 8.937 * (584 + 0.45 * temp_diff) * res["hydrogen"] / res["coalGCV"]
    result["LossDueToH2OInAir"] = result["airHumidityFactor"] * result["ActualAirSupplied"] * 0.45*temp_diff * 100 / res["coalGCV"]
    result["co2AtAphOutlet"] = 19.4 - res["aphFlueGasOutletO2"]
    result["coAtAphOutletMeasuredPpm"] = res["coDilutionAcrossEspTest"] + res["CO_Online_ESP_O_L"]
    result["coAtAphOutletInPercentage"] = result["coAtAphOutletMeasuredPpm"] * 100 / 10**6
    result["LossDueToPartialCombustion"] = round((result["coAtAphOutletInPercentage"] * res["carbon"] / 100.0) / (result["coAtAphOutletInPercentage"] + result["co2AtAphOutlet"]) * 5744 * 100 / res["coalGCV"], 3)
    result["LossESPAshUBC"] = (res["flyAshRatioInPercent"] / 100) * res["coalAsh"] * res["flyAshUnburntCarbon"] * 8077 / (100 * res["coalGCV"])
    result["LossBottomAshUBC"] = (res["bottomAshRatioInPercent"] / 100) * res["coalAsh"] * res["bedAshUnburntCarbon"] * 8077 / (100 * res["coalGCV"])
    result["LossESPAshSensible"] = 0.01 * res["flyAshRatioInPercent"] * res["coalAsh"] * 0.01 * (0.16 * (1.8 * res["aphFlueGasOutletTemp"] + 32)+ 1.09 * (10**(-4)) * ((1.8 * res["aphFlueGasOutletTemp"] +32)**2)  - 2.843 * (10**(-8)) * ((1.8 * res["aphFlueGasOutletTemp"] + 32)**3) - 12.95) * 2.326 / 4.1868 * 100 / res["coalGCV"]
    result["LossBottomAshSensible"] = 0.01 * res["bottomAshRatioInPercent"] * res["coalAsh"] * 0.01 * (0.16 * (1.8 * res["bottomAshTempConstant"]+ 32) + 1.09 * (10**(-4)) * ((1.8 * res["bottomAshTempConstant"] +32)**2) - 2.843 * (10**(-8)) * ((1.8 * res["bottomAshTempConstant"] + 32)**3) - 12.95) * 2.326 / 4.1868 * 100 / res["coalGCV"] + 31500 * 3.6 * 17.54 / (1000 * res["coalFlow"]) / res["coalGCV"] / 4.1868 * 100
    result["LossTotalUBC"] = result["LossESPAshUBC"] + result["LossBottomAshUBC"]
    result["LossTotalSensible"] = result["LossESPAshSensible"] + result["LossBottomAshSensible"]
    result["LossDueToRadiation"] = res["LossDueToRadiation"]
    result["LossTotal"] = result["LossDueToDryFlueGas"] + result["LossDueToH2OInFuel"] + result["LossDueToH2InFuel"] + result["LossDueToH2OInAir"] + result["LossDueToPartialCombustion"] + result["LossTotalUBC"] + result["LossTotalSensible"] + result["LossDueToRadiation"]
    result["boilerEfficiencyAsPerAsmePtc4"] = 100.0 - result["LossTotal"]
    result["LossMillRejects"] = (res["millRejectsCV"] * res["millRejectsQuantity"] * 100.0) / (res["load"] * 0.7 * 1000.0 * res["coalGCV"])
    result["LossBlowDownLeakage"] = (0.8 * res["dmMakeUpWater"] * 300 + 0.2 * res["dmMakeUpWater"] * 150) * 100 / (res["load"] * 0.7 * res["coalGCV"])
    result["LossPlantSpecificOther"] = res["plantSpecificOtherLosses"]
    result["boilerEfficiency"] = result["boilerEfficiencyAsPerAsmePtc4"] - result["LossMillRejects"] - result["LossBlowDownLeakage"] - result["LossPlantSpecificOther"]
    return result


def boiler_efficiency_type14(res):
    result = {}
    temp_diff = res['aphFlueGasOutletTemp'] - res['ambientAirTemp']
    result["saturationVaporPressure"] = 0.61078 * math.exp(((17.27 * res["ambientAirTemp"]) / (res["ambientAirTemp"] + 237.3)))
    result["vaporPressure"] = res["ambientRelativeHumidityPRC"] * result["saturationVaporPressure"]
    result["specificHumidity"] = 0.622 * result["vaporPressure"] / ((res["ambientAirPressurePascal"]*100) - 0.378 * result["vaporPressure"])
    result["moistureContentInAir"] = result["specificHumidity"] / (1.0 - result["specificHumidity"])
    result["aphLeakagePassA"] = 100.0 * (res["aphFlueGasOutletO2_A"] - res["aphFlueGasInletO2_A"]) / (21.0 - res["aphFlueGasOutletO2_A"])
    result["aphLeakagePassB"] = 100.0 * (res["aphFlueGasOutletO2_B"] - res["aphFlueGasInletO2_A"]) / (21.0 - res["aphFlueGasOutletO2_B"])
    result["flueGasTempForNOAphLeakage"] = (((result["aphLeakagePassA"] + result["aphLeakagePassB"]) / 2) * 0.01 * (res["aphFlueGasOutletTemp"] - res["aphFlueGasInletTemp"])) + res["aphFlueGasOutletTemp"]
    result["weightedAphInletTemp"] = res["ambientAirTemp"]
    result["avgO2AtAphOutlet"] = res["aphFlueGasOutletO2_A"]
    result["excessAirSupplied"] = result["avgO2AtAphOutlet"] / (21 - result["avgO2AtAphOutlet"]) * 100.0
    result["theoriticalAirRequired"] = ((11.6*res["carbon"]) + (34.8 * (res["hydrogen"]) - (res["oxygen"] / 8.0)) + (4.35 * res["coalSulphur"])) / 100.0
    result["actualMassOfAirSupplied"] = result["theoriticalAirRequired"] * (1 + (result["excessAirSupplied"] / 100.0))
    result["massOfDryFlueGas"] = (((res["carbon"] / 100.0) * 44.0) / 12.0) + (res.get("nitrogen", 0) / 100.0) + (result["actualMassOfAirSupplied"] * 77.0 / 100.0) + (((result["actualMassOfAirSupplied"] - result["theoriticalAirRequired"]) * 23.0) / 100.0)
    result["totalUnburntCarbonInAsh"] = (res["coalAsh"] * res["bedAshUnburntCarbon"] * 10 * 0.01 * 0.01 * 0.01) + (res["coalAsh"] * res["flyAshUnburntCarbon"] * 90 * 0.01 * 0.01 * 0.01)
    result["carbonInAsh"] = (res["flyAshUnburntCarbon"] * 90 * 0.01) + (res["bedAshUnburntCarbon"] * 10 * 0.01)
    result["carbonInAshPerKgOfFuel"] = ((res["coalAsh"] / 100.0) * result["carbonInAsh"]) / (100.0 - result["carbonInAsh"])
    result["empiricalCO2"] = 18.68 - result["avgO2AtAphOutlet"]
    result["weightOfDryFlueGas"] = (res["carbon"] + (res["coalSulphur"] / 2.67) - 100 * result["carbonInAshPerKgOfFuel"]) / (12 * result["empiricalCO2"])
    result["sensibleHeatOfDryGas"] = result["weightOfDryFlueGas"] * 30.6 * temp_diff
    result["LossDueToDryFlueGas"] = (result["sensibleHeatOfDryGas"] * 100.0) / (res["coalGCV"] * 4.18674)
    result["sensibleHeatOfWater"] = 1.88 * (res["aphFlueGasOutletTemp"] - 25.0) + 2442 + (4.2 * (25 - result["weightedAphInletTemp"]))
    result["LossDueToH2InFuel"] = (result["sensibleHeatOfWater"] * res["hydrogen"] * 9.0) / (res["coalGCV"] * 4.18674)
    result["LossDueToH2OInFuel"] = (result["sensibleHeatOfWater"] * res["coalMoist"]) / (res["coalGCV"] * 4.18674)
    result["LossDueToH2OInAir"] = (result["actualMassOfAirSupplied"] * result["moistureContentInAir"] * (0.45 * temp_diff * 100.0)) / res["coalGCV"]
    result["LossDueToPartialCombustion"] = 0.0
    result["LossDueToUnburntCarbon"] = result["totalUnburntCarbonInAsh"] * 8084.0 * 100.0 / res["coalGCV"]
    result["LossDueToRadiation"] = 0.99
    result["LossTotal"] = result["LossDueToDryFlueGas"] + result["LossDueToH2InFuel"] + result["LossDueToH2OInFuel"] + result["LossDueToH2OInAir"] + result["LossDueToPartialCombustion"] + result["LossDueToUnburntCarbon"] + result["LossDueToRadiation"]
    result["boilerEfficiency"] = 100.0 - result["LossTotal"]
    return result


def boiler_efficiency_type15(res):
    required = ["carbon", "hydrogen", "coalSulphur", "oxygen", "aphFlueGasOutletO2", "coalMoist", "aphFlueGasOutletTemp", "ambientAirTemp", "coalGCV","coalAsh","airHumidityFactor", "LossUnaccounted", "LossDueToRadiation", "flyAshUnburntCarbon", "bedAshUnburntCarbon"]
    for i in required:
        if i not in res:
            return {"error": str(i) + " missing"}, 400
    
    temp_diff = _boiler_temp_diff(res['aphFlueGasOutletTemp'], res['ambientAirTemp'])
    theo_air = _boiler_base_required(res)
    excess_air = _boiler_excess_air(res['aphFlueGasOutletO2'])
    actual_air = _boiler_actual_air(theo_air, excess_air)
    
    result = {
        'TheoAirRequired': theo_air,
        'ExcessAir': excess_air,
        'LossDueToH2OInFuel': _boiler_loss_h2o_in_fuel(res['coalMoist'], temp_diff, res['coalGCV']),
        'LossDueToH2InFuel': _boiler_loss_h2_in_fuel_v2(res['hydrogen'], temp_diff, res['coalGCV']),
        'LossBedAshUBC': _boiler_loss_ash_ubc(0.20, res['coalAsh'], res['bedAshUnburntCarbon'], res['coalGCV']),
        'LossFlyAshUBC': _boiler_loss_ash_ubc(0.80, res['coalAsh'], res['flyAshUnburntCarbon'], res['coalGCV']),
        'LossDueToRadiation': res['LossDueToRadiation'],
        'LossUnaccounted': res['LossUnaccounted'],
    }
    result['LossFlueGasUBC'] = res['COInFlueGasPPM'] * 28 * 5654 * 100 / ((10 ** 6) * res['coalGCV'])
    result['ActualAirSupplied'] = actual_air
    result['LossDueToH2OInAir'] = _boiler_loss_h2o_in_air(res['airHumidityFactor'], actual_air, temp_diff, res['coalGCV'])
    result['massofDryFlueGas'] = (res['carbon'] * 44 / 12 + res['coalSulphur'] * 32 / 64 + res['ActualAirSupplied'] * 77/100 + (res['oxygen']* 32) / 100)
    result['LossDueToDryFlueGas'] = result['massofDryFlueGas'] * 0.24 * temp_diff * 100 / res['coalGCV']
    result['LossTotal'] = result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] + result['LossUnaccounted'] + result['LossDueToRadiation'] + result['LossFlueGasUBC']
    result['boilerEfficiency'] = 100 - result['LossTotal']
    return result


def boiler_efficiency_type16(res):
    required = ["carbon", "hydrogen", "coalSulphur", "oxygen", "aphFlueGasOutletO2", "coalMoist", "aphFlueGasOutletTemp", "ambientAirTemp", "coalGCV", "coalAsh", "airHumidityFactor", "COInFlueGasPPM", "LossUnaccounted", "LossDueToRadiation", "flyAshUnburntCarbon", "bedAshUnburntCarbon"]
    for i in required:
        if i not in res:
            return {"error": f"{i} missing"}, 400
    
    result = {}
    Fcdc = res['coalFC'] / (1 - ((1.1 * res['coalAsh']) / 100 - res['coalMoist'] / 100))
    Vmdf = 100 - Fcdc
    Cdf = Fcdc + (0.9 * Vmdf) - 14
    Hdf = Vmdf * (7.35 / (Vmdf + 10) - 0.013)
    Ndf = 2.1 - (0.012 * Vmdf)
    result['carbon'] = (Cdf * (res['coalVM'] + res['coalFC'])) / (Vmdf + Fcdc)
    result['hydrogen'] = (Hdf * (res['coalVM'] + res['coalFC'])) / (Vmdf + Fcdc)
    result['nitrogen'] = (Ndf * (res['coalVM'] + res['coalFC'])) / (Vmdf + Fcdc)
    result['coalSulphur'] = 0.009 * (res['coalFC'] + res['coalVM'])
    result["oxygen"] = (100 - result['carbon'] - result['hydrogen'] - result['coalSulphur'] - result['nitrogen'] - res['coalAsh'] - res['coalMoist'])
    temp_diff = _boiler_temp_diff(res['aphFlueGasOutletTemp'], res['ambientAirTemp'])
    result['TheoAirRequired'] = (0.1143 * result['carbon'] + 0.345 * result['hydrogen'] - 0.043125 * result['oxygen'] + 0.0432 * result['coalSulphur'])
    result['ExcessAir'] = _boiler_excess_air(res['aphFlueGasOutletO2'])
    result['ActualAirSupplied'] = _boiler_actual_air(result['TheoAirRequired'], result['ExcessAir'])
    result['massOfDryFlueGas'] = (((result['carbon'] / 100.0) * 44.0 / 12.0) + (result['nitrogen'] / 100.0) + (result['ActualAirSupplied'] * 77.0 / 100.0) + ((result['ActualAirSupplied'] - result['TheoAirRequired']) * 23.0 / 100.0))
    result['LossDueToDryFlueGas'] = (result['massOfDryFlueGas'] * 0.23 * temp_diff / res['coalGCV']) * 100
    result['LossDueToH2InFuel'] = (9 * result['hydrogen'] * (584 + 0.23 * temp_diff) / res['coalGCV'])
    result['LossDueToH2OInFuel'] = (res['coalMoist'] * (584 + 0.23 * temp_diff) / res['coalGCV'])
    result['LossDueToH2OInAir'] = (res['airHumidityFactor'] * result['ActualAirSupplied'] * 0.23 * temp_diff * 100 / res['coalGCV'])
    result["LossDueToRadiation"] = res["LossDueToRadiation"]
    result["LossUnaccounted"] = res["LossUnaccounted"]
    result["LossESPAshUBC"] = _boiler_loss_ash_ubc(0.65, res["coalAsh"], res["flyAshUnburntCarbon"], res["coalGCV"])
    result["LossBottomAshUBC"] = _boiler_loss_ash_ubc(0.05, res["coalAsh"], res["bedAshUnburntCarbon"], res["coalGCV"])
    result['LossTotal'] = (result['LossDueToDryFlueGas'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInFuel'] + result['LossDueToH2OInAir'] + result['LossBottomAshUBC'] + result['LossESPAshUBC'] + result['LossUnaccounted'] + result['LossDueToRadiation'])
    result['boilerEfficiency'] = 100 - result['LossTotal']
    return result


def boiler_efficiency_type17(res):
    result = {}
    result["flyAshRatioInPercent"] = (res["flyAshUnburntCarbon"])/(res["bedAshUnburntCarbon"]+res["flyAshUnburntCarbon"])*100
    result["bottomAshRatioInPercent"] = (res["bedAshUnburntCarbon"])/(res["bedAshUnburntCarbon"]+res["flyAshUnburntCarbon"])*100
    result["TheoAirRequired"] = (11.6*res["carbon"]/100)+34.8*(res["hydrogen"]-res["oxygen"]/8)/100+(4.35*res["coalSulphur"]/100)
    result["ExcessAir"] = (res["averageO2AtAphOutlet"] * 100) / (21 - res["averageO2AtAphOutlet"])
    result["ActualAirSupplied"] = (1 + result["ExcessAir"] / 100) * result["TheoAirRequired"]
    result["massofDryFlueGas"] = (res["carbon"] * 44 / 12 + res["coalSulphur"] * 64 / 32 + res.get("nitrogen", 0)/100 + result["ActualAirSupplied"] * 77 + (result["ActualAirSupplied"] - result["TheoAirRequired"]) * 23) / 100
    temp_diff = _boiler_temp_diff(res["aphFlueGasOutletTemp"], res["ambientAirTemp"])
    result["LossDueToDryFlueGas"] = result["massofDryFlueGas"] * 0.24 * temp_diff * 100 / res["coalGCV"]
    result["LossDueToH2InFuel"] = 9 * (584 + 0.45 * temp_diff) * res["hydrogen"] / res["coalGCV"]
    result["LossDueToH2OInFuel"] = res["coalMoist"] * (584 + (0.45 * temp_diff)) / res["coalGCV"]
    result["lossDueToCO2"] = ((0*(res["carbon"]/100))/(0+0.07162))*(5744/res["coalGCV"])*100
    result["LossESPAshUBC"] = (result["flyAshRatioInPercent"] / 100) * res["coalAsh"] * res["flyAshUnburntCarbon"] * 8056 / (100 * res["coalGCV"])
    result["LossBottomAshUBC"] = (result["bottomAshRatioInPercent"] / 100) * res["coalAsh"] * res["bedAshUnburntCarbon"] * 8056 / (100 * res["coalGCV"])
    result["LossESPAshSensible"] = (0.16*res["coalAsh"]*result["flyAshRatioInPercent"]*temp_diff)*100/100/100/res["coalGCV"]
    result["LossBottomAshSensible"] = (0.16*res["coalAsh"]*result["bottomAshRatioInPercent"]*(1100-res['ambientAirTemp']))*100/100/100/res["coalGCV"]
    result["LossTotalUBC"] = result["LossESPAshUBC"] + result["LossBottomAshUBC"]
    result["LossTotalSensible"] = result["LossESPAshSensible"] + result["LossBottomAshSensible"]
    result["LossDueToRadiation"] = res["LossDueToRadiation"]
    result["LossDueToH2OInAir"] = (result["ActualAirSupplied"] * res["airHumidityFactor"] * 0.45 * temp_diff * 100 / (res["coalGCV"]))
    result["LossTotal"] = result["lossDueToCO2"] + result["LossDueToDryFlueGas"] + result["LossDueToH2OInFuel"] + result["LossDueToH2InFuel"] + result["LossDueToH2OInAir"] + result["LossTotalUBC"] + result["LossTotalSensible"] + res["LossDueToRadiation"]
    result["boilerEfficiency"] = 100 - result["LossTotal"]
    return result


def boiler_efficiency_type18(res):
    result = boiler_efficiency_type1(res)
    res["LossFlyAshUBC"] = (45/100)*(res["coalAsh"]/(100-res["flyAshUnburntCarbon"]))*(8052*(res["flyAshUnburntCarbon"]/100))/(res["coalGCV"])*100
    res["LossBedAshUBC"] = (55/100)*(res["coalAsh"]/(100-res["bedAshUnburntCarbon"]))*(8052*(res["bedAshUnburntCarbon"]/100))/(res["coalGCV"])*100
    result['LossTotal'] = result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] + result['LossSensibleBedAsh'] + result['LossSensibleFlyAsh'] + result['LossUnaccounted'] + result['LossDueToRadiation']
    result['boilerEfficiency'] = 100 - result['LossTotal']
    return result