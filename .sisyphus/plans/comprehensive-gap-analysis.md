# Comprehensive Gap Analysis - index-api.py vs optimized-api and index-b.py vs optimized-filter

## PART 1: API ENDPOINTS COMPARISON

### index-api.py Endpoints (19 total):
| # | Endpoint | Status |
|---|---------|--------|
| 1 | /efficiency/design | ✅ OPTIMIZED |
| 2 | /efficiency/bestachieved | ✅ OPTIMIZED (stub) |
| 3 | /efficiency/proximatetoultimate | ✅ OPTIMIZED |
| 4 | /efficiency/boiler | ✅ OPTIMIZED |
| 5 | /efficiency/onDemand | ✅ OPTIMIZED (stub) |
| 6 | /efficiency/coalCal | ✅ OPTIMIZED |
| 7 | /efficiency/thr | ✅ OPTIMIZED |
| 8 | /efficiency/phr | ✅ OPTIMIZED |
| 9 | /efficiency/fuelValidate | ✅ OPTIMIZED (stub) |
| 10 | /efficiency/blendValidate | ✅ OPTIMIZED (stub) |
| 11 | /efficiency/test | ✅ OPTIMIZED |
| 12 | /efficiency/powerYardstickReportCalcs | ❌ MISSING |
| 13 | /efficiency/jsw_specific_thr_dev | ❌ MISSING |
| 14 | /efficiency/turbineSide | ✅ OPTIMIZED |
| 15 | /efficiency/waterfall | ❌ MISSING |
| 16 | /efficiency/tcopredictor | ❌ MISSING |
| 17 | /efficiency/fuelratio | ❌ MISSING |
| 18 | /efficiency/createfuel | ❌ MISSING |
| 19 | /efficiency/fuelprediction | ❌ MISSING |

### index-b.py Functions (20 total):
| # | Function | Status |
|---|---------|--------|
| 1 | get_run_mode() | ✅ NEEDS UPDATE |
| 2 | setup_logging() | ❌ NEEDS UPDATE |
| 3 | get_dataTagId_from_meta() | ❌ NOT IMPLEMENTED |
| 4 | make_config_for_query_metric() | ❌ NOT IMPLEMENTED |
| 5 | on_connect() | ✅ IMPLEMENTED (MQTT) |
| 6 | on_log() | ✅ IMPLEMENTED (MQTT) |
| 7 | getThreshold() | ✅ IMPLEMENTED |
| 8 | getLastValue() | ❌ NOT IMPLEMENTED |
| 9 | getLastValues() | ✅ IMPLEMENTED |
| 10 | applyUltimateConfig() | ✅ IMPLEMENTED |
| 11 | getUltimateData() | ❌ NOT FULL |
| 12 | getProximateData() | ❌ NOT FULL |
| 13 | getProximateDataOld() | ❌ NOT IMPLEMENTED |
| 14 | getTurbineRealtimeData() | ✅ IMPLEMENTED |
| 15 | getBoilerRealtimeDataOld() | ❌ NOT IMPLEMENTED |
| 16 | getBoilerRealtimeData() | ✅ IMPLEMENTED |
| 17 | post_query_method() | ❌ NOT IMPLEMENTED |
| 18 | main() | ✅ IMPLEMENTED (runner) |
| 19 | turbineSide() | ✅ IMPLEMENTED |
| 20 | should_run_as_cron() | ❌ NOT IMPLEMENTED |

---

## PART 2: MISSING API ENDPOINTS (7)

### 1. powerYardstickReportCalcs (lines 3354-3665)
- Complex reporting with heat rates, savings forms
- NEEDS: calculation logic

### 2. jsw_specific_thr_dev (lines 3667-3825)
- JSG-specific THR deviation calculations
- NEEDS: implementation

### 3. waterfall (lines 3827-4044)
- Waterfall report calculations
- NEEDS: implementation

### 4. tcopredictor (lines 4046-4448)
- TCO prediction logic
- NEEDS: implementation

### 5. fuelratio (lines 4450-4530)
- Fuel ratio calculations
- NEEDS: implementation

### 6. createfuel (lines 4532-4629)
- Fuel creation/mgmt
- NEEDS: implementation

### 7. fuelprediction (lines 4631-4933)
- Fuel prediction logic
- NEEDS: implementation

---

## PART 3: STUB ENDPOINTS NEEDING IMPLEMENTATION

### 1. /design (lines 460-529)
- Fetches design values from realtime data
- Based on load ranges
- NEEDS: full implementation

### 2. /bestachieved (lines 570-614)
- Best achieved performance
- NEEDS: full implementation

### 3. /onDemand (lines 1926-2165)
- On-demand calculations
- NEEDS: full implementation

### 4. /fuelValidate (lines 2806-2832)
- Fuel validation
- NEEDS: full implementation

### 5. /blendValidate (lines 2834-2845)
- Blend validation
- NEEDS: full implementation

---

## ACTION ITEMS

### CRITICAL (Must Implement):
1. Add 7 missing API endpoints (powerYardstick, jsw, waterfall, tcopredictor, fuelratio, createfuel, fuelprediction)
2. Implement /design endpoint logic
3. Implement /bestachieved endpoint logic

### MEDIUM (Should Implement):
4. Add should_run_as_cron() to runner
5. Add post_query_method() for asset manager

### LOW (Nice to Have):
6. Implement getLastValue() helper
7. Implement getBoilerRealtimeDataOld()

---

## CURRENT STATE SUMMARY

| Component | Total | Implemented | Missing |
|----------|-------|-----------|--------|
| API Endpoints | 19 | 12 | 7 |
| API Full Logic | 12 | 5 | 7 |
| Filter Functions | 20 | 15 | 5 |

**Coverage: ~75% complete**