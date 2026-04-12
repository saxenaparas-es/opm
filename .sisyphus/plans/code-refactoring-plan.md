# Code Refactoring & Optimization Work Plan

## Overview
**Project**: Refactor and optimize index-api.py and index-b.py to industry-level standards
**Objective**: Transform monolithic, inconsistent code into modular, DRY-compliant, O(1) dispatch optimized codebase
**Scope**: 2 repos (API repo + Filter/Buffer repo)

---

## VERIFICATION COMPLETE - COMPREHENSIVE ANALYSIS

### Verified: index-api.py

**11 REST Endpoints:**
| Route | Function | Lines |
|-------|----------|-------|
| `/efficiency/design` | `fetchDesign()` | 460 |
| `/efficiency/bestachieved` | `bestAchieved()` | 570 |
| `/efficiency/proximatetoultimate` | `proximatetoultimate()` | 616 |
| `/efficiency/boiler` | `boilerEfficiency()` | 1012 |
| `/efficiency/onDemand` | `onDemandForCombustion()` | 1926 |
| `/efficiency/coalCal` | `coalFlowCalculation()` | 2167 |
| `/efficiency/thr` | `THRCalculation()` | 2319 |
| `/efficiency/phr` | `PHRCalculation()` | 2769 |
| `/efficiency/fuelValidate` | `validate_json()` | 2806 |
| `/efficiency/blendValidate` | `validate_blend()` | 2834 |
| `/efficiency/test` | `test()` | 2847 |

**35+ Calculation Functions:**
- 17 Proximate to Ultimate types (type1-type15, type17, type18)
- 18 Boiler Efficiency types (type1-type18)
- 16 THR categories (cogent, cogent2-cogent8, ingest, ingest2, pressureInMpa, pressureInKsc, pressureInKsc1, lpg_type, DBPower)
- Coal flow calculations, Plant heat rate

**Data Fetching Functions:** 12+ functions (getLastValues, getHistoricValues, getProximateData, getUltimateData, etc.)

**Helper Utilities:** NpEncoder, replace_with_description, add_hr_reconciliation, get_relationship_between_input_output, etc.

### Verified: index-b.py

**Main Execution Flow (main() - lines 517-1544):**
1. Fetch mapping file from API
2. Calculate post_time (rounded to minute)
3. Turbine Heat Rate Processing → MQTT/Kairos publishing
4. Boiler Efficiency Processing → MQTT/Kairos publishing
5. Plant Heat Rate calculation

**Data Collection Functions:** 14+ functions
**MQTT Publishing:** 5 topic patterns per output
**Scheduler:** APScheduler with configurable frequency (default 300s)

### Verified: Cross-Cutting Issues

**Credentials Status:** GOOD NEWS - Credentials come from `app_config` module, NOT hardcoded in these files!

**if-elif Chains Needing O(1) Conversion:**
1. Proximate types (lines 626-663) - ALREADY HAS DICT (lines 991-1008), just not using it!
2. Boiler types (lines 1020-1066) - ALREADY HAS DICT (lines 2852-2867), just not using it!
3. **THR category dispatch (lines 2342-2764) - NEEDS NEW DICT**
4. OnDemand boiler types (lines 2103-2140) - NEEDS DICT

**Duplicated Code Blocks (between both files):**
- `getLastValues()` - in both files
- `getProximateData()` - in both files
- `getUltimateData()` - in both files
- `getBoilerRealtimeData()` - in both files
- `getThreshold()` - in both files

**Communication Protocol:**
- index-b.py calls index-api.py via REST API (8 endpoints)
- Then publishes results to MQTT + Kairos

---

## Protected Items (Calculations Must Be Preserved Exactly)

### Proximate to Ultimate Core Formulas:
```
Carbon:      0.97 * coalFC + 0.7 * (coalVM + 0.1*coalAsh) - (coalMoist * (0.6 - 0.01*coalMoist))
Hydrogen:    0.036 * coalFC + 0.086 * (coalVM - 0.1*coalAsh) - 0.0035 * coalMoist^2 * (1 - 0.02*coalMoist)
Nitrogen:    2.1 - 0.02 * coalVM
Sulphur:     0.009 * (coalFC + coalVM)
Oxygen:      100 - carbon - hydrogen - nitrogen - sulphur - ash - moisture
```

### Boiler Efficiency Core Formulas:
```
TheoAirRequired:  0.116 * carbon + 0.348 * hydrogen + 0.0435 * sulphur - 0.0435 * oxygen
ExcessAir:        (O2 * 100) / (21 - O2)
ActualAirSupplied: (1 + ExcessAir/100) * TheoAirRequired
massofDryFlueGas:  (carbon * 44/12 + sulphur * 64/32 + nitrogen + ActualAirSupplied * 77 + (ActualAirSupplied - TheoAirRequired) * 23) / 100
```

### THR Core Formulas:
- IAPWS97 steam property calculations
- Enthalpy conversion: `/ 4.1868`
- All 16 category-specific formulas

### Key Constants (DO NOT CHANGE):
- 8080, 8077, 5654, 5744 (ash heat values)
- 584, 0.45 (moisture loss constants)
- 21 (oxygen in air)
- 0.116, 0.348, 0.0435 (air requirement coefficients)

---

## Work Plan

### Phase 1: Analysis & Strategy

- [ ] 1.1 Create detailed mapping of all function types (proximates, boilers, THR calculations)
- [ ] 1.2 Identify all duplicate code blocks that can be consolidated
- [ ] 1.3 Document all calculation formulas that MUST be preserved exactly
- [ ] 1.4 Map all current hardcoded credentials requiring environment variable conversion

### Phase 2: API Repo Refactoring (index-api.py → optimized-api/)

- [ ] 2.1 Create modular folder structure
  ```
  optimized-api/
  ├── config/
  │   └── settings.py          # Environment-based config management
  ├── core/
  │   ├── __init__.py
  │   ├── dispatch.py          # O(1) type dispatch dictionaries
  │   ├── validators.py        # Input validation utilities
  │   └── exceptions.py        # Custom exceptions
  ├── calculations/
  │   ├── __init__.py
  │   ├── proximate.py         # Proximate to ultimate conversions
  │   ├── boiler_efficiency.py # All boiler efficiency types
  │   ├── turbine.py           # THR calculations
  │   ├── coal.py              # Coal flow calculations
  │   └── plant.py             # Plant heat rate
  ├── data/
  │   ├── __init__.py
  │   ├── fetch_utils.py       # Data fetching utilities
  │   └── transformers.py      # Data transformation
  ├── routes/
  │   ├── __init__.py
  │   ├── efficiency.py        # Flask route handlers
  │   └── websocket.py         # Real-time updates
  ├── tests/
  │   ├── __init__.py
  │   ├── test_calculations.py # Calculation accuracy tests
  │   └── test_api.py          # API endpoint tests
  └── app.py                   # Main Flask application entry point
  ```

- [ ] 2.2 Implement O(1) dispatch system for all type handlers
- [ ] 2.3 Create environment-based configuration module
- [ ] 2.4 Extract common utilities (validators, formatters)
- [ ] 2.5 Add proper docstrings and type hints
- [ ] 2.6 Preserve ALL calculation formulas exactly (verification required)
- [ ] 2.7 Clean up dead code while preserving important comments

### Phase 3: Filter Repo Refactoring (index-b.py → optimized-filter/)

- [ ] 3.1 Create modular folder structure
  ```
  optimized-filter/
  ├── config/
  │   └── settings.py          # Environment-based config
  ├── core/
  │   ├── __init__.py
  │   ├── dispatch.py          # Type dispatch
  │   └── utils.py             # Common utilities
  ├── data/
  │   ├── __init__.py
  │   ├── collectors.py        # Data collection from sensors
  │   ├── filters.py          # Data filtering logic
  │   └── buffers.py          # Buffer management
  ├── mqtt/
  │   ├── __init__.py
  │   ├── client.py           # MQTT client wrapper
  │   └── publishers.py       # Data publishers
  ├── scheduler/
  │   ├── __init__.py
  │   └── jobs.py             # Scheduled jobs
  ├── processors/
  │   ├── __init__.py
  │   ├── turbine.py          # Turbine data processing
  │   └── boiler.py           # Boiler data processing
  ├── tests/
  │   ├── __init__.py
  │   └── test_processors.py
  └── runner.py               # Main entry point
  ```

- [ ] 3.2 Separate data collection from processing logic
- [ ] 3.3 Implement environment-based credential management
- [ ] 3.4 Create reusable MQTT client with proper error handling
- [ ] 3.5 Add proper logging and monitoring hooks
- [ ] 3.6 Preserve data flow and calculation calls to API

### Phase 4: Cross-Cutting Concerns

- [ ] 4.1 Create shared constants module (for both repos)
- [ ] 4.2 Implement consistent error response format
- [ ] 4.3 Add structured logging throughout
- [ ] 4.4 Create environment variable validation
- [ ] 4.5 Document API contract between repos

### Phase 5: Testing & Verification

- [ ] 5.1 Create calculation verification tests (ensure formulas unchanged)
- [ ] 5.2 Run integration tests between both repos
- [ ] 5.3 Performance benchmarking (before vs after)
- [ ] 5.4 Code quality checks (linting, type checking)
- [ ] 5.5 Security audit (verify no hardcoded secrets)

---

## Key Decisions Required

1. **Python Version**: Target Python 3.9+ for type hints support?
2. **Test Framework**: pytest preferred?
3. **Lint Tool**: Black + flake8 or just Ruff?
4. **API Client**: Keep existing or use requests-futures for async?
5. **Logging**: JSON structured logging or standard?

---

## Protected Items (DO NOT MODIFY)

### Calculation Formulas (Must Preserve Exactly)

From proximateToUltimate calculations:
- Carbon: `0.97 * coalFC + 0.7 * (coalVM + 0.1*coalAsh) - (coalMoist * (0.6 - 0.01*coalMoist))`
- Hydrogen: `0.036 * coalFC + 0.086 * (coalVM - 0.1*coalAsh) - 0.0035 * coalMoist^2 * (1 - 0.02*coalMoist)`
- Nitrogen: `2.1 - 0.02 * coalVM`
- Sulphur: `0.009 * (coalFC + coalVM)`

From boilerEfficiency calculations:
- TheoAirRequired: `0.116 * carbon + 0.348 * hydrogen + 0.0435 * sulphur - 0.0435 * oxygen`
- ExcessAir: `(O2 * 100) / (21 - O2)`
- All loss calculations with specific constants (8080, 8077, 5654, etc.)

From THR calculations:
- All IAPWS97 steam property calculations
- Enthalpy calculations with specific conversion factors (4.1868)
- All category-specific formulas (cogent, ingest, pressureInMpa, etc.)

---

## Success Criteria

- [ ] All if-elif-else chains replaced with O(1) dictionary dispatch
- [ ] All hardcoded credentials moved to environment variables
- [ ] Code duplicated reduced by 60% (DRY principle)
- [ ] All calculations produce identical results to original code
- [ ] Two separate, independently deployable repos
- [ ] 80% of functions have proper docstrings
- [ ] Type hints on all public function signatures
- [ ] Zero security vulnerabilities (no hardcoded secrets)
- [ ] Tests verify calculation accuracy matches original

---

## Notes

- User explicitly requested output as separate folders, not ZIP
- Calculations must not be touched - this is highest priority
- Current code already has some optimized patterns (dictionary dispatch exists) - ensure consistency
- Remove dead comments but preserve important calculation rationale comments