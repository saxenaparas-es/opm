import os
import time
import logging
from datetime import datetime
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
