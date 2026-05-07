import os
import time
import logging
import json
import requests
from datetime import datetime
from typing import Dict
from apscheduler.schedulers.background import BackgroundScheduler
from config.settings import getconfig
from data.collectors import DataCollector
from mqtt.client import MQTTPublisher
from processors.turbine import TurbineProcessor, BoilerProcessor
from config.logging_utils import (
    logger, log_section, log_variable, log_info, log_warning, log_error,
    setup_logging, runner_logger as rl
)

log_section("OPTIMIZED FILTER - INITIALIZING")


def get_run_mode():
    if os.environ.get('CRON_MODE', '').lower() == 'true':
        return 'cron'
    return 'server'


def main():
    rl.info("="*60)
    rl.info("▶ MAIN FUNCTION START")
    rl.info("="*60)
    
    config = getconfig()
    rl.info("Configuration loaded")
    log_variable("config_keys", list(config.keys()) if config else "empty")
    
    unit_id = os.environ.get('UNIT_ID', '')
    log_variable("UNIT_ID", unit_id)
    
    if not unit_id:
        log_error(Exception("UNIT_ID not set"), "runner.main")
        return
    
    unit_config = getconfig(unit_id)
    broker_config = {
        'address': unit_config.get('BROKER_ADDRESS', ''),
        'port': int(unit_config.get('Q_PORT', 1883)),
        'username': unit_config.get('BROKER_USERNAME', ''),
        'password': unit_config.get('BROKER_PASSWORD', '')
    }
    log_variable("BROKER_ADDRESS", broker_config['address'])
    log_variable("BROKER_PORT", broker_config['port'])
    
    api_config = unit_config.get('api', {})
    log_variable("api_config_keys", list(api_config.keys()))
    log_variable("EFFICIENCY_URL", api_config.get('efficiency', ''))
    
    rl.info("Creating DataCollector...")
    collector = DataCollector(
        config={'api_meta': api_config.get('meta', ''), 
                'api_query': api_config.get('query', ''),
                'efficiency_url': api_config.get('efficiency', ''),
                'kairos': api_config.get('kairos', '')},
        unit_id=unit_id
    )
    rl.info("DataCollector created")
    
    kairos_url = api_config.get('kairos', '')
    
    rl.info("Creating MQTTPublisher...")
    publisher = MQTTPublisher(
        broker_address=broker_config['address'],
        port=broker_config['port'],
        username=broker_config['username'],
        password=broker_config['password'],
        client_id=f"filter_{unit_id}",
        kairos_url=kairos_url,
        unit_id=unit_id
    )
    rl.info("MQTTPublisher created")
    
    try:
        publisher.connect()
        rl.info("✓ MQTT connected successfully")
    except Exception as e:
        log_warning(f"MQTT connection failed: {e}. Continuing without MQTT.")
        publisher = None
    
    rl.info("Fetching mapping from API...")
    mapping = collector.fetch_mapping()
    log_variable("mapping_records_count", len(mapping))
    log_variable("mapping[0]_keys", list(mapping[0].keys()) if mapping else [])
    
    if mapping and len(mapping) > 0:
        mapping_content = str(mapping[0])
        log_variable("mapping_content_preview", mapping_content[:300] + "..." if len(mapping_content) > 300 else mapping_content)

    save_csv = os.environ.get('SAVE_CSV', 'false').lower() == 'true'

    if save_csv and mapping:
        csv_filename = f"{unit_id}_input.csv"
        import pandas as pd
        pd.DataFrame(mapping).to_csv(csv_filename, index=False)
        rl.info(f"Saved mapping to CSV: {csv_filename}")
    
    if not mapping:
        log_warning(f"No mapping found for unit {unit_id}")
        return
    
    post_time = int((int(datetime.now().timestamp() / 60) * 60) * 1000)
    log_variable("post_time", post_time)
    
    if mapping and len(mapping) > 0:
        mapping_data = mapping[0].get("output", {})
        if not mapping_data:
            mapping_data = mapping[0].get("input", {})
        log_variable("mapping_data_keys", list(mapping_data.keys()))
        
        if "turbineHeatRate" in mapping_data:
            log_section("PROCESSING TURBINE HEAT RATE")
            turbine_proc = TurbineProcessor(collector, publisher, mapping_data, unit_id)
            turbine_proc.process(unit_id, post_time)
            rl.info("Turbine heat rate processing complete")
        
        if "boilerEfficiency" in mapping_data:
            log_section("PROCESSING BOILER EFFICIENCY")
            boiler_proc = BoilerProcessor(collector, publisher, mapping_data, unit_id)
            boiler_proc.process(unit_id, post_time)
            rl.info("Boiler efficiency processing complete")

        if "plantHeatRate" in mapping_data:
            log_section("PROCESSING PLANT HEAT RATE (PHR)")
            phr_result = process_plant_heat_rate(collector, mapping_data, api_config, unit_id, post_time)
            if phr_result:
                rl.info(f"Plant heat rate processing complete: {phr_result}")
            else:
                rl.warning("Plant heat rate processing returned no data")

        if unit_id == "6375e28c32ebf700068ac0aa":
            log_section("PROCESSING JSW SPECIFIC THR DEV")
            jsw_result = process_jsw_specific_thr_dev(collector, publisher, mapping_data, api_config, unit_id, post_time)
            if jsw_result:
                rl.info(f"JSW specific THR dev processing complete")
            else:
                rl.warning("JSW specific THR dev processing returned no data")
    
    if publisher:
        publisher.close()
        rl.info("MQTT connection closed")
    
    rl.info(f"✓ Completed processing for unit {unit_id}")
    rl.info("="*60)
    rl.info("▶ MAIN FUNCTION END")
    rl.info("="*60)


if __name__ == '__main__':
    run_mode = get_run_mode()
    log_section(f"STARTING IN {run_mode.upper()} MODE")
    log_variable("run_mode", run_mode)
    
    frequency = int(os.environ.get('FREQUENCY', '300'))
    log_variable("frequency_seconds", frequency)
    
    if run_mode == 'cron':
        main()
    else:
        scheduler = BackgroundScheduler()
        scheduler.add_job(main, 'interval', seconds=frequency, misfire_grace_time=None)
        scheduler.start()
        log_info(f"Scheduler started with {frequency}s interval")
        
        while True:
            time.sleep(60)


def turbineSide(unit_id: str, mapping_data: dict) -> Dict:
    result = {"unitId": unit_id}
    turbine_tags = []
    
    for turbine in mapping_data.get("turbineHeatRate", []):
        for tag_value in turbine.get("realtime", {}).values():
            if isinstance(tag_value, list):
                turbine_tags.extend(tag_value)
    
    collector = DataCollector(
        config={'api_meta': os.environ.get('API_META', '')},
        unit_id=unit_id
    )
    
    if turbine_tags:
        data = collector.get_last_values(turbine_tags)
        if not data.empty:
            result["turbineData"] = data.to_dict(orient="records")[0]
            result["status"] = "success"
        else:
            result["status"] = "no_data"
    else:
        result["status"] = "no_tags"
    
    return result


def should_run_as_cron(unit_id: str) -> bool:
    cron_units = os.environ.get("CRON_UNITS", "")
    if not cron_units:
        return False
    return unit_id in cron_units.split(",")


def process_plant_heat_rate(collector: DataCollector, mapping_data: dict, api_config: dict, unit_id: str, post_time: int) -> dict:
    """
    Process Plant Heat Rate (PHR) - corresponds to index-b.py lines 1370-1423
    """
    import requests
    import json

    result = {"status": "skipped"}

    if "plantHeatRate" not in mapping_data:
        rl.warning("No plantHeatRate in mapping_data")
        return result

    phr_mapping = mapping_data.get("plantHeatRate", {})
    eff_url = api_config.get('efficiency', '')

    if not eff_url:
        rl.warning("No efficiency URL configured")
        return result

    try:
        phr_realtime = requests.post(eff_url + "phr", json=phr_mapping.get("realtime", {}))
        phr_design = requests.post(eff_url + "phr", json=phr_mapping.get("design", {}))
        phr_bperf = requests.post(eff_url + "phr", json=phr_mapping.get("bestAchieved", {}))

        result = {
            "status": "success",
            "realtime": phr_realtime.json() if phr_realtime.status_code == 200 else {},
            "design": phr_design.json() if phr_design.status_code == 200 else {},
            "bperf": phr_bperf.json() if phr_bperf.status_code == 200 else {}
        }

        rl.info(f"PHR realtime: {result.get('realtime', {})}")
        rl.info(f"PHR design: {result.get('design', {})}")
        rl.info(f"PHR bperf: {result.get('bperf', {})}")

    except Exception as e:
        rl.error(f"PHR processing error: {e}")
        result = {"status": "error", "error": str(e)}

    return result


def process_jsw_specific_thr_dev(collector: DataCollector, publisher: MQTTPublisher, mapping_data: dict, api_config: dict, unit_id: str, post_time: int) -> dict:
    """
    Process JSW specific THR deviation - corresponds to index-b.py lines 1428-1477
    Only runs for unit_id == "6375e28c32ebf700068ac0aa"
    """
    import requests

    result = {"status": "skipped"}

    if "turbineHeatRate" not in mapping_data:
        rl.warning("No turbineHeatRate in mapping_data for JSW")
        return result

    thr_mapping = mapping_data.get("turbineHeatRate", [])
    eff_url = api_config.get('efficiency', '')

    if not eff_url:
        rl.warning("No efficiency URL configured for JSW")
        return result

    suffixes = ["", "_bperf", "_des"]
    calc_type = ["actual", "bperf", "design"]
    required_params_names = ["realtime", "bestAchieved", "design"]

    jsw_thr_dev_results = []

    for idx, param_name in enumerate(required_params_names):
        if param_name not in thr_mapping:
            continue

        param_data = thr_mapping[param_name]
        jsw_request_body = {}
        for k, v in param_data.items():
            if isinstance(v, dict):
                jsw_request_body.update(v)
            else:
                jsw_request_body[k] = v

        try:
            jsw_response = requests.post(eff_url + "jsw_specific_thr_dev", json=jsw_request_body)
            if jsw_response.status_code == 200:
                jsw_thr_dev_results.append(jsw_response.json())
                rl.info(f"JSW THR dev ({param_name}): success")
            else:
                rl.warning(f"JSW THR dev ({param_name}): failed with status {jsw_response.status_code}")
        except Exception as e:
            rl.error(f"JSW THR dev ({param_name}) error: {e}")

    if jsw_thr_dev_results:
        result = {"status": "success", "count": len(jsw_thr_dev_results)}
    else:
        result = {"status": "no_data"}

    return result
