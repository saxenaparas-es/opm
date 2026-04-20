from _imports import Flask, jsonify
from routes.efficiency import efficiency_bp
from data.fetch_utils import init_config as init_fetch_config
from config.settings import getconfig
from core.dispatch import init_dispatch
from core.logging_utils import (
    logger, log_section, log_variable, log_info, log_warning,
    setup_logging, log_error
)
import sys

try:
    from flask_cors import CORS
except ImportError:
    CORS = None

log_section("STARTING OPTIMIZED API SERVER")
log_info("Python version: " + sys.version.split()[0])

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

log_variable("Flask app name", app.name)
log_variable("JSON_SORT_KEYS", app.config['JSON_SORT_KEYS'])
log_variable("JSONIFY_PRETTYPRINT_REGULAR", app.config['JSONIFY_PRETTYPRINT_REGULAR'])

if CORS:
    CORS(app)
    log_info("CORS enabled")
else:
    log_warning("CORS not available (flask_cors not installed)")


def create_app(config_dict=None):
    log_section("CREATING FLASK APP INSTANCE")
    
    app_instance = Flask(__name__)
    app_instance.config['JSON_SORT_KEYS'] = False
    app_instance.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    
    if CORS:
        CORS(app_instance)
        log_info("CORS enabled for app instance")
    
    if config_dict:
        log_info("Initializing fetch config with custom dict")
        init_fetch_config(config_dict)
    
    log_info("Registering efficiency blueprint at /efficiency")
    app_instance.register_blueprint(efficiency_bp, url_prefix='/efficiency')
    
    log_info("Flask app instance created successfully")
    return app_instance


log_info("Registering efficiency blueprint at /efficiency")
app.register_blueprint(efficiency_bp, url_prefix='/efficiency')


if __name__ == '__main__':
    log_section("RUNNING API SERVER")
    
    try:
        config = getconfig()
        log_info("Configuration loaded")
        log_variable("config_keys", list(config.keys()) if config else "empty")
    except Exception as e:
        log_error(e, "getconfig")
        config = {}
    
    try:
        init_fetch_config(config)
        log_info("Fetch config initialized")
    except Exception as e:
        log_error(e, "init_fetch_config")
    
    try:
        init_dispatch()
        log_info("Dispatch initialized")
    except Exception as e:
        log_error(e, "init_dispatch")
    
    log_info("Starting Flask server on 0.0.0.0:5000")
    log_info("Debug mode: ENABLED")
    log_section("API SERVER READY - ACCEPTING REQUESTS")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
