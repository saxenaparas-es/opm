import os

API_META = os.environ.get('API_META', '')
API_QUERY = os.environ.get('API_QUERY', '')
EFFICIENCY_URL = os.environ.get('EFFICIENCY_URL', '')
KAIROS_URL = os.environ.get('KAIROS_URL', '')

BROKER_ADDRESS = os.environ.get('BROKER_ADDRESS', '')
BROKER_PORT = int(os.environ.get('Q_PORT', '1883'))
BROKER_USERNAME = os.environ.get('BROKER_USERNAME', '')
BROKER_PASSWORD = os.environ.get('BROKER_PASSWORD', '')

API_USERNAME = os.environ.get('API_USERNAME', '')
API_PASSWORD = os.environ.get('API_PASSWORD', '')

unitId = os.environ.get('UNIT_ID', '')


def getconfig(unit_id=None):
    try:
        import app_config as cfg
        config = cfg.getconfig()
        if unit_id:
            return config.get(unit_id, {})
        return config
    except ImportError:
        return {}


def get_efficiency_url():
    return EFFICIENCY_URL or os.environ.get('EFFICIENCY_URL', '')


def get_api_meta():
    return API_META or os.environ.get('API_META', '')