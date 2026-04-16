import os

API_META = os.environ.get('API_META', '')
API_QUERY = os.environ.get('API_QUERY', '')
API_DATA = os.environ.get('API_DATA', '')
EFFICIENCY_URL = os.environ.get('EFFICIENCY_URL', '')
KAIROS_URL = os.environ.get('KAIROS_URL', '')

# Additional endpoints from app_config
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

UNIT_ID = os.environ.get('UNIT_ID', '')


def getconfig(unit_id=None):
    try:
        import app_config as cfg
        config = cfg.getconfig()
        if unit_id:
            return config.get(unit_id, {})
        return config
    except ImportError:
        # Fallback to environment variables
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
            },
            'BROKER_ADDRESS': BROKER_ADDRESS,
            'BROKER_USERNAME': BROKER_USERNAME,
            'BROKER_PASSWORD': BROKER_PASSWORD,
            'kairos': KAIROS_URL,
            'UNIT_ID': UNIT_ID
        }


def get_efficiency_url():
    return EFFICIENCY_URL or os.environ.get('EFFICIENCY_URL', '')


def get_api_meta():
    return API_META or os.environ.get('API_META', '')