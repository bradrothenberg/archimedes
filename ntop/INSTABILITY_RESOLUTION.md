# 6-DOF Simulation Instability - RESOLVED

## Summary

The 6-DOF simulation was showing severe pitch divergence and appeared unstable despite AVL analysis indicating stable aerodynamics (Cma = -0.237 /rad, positive static margin). **The root cause was a unit mismatch in the atmosphere model**, causing dynamic pressure (qbar) to be calculated 69x too large.

## Problem

Initial simulation showed:
- Severe pitch divergence (pitch angle → +100°)
- Altitude loss of 8,000 ft in 20 seconds
- Velocity acceleration to 1,600 ft/s (uncontrolled)
- Linear acceleration: 1,875 ft/s² (~58g)
- Angular acceleration: 142 rad/s²

## Root Cause Analysis

### Investigation Steps

1. **Verified Aero Deck** ✓
   - Confirmed Cma = -0.237 /rad (negative = stable)
   - All Cmα values negative throughout flight envelope
   - Cmq = -1.44 /rad (negative = damped)
   - Aero model correctly produces restoring moments

2. **Checked Trim Condition** ✓
   - Found hardcoded trim values were NOT actually trimmed
   - Massive accelerations indicated something fundamentally wrong

3. **Traced Force Computation** ✓
   - Discovered qbar = 10,311 lbf/ft² (should be ~149 lbf/ft²)
   - Mach = 1.64 (should be ~0.47)
   - All aerodynamic forces 69x too large

4. **Identified Unit Mismatch** ✓
   - `StandardAtmosphere1976` uses SI units (meters, Pascals, kg/m³)
   - Simulation uses US customary units (feet, lbf/ft², slug/ft³)
   - Altitude in feet was being treated as meters
   - 20,000 ft was interpreted as 20,000 m (65,600 ft equivalent)

## Solution

Created `atmosphere_us.py` wrapper that:
1. Converts altitude from feet → meters before table lookup
2. Converts pressure from Pascals → lbf/ft²
3. Converts temperature from Kelvin → Rankine
4. Computes qbar in US customary units (lbf/ft²)

### Results After Fix

**Before:**
- qbar = 10,311 lbf/ft² ✗
- Mach = 1.64 ✗
- az = -1,875 ft/s² = -58g ✗
- q_dot = -142 rad/s² ✗

**After:**
- qbar = 148 lbf/ft² ✓
- Mach = 0.467 ✓
- az = +4.6 ft/s² = +0.14g ✓
- q_dot = -2.0 rad/s² ✓

## Simulation Results

With the fixed atmosphere model, the 6-DOF simulation now shows:
- **Bounded oscillations** after control doublet inputs
- **Damped response** - oscillations decay over time
- **Stable behavior** - no pitch divergence
- **Reasonable forces and moments**

The aircraft still shows a descent due to imperfect hardcoded trim values, but this is NOT aerodynamic instability - it's simply an unbalanced initial condition.

## Files Created/Modified

### New Files:
- `src/archimedes/experimental/aero/atmosphere_us.py` - US units wrapper for atmosphere
- `ntop/trace_forces.py` - Debug script for force computation
- `ntop/check_trim.py` - Trim verification script
- `ntop/test_aero_stability.py` - Aero model stability test
- `ntop/debug_aero_deck.py` - Aero deck analysis
- `ntop/debug_forces.py` - Force vs elevator sweep
- `ntop/INSTABILITY_RESOLUTION.md` - This document

### Modified Files:
- `ntop/run_ntop_sim.py` - Import atmosphere_us wrapper
- `ntop/ntop_vehicle.py` - Import atmosphere_us wrapper

## Verification

The aero model is confirmed STABLE:
```
Cma = -0.241 /rad  (negative = stable pitch stiffness)
Cmq = -1.439 /rad  (negative = stable pitch damping)
Static Margin = +8.39%  (positive = stable)
Neutral Point = 13.54 ft (8.36" aft of CG)
```

## Conclusion

**The aircraft IS STABLE.** The simulation now correctly models the aerodynamics with:
- Proper dynamic pressure calculation
- Correct aerodynamic forces and moments
- Bounded, damped response to perturbations

The remaining descent in the simulation is due to imperfect trim (hardcoded values), not aerodynamic instability. A proper trim solver would eliminate this.

## Next Steps (Optional)

To achieve perfect trimmed flight:
1. Use the trim solver (`trim.py`) to find true equilibrium
2. Update simulation with proper trim values (alpha, elevator, throttle)
3. Aircraft should maintain level flight indefinitely

---

**Status**: ✓ RESOLVED
**Date**: 2025-11-11
**Solution**: Fixed unit mismatch in atmosphere model (SI → US customary)
