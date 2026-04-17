import os
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / '.env'
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)

API_META = os.environ.get('API_META', '')
API_QUERY = os.environ.get('API_QUERY', '')
API_DATA = os.environ.get('API_DATA', '')
EFFICIENCY_URL = os.environ.get('EFFICIENCY_URL', '')

MODEL_URL = os.environ.get('MODEL_URL', '')
PREDICTION_URL = os.environ.get('PREDICTION_URL', '')
BATCH_EFFICIENCY_URL = os.environ.get('BATCH_EFFICIENCY_URL', '')
SERVICE_URL = os.environ.get('SERVICE_URL', '')

BROKER_ADDRESS = os.environ.get('BROKER_ADDRESS', '')
BROKER_PORT = int(os.environ.get('Q_PORT', '1883'))
BROKER_USERNAME = os.environ.get('BROKER_USERNAME', '')
BROKER_PASSWORD = os.environ.get('BROKER_PASSWORD', '')

API_USERNAME = os.environ.get('API_USERNAME', '')
API_PASSWORD = os.environ.get('API_PASSWORD', '')


def getconfig():
    try:
        import app_config as cfg
        return cfg.getconfig()
    except ImportError:
        return {
            'api': {
                'meta': API_META,
                'query': API_QUERY,
                'datapoints': API_DATA,
                'efficiency': EFFICIENCY_URL,
                'model': MODEL_URL,
                'prediction': PREDICTION_URL,
                'batchefficiency': BATCH_EFFICIENCY_URL,
                'service': SERVICE_URL
            }
        }


def get_efficiency_url():
    config = getconfig()
    return config.get('api', {}).get('efficiency', '')


def get_api_config():
    config = getconfig()
    return config.get('api', {})