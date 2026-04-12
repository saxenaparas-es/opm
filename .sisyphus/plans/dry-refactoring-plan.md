# Code Refactoring Plan: Centralized Imports + Rigorous DRY

## Objective
Transform monolithic code into modular, DRY-compliant, industry-level code with centralized imports.

## Scope

### IN:
- Create centralized imports file for all Python files
- Refactor proximate calculations (18 types → 1 core + parameters)
- Refactor boiler efficiency to reduce duplication
- Centralize IAPWS97 steam property calculations
- Keep ALL calculation formulas EXACTLY as-is
- Output to optimized-api/ and optimized-filter/

### OUT:
- Merge api and filter - keep separate
- Modify any calculation formulas
- Change return values/response structure

---

## Work Breakdown

### Wave 1: Create Centralized Imports

**T1: Create centralized imports module**
- File: `optimized-api/_imports.py`
- Content: All shared imports (flask, iapws97, math, etc.)
- Each calculation file imports from this single source

### Wave 2: DRY Refactor - Proximate Calculations

**T2: Refactor proximate.py (18 types → 1 core function)**
- Extract common calculation to `_proximate_core()`
- Add parameter flags for variations:
  - `fixed_sulphur`: for type10 (sulphur=0.7)
  - `gcv_scaling`: for type13 (carbon × GCV/100)
- Create dispatch mapping to call core with correct params
- Remove 300+ lines of duplicate code

### Wave 3: DRY Refactor - Boiler Efficiency

**T3: Refactor boiler_efficiency.py**
- Extract common calculation patterns
- Create base function that type7-type10, type18 can call with params
- Reduce code duplication while preserving exact formulas

### Wave 4: DRY Refactor - Turbine

**T4: Refactor turbine.py**
- Create centralized IAPWS97 helper in `_imports.py`
- Create steam property wrapper functions
- Reduce repeated IAPWS97 instantiation code

### Wave 5: Update All Import Statements

**T5: Update all Python files to use centralized imports**
- Update app.py, routes/efficiency.py, core/dispatch.py
- Update data/fetch_utils.py
- Update config/settings.py
- Update optimized-filter files

### Wave 6: Final Verification

**T6: Verify all calculations produce identical results**
- Test each endpoint with sample data
- Compare output with original monolithic code

---

## Key DRY Refactoring Details

### Proximate Core Function
```python
def _proximate_core(coalFC, coalVM, coalAsh, coalMoist, 
                    fixed_sulphur=None, gcv_scaling=False, coalGCV=None):
    """Common proximate to ultimate calculation"""
    # ... exact formulas preserved ...
    # Handle variations via parameters
```

### IAPWS97 Centralized Helper
```python
# In _imports.py
def get_steam_properties(temp_c, pressure_bar):
    """Centralized IAPWS97 wrapper"""
    steam = IAPWS97(T=temp_c + 273, P=pressure_bar * 0.0980665)
    return steam.h / 4.1868  # Convert to kcal/kg
```

---

## Success Criteria
- [ ] All imports centralized in one file
- [ ] Proximate: 18 types implemented with ~60% less code
- [ ] Boiler: Reduced duplication where applicable
- [ ] Turbine: Centralized steam property calculations
- [ ] All calculations produce IDENTICAL results to original
- [ ] Tests pass for all endpoints
