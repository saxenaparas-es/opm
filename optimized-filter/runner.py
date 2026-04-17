import os
import time
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from config.settings import getconfig
from data.collectors import DataCollector
from mqtt.client import MQTTPublisher
from processors.turbine import TurbineProcessor, BoilerProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_run_mode():
    if os.environ.get('CRON_MODE', '').lower() == 'true':
        return 'cron'
    return 'server'


def main():
    config = getconfig()
    logger.info(f"Full config: {config}")
    unit_id = os.environ.get('UNIT_ID', '')
    
    if not unit_id:
        logger.error("UNIT_ID not set")
        return
    
    unit_config = getconfig(unit_id)
    broker_config = {
        'address': unit_config.get('BROKER_ADDRESS', ''),
        'port': int(unit_config.get('Q_PORT', 1883)),
        'username': unit_config.get('BROKER_USERNAME', ''),
        'password': unit_config.get('BROKER_PASSWORD', '')
    }
    
    api_config = unit_config.get('api', {})
    
    collector = DataCollector(
        config={'api_meta': api_config.get('meta', ''), 
                'api_query': api_config.get('query', ''),
                'efficiency_url': api_config.get('efficiency', ''),
                'kairos': api_config.get('kairos', '')},
        unit_id=unit_id
    )
    
    kairos_url = api_config.get('kairos', '')
    
    publisher = MQTTPublisher(
        broker_address=broker_config['address'],
        port=broker_config['port'],
        username=broker_config['username'],
        password=broker_config['password'],
        client_id=f"filter_{unit_id}",
        kairos_url=kairos_url,
        unit_id=unit_id
    )
    
    try:
        publisher.connect()
        logger.info("MQTT connected successfully")
    except Exception as e:
        logger.warning(f"MQTT connection failed: {e}. Continuing without MQTT.")
        publisher = None
    
    mapping = collector.fetch_mapping()
    logger.info(f"Fetched mapping for unit {unit_id}: {len(mapping)} records")
    logger.info(f"Full mapping[0] keys: {list(mapping[0].keys()) if mapping else []}")
    logger.info(f"Mapping[0] type: {type(mapping[0]) if mapping else 'None'}")
    if mapping and len(mapping) > 0:
        logger.info(f"Mapping[0] content: {str(mapping[0])[:500]}")
    
    if not mapping:
        logger.warning(f"No mapping found for unit {unit_id}")
        return
    
    post_time = int((int(datetime.now().timestamp() / 60) * 60) * 1000)
    
    if mapping and len(mapping) > 0:
        mapping_data = mapping[0].get("output", {})
        if not mapping_data:
            mapping_data = mapping[0].get("input", {})
        logger.info(f"Mapping data keys: {list(mapping_data.keys())}")
        
        if "turbineHeatRate" in mapping_data:
            logger.info("Processing turbineHeatRate...")
            turbine_proc = TurbineProcessor(collector, publisher, mapping_data, unit_id)
            turbine_proc.process(unit_id, post_time)
        
        if "boilerEfficiency" in mapping_data:
            logger.info("Processing boilerEfficiency...")
            boiler_proc = BoilerProcessor(collector, publisher, mapping_data, unit_id)
            boiler_proc.process(unit_id, post_time)
    
    if publisher:
        publisher.close()
    logger.info(f"Completed processing for unit {unit_id}")


if __name__ == '__main__':
    run_mode = get_run_mode()
    logger.info(f"Starting in {run_mode} mode")
    
    frequency = int(os.environ.get('FREQUENCY', '300'))
    
    if run_mode == 'cron':
        main()
    else:
        scheduler = BackgroundScheduler()
        scheduler.add_job(main, 'interval', seconds=frequency, misfire_grace_time=None)
        scheduler.start()
        logger.info(f"Scheduler started with {frequency}s interval")
        
        while True:
            time.sleep(60)