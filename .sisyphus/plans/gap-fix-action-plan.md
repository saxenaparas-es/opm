# Gap Fix Action Plan - optimized-filter vs index-b.py

## Purpose
This plan identifies ALL gaps between the original index-b.py (1704 lines) and optimized-filter to ensure full functional parity.

---

## GAP ANALYSIS

### GAP 1: MQTT Publishing - Triple Values (CRITICAL)
**Original**: lines 1104-1126, 726-743
- Publishes 3 values per metric: actual, design (_des), bestperf (_bperf)
- Also publishes to `/r` real-time topics

**Current**: Only publishes 1 value (actual)
**Impact**: Missing design & best performance tracking

**Files to modify**:
- `optimized-filter/processors/turbine.py` - BoilerProcessor.process(), TurbineProcessor.process()

---

### GAP 2: Design & BestPerformance API Calls (CRITICAL)
**Original**: lines 639-691
- Calls `/efficiency/design` for design values
- Calls `/efficiency/bestachieved` for best performance
- All 3 results used for THR calculation

**Current**: Only calls `/efficiency/thr`
**Impact**: Cannot calculate design/bestperf efficiency values

**Files to modify**:
- `optimized-filter/data/collectors.py` - Add call_design_api(), call_bestachieved_api() methods
- `optimized-filter/processors/turbine.py` - TurbineProcessor.process()

---

### GAP 3: KairosDB Publishing (MEDIUM)
**Original**: Uses BOTH MQTT + KairosDB (qr.postDataPacket)
- Lines 741-743, 780-782, 1108-1116, 1125-1126

**Current**: Only MQTT
**Impact**: Missing historical data storage

**Files to modify**:
- `optimized-filter/mqtt/client.py` - Add KairosDB publishing method

---

### GAP 4: Plant Heat Rate Tracking (MEDIUM)
**Original**: lines 622-636, 714-721
- Tracks arrays: realtime, design, bestAchieved
- For turbineHeatRate, boilerEfficiency, boilerSteamFlow, turbineSteamFlow

**Current**: Not tracking
**Impact**: Cannot calculate overall plant performance

**Files to modify**:
- `optimized-filter/processors/turbine.py` - Add plant_heat_rate tracking

---

### GAP 5: Asset Manager Publishing (MEDIUM)
**Original**: lines 516-536, 1065-1198
- Publishes to asset manager metric namespace
- With tags: dataTagId, parameter, measureUnit, calculationType, relatedTo

**Current**: Not implemented
**Impact**: Missing asset manager integration

**Files to modify**:
- `optimized-filter/mqtt/client.py` - Add publish_asset_manager() method

---

### GAP 6: CoalCal Outputs Publishing (LOW)
**Original**: lines 1201-1233
- Publishes coalCalOutputs (coalFlow, costOfFuel, costPerUnitSteam)
- 5 variations: actual, design, bestperf, des_dev, bperf_dev

**Current**: Not implemented
**Impact**: Missing coal calculation outputs

**Files to modify**:
- `optimized-filter/processors/turbine.py` - Add coal_cal_publish() method

---

### GAP 7: Threshold Checking (MEDIUM)
**Original**: lines 581-617
- Checks equipmentStatus tag
- Skip flag logic based on load/steamFlow thresholds

**Current**: Not implemented
**Impact**: No equipment health checking

**Files to modify**:
- `optimized-filter/data/collectors.py` - Add check_threshold() method

---

### GAP 8: post_query_method (LOW)
**Original**: lines 516-536
- Generic relationship-based publishing for asset manager

**Current**: Not implemented
**Impact**: Missing generic publishing

**Files to modify**:
- `optimized-filter/mqtt/client.py` - Add post_query_method()

---

### GAP 9: Turbine Side Calculations (LOW)
**Original**: lines 1569-1615
- Separate turbineSide() function for isentropic efficiency

**Current**: Not implemented
**Impact**: Missing turbine-side calculations

**Files to modify**:
- New file: `optimized-filter/processors/turbine_side.py`

---

### GAP 10: applyUltimateConfig (MEDIUM)
**Original**: lines 264-302
- Handles dynamic/static fuel mixture types

**Current**: Not implemented
**Impact**: Cannot handle blended fuels

**Files to modify**:
- `optimized-filter/data/collectors.py` - Add apply_fuel_config() method

---

## ACTION PLAN

### Phase 1: Core Publishing Fixes (Priority 1)

#### Task 1.1: Fix Boiler 3-value Publishing
- Modify: `processors/turbine.py` BoilerProcessor.process()
- Add: _des and _bperf datapoint publishing
- Add: MQTT /r topic publishing

#### Task 1.2: Fix Turbine 3-value Publishing  
- Modify: `processors/turbine.py` TurbineProcessor.process()
- Add: design, bestperf calculations
- Add: /r topics

#### Task 1.3: Add KairosDB Publishing
- Modify: `mqtt/client.py`
- Add: publish_to_kairos() method

---

### Phase 2: API Integration (Priority 2)

#### Task 2.1: Add Design API Calls
- Modify: `data/collectors.py`
- Add: call_design_api() method

#### Task 2.2: Add BestAchieved API Calls
- Modify: `data/collectors.py`
- Add: call_bestachieved_api() method

#### Task 2.3: Update Turbine Processor
- Modify: `processors/turbine.py`
- Use all 3 API calls for design/bestperf

---

### Phase 3: Supporting Logic (Priority 3)

#### Task 3.1: Plant Heat Rate Tracking
- Modify: `processors/turbine.py`
- Add: plant_heat_rate dict tracking

#### Task 3.2: Asset Manager Publishing
- Modify: `mqtt/client.py`
- Add: publish_asset_manager() method

#### Task 3.3: Threshold Checking
- Modify: `data/collectors.py`
- Add: check_threshold() method

#### Task 3.4: Fuel Config Handling
- Modify: `data/collectors.py`
- Add: apply_fuel_config() method

---

### Phase 4: Additional Features (Priority 4)

#### Task 4.1: CoalCal Publishing
- Modify: `processors/turbine.py`
- Add: coal output publishing

#### Task 4.2: Turbine Side
- New: `processors/turbine_side.py`
- Implement: turbineSide() function

---

## Success Criteria

After implementation:
- [ ] All 3 values published (actual, _des, _bperf)
- [ ] Design & BestAchieved API calls working
- [ ] KairosDB publishing functional
- [ ] Plant heat rate tracking enabled
- [ ] Asset manager publishing functional
- [ ] All original functionality preserved

---

## Files to Modify

| File | Changes |
|------|--------|
| `optimized-filter/mqtt/client.py` | +3 methods |
| `optimized-filter/data/collectors.py` | +5 methods |
| `optimized-filter/processors/turbine.py` | +major logic |
| `optimized-filter/processors/turbine_side.py` | NEW file |