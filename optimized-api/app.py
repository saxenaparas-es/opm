from optimized_api._imports import Flask, jsonify
from optimized_api.routes.efficiency import efficiency_bp
from optimized_api.data.fetch_utils import init_config as init_fetch_config
from optimized_api.config.settings import getconfig
try:
    from flask_cors import CORS
except ImportError:
    CORS = None

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

if CORS:
    CORS(app)


def create_app(config_dict=None):
    app_instance = Flask(__name__)
    app_instance.config['JSON_SORT_KEYS'] = False
    app_instance.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    
    if CORS:
        CORS(app_instance)
    
    if config_dict:
        init_fetch_config(config_dict)
    
    app_instance.register_blueprint(efficiency_bp, url_prefix='/efficiency')
    
    return app_instance


app.register_blueprint(efficiency_bp, url_prefix='/efficiency')


if __name__ == '__main__':
    config = getconfig()
    init_fetch_config(config)
    app.run(host='0.0.0.0', port=5000, debug=True)