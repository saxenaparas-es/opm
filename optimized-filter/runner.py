import os
import time
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from optimized_filter.config.settings import getconfig
from optimized_filter.data.collectors import DataCollector
from optimized_filter.mqtt.client import MQTTPublisher
from optimized_filter.processors.turbine import TurbineProcessor, BoilerProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_run_mode():
    if os.environ.get('CRON_MODE', '').lower() == 'true':
        return 'cron'
    return 'server'


def main():
    config = getconfig()
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
                'efficiency_url': api_config.get('efficiency', '')},
        unit_id=unit_id
    )
    
    publisher = MQTTPublisher(
        broker_address=broker_config['address'],
        port=broker_config['port'],
        username=broker_config['username'],
        password=broker_config['password'],
        client_id=f"filter_{unit_id}"
    )
    publisher.connect()
    
    mapping = collector.fetch_mapping()
    if not mapping:
        logger.warning(f"No mapping found for unit {unit_id}")
        return
    
    post_time = int((int(datetime.now().timestamp() / 60) * 60) * 1000)
    
    if mapping and len(mapping) > 0:
        mapping_data = mapping[0].get("input", {})
        
        if "turbineHeatRate" in mapping_data:
            turbine_proc = TurbineProcessor(collector, publisher, mapping_data)
            turbine_proc.process(unit_id, post_time)
        
        if "boilerEfficiency" in mapping_data:
            boiler_proc = BoilerProcessor(collector, publisher, mapping_data)
            boiler_proc.process(unit_id, post_time)
    
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