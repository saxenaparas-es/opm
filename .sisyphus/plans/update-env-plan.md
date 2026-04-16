# Updated app_config Integration Plan

## Understanding the Problem

### Original Code Usage of app_config:

**index-api.py** uses `app_config` to get:
- `config["api"]["meta"]` - API metadata endpoint
- `config["api"]["query"]` - Query endpoint  
- `config["api"]["efficiency"]` - Efficiency calculation endpoint
- `config["BROKER_ADDRESS"]` - MQTT broker address

**index-b.py** uses `app_config` to get:
- Same API endpoints
- Same MQTT config
- Unit-specific configs via `config.get(unitId, {})`

---

## What We Need to Do

### 1. Update .env.example with ALL variables from app_config:

From app_config output:
- API_META (meta endpoint) - Already have
- API_QUERY (query endpoint) - Already have
- API_DATA (datapoints) - Already have
- EFFICIENCY_URL - Already have
- BROKER_ADDRESS - Already have
- BROKER_USERNAME - Add
- BROKER_PASSWORD - Add

Additional endpoints from app_config (not currently in .env):
- MODEL_URL
- PREDICTION_URL
- BATCH_EFFICIENCY_URL
- SERVICE_URL
- FCM_URL

### 2. Keep graceful fallback in settings.py (already done):
- If app_config available → use it
- If not → use env vars

---

## Action Plan

1. Update .env.example with all variables
2. Ensure settings.py has proper fallback
3. Document app_config optional usage

This is a SIMPLE fix - just updating the env file!