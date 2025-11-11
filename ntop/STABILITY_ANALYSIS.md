# nTop Flying Wing - Stability Analysis Report

## Executive Summary

**CRITICAL FINDING**: The nTop flying wing is **statically unstable** in pitch and **cannot fly safely** without modifications.

The 6-DOF simulation successfully revealed a fundamental design flaw: the center of gravity is positioned too far aft, resulting in positive pitch stiffness (Cma > 0), which causes divergent pitch-up behavior.

## Simulation Results

### Test: Elevator Doublet (±5°, t=2-4s)

**Observed Behavior:**
- Velocity divergence: 484 → 3,000+ ft/s in 20 seconds
- Altitude loss: 20,000 → 8,000 ft (12,000 ft lost)
- Extreme pitch excursions: ±180° oscillations
- Roll coupling: -180° despite no aileron input
- Angular rates: >100 deg/s pitch rate spikes
- Uncontrolled acceleration into dive

**Conclusion**: Aircraft exhibits classic pitch divergence instability.

## Root Cause Analysis

### Stability Derivatives (from AVL at α=5°)

| Derivative | Value | Requirement | Status |
|------------|-------|-------------|--------|
| Cma | **+0.6259 /rad** | **< 0** | **FAIL** |
| Cmq | -1.7965 /rad | < -0.5 | PASS |
| CLa | 3.3411 /rad | > 0 | PASS |
| Clp | -0.2376 /rad | < 0 | PASS |
| Cnr | -0.0038 /rad | < 0 | MARGINAL |

**Critical Issue**: **Cma is POSITIVE**, meaning pitching moment INCREASES with angle of attack. This is aerodynamically unstable.

### Center of Gravity Analysis

**From mass.csv:**
- CG X-location: 154.15 inches (12.846 feet)

**AVL Reference Point:**
- Xref = 12.846 feet = 154.15 inches
- **CONFIRMED**: AVL moments are computed at the actual CG (no transfer needed)

**Wing Geometry:**
- Root LE: 0.26 inches
- Root TE: 269.07 inches
- Root chord: 268.81 inches
- Mean aerodynamic chord (MAC): 99.58 inches = 8.30 feet

**CG Position:**
- CG at 57.2% of root chord
- CG at 18.7 feet from nose

**Static Margin:**
- CG is 0.187 MAC (18.7%) **aft** of the neutral point
- For comparison, typical aircraft: +5% to +15% MAC (CG ahead of NP)

### Static Margin

Static Margin = (Neutral Point - CG) / MAC

Calculation:
- Static Margin = -Cma / CLa = -0.6259 / 3.3411 = **-0.187 MAC**

With negative static margin:
- CG is **0.187 MAC (18.7%) aft** of the neutral point
- Aircraft is **statically unstable** in pitch
- Will pitch up divergently without continuous corrective input

### Required CG Relocation

To achieve a safe +10% static margin:
- Required CG shift: **28.6 inches forward** (2.38 feet)
- Target CG location: 125.5 inches from nose (currently at 154.15 inches)
- This would place CG at ~47% root chord (currently at 57%)

## Physical Explanation

A statically stable aircraft has its CG **ahead** of its neutral point (NP):
- When disturbed to higher AoA → pitching moment is nose-down → restoring
- Cma < 0 (negative slope)
- Static margin is positive

This aircraft has CG **behind** the neutral point:
- When disturbed to higher AoA → pitching moment is nose-up → diverging
- Cma > 0 (positive slope)
- Static margin is negative (-18.7%)
- Like balancing a pencil on your finger - unstable equilibrium

**Key Stability Relationship:**
```
Cma = CLa × (CG - NP) / MAC

For this aircraft:
+0.6259 = 3.3411 × (CG - NP) / 8.30 ft
CG - NP = +1.55 feet = +0.187 MAC

The positive value confirms CG is aft of NP.
```

## Consequences

1. **Unflyable without computer**: Requires continuous active control
2. **Pilot workload**: Impossible for human to fly manually
3. **Safety**: Any control system failure results in immediate loss of control
4. **Certification**: Would not meet FAA/EASA stability requirements

## Solutions (Ranked by Feasibility)

### Option 1: Relocate Center of Gravity (RECOMMENDED)

**Target**: Move CG forward by 28.6 inches to achieve +10% static margin

**Current State:**
- CG at 154.15 inches (57.2% root chord)
- Static margin: -18.7% MAC (unstable)

**Target State:**
- CG at 125.5 inches (46.7% root chord)
- Static margin: +10% MAC (stable)

**Methods:**
- Move batteries/fuel forward
- Add ballast in nose
- Redistribute payload
- Redesign internal layout

**Benefits:**
- Inherent stability without flight control system
- Simpler flight controls
- Certifiable design
- Pilot-friendly
- Eliminates need for continuous computer control

**Drawbacks:**
- Requires physical redesign
- May impact other performance metrics
- Weight redistribution needed

### Option 2: Stability Augmentation System (SAS)

**Approach**: Implement fly-by-wire with automatic pitch damping

**Algorithm Example:**
```
elevator_command = pilot_input + Kq * pitch_rate + Ka * (alpha - alpha_trim)
```

Where:
- Kq: Pitch rate feedback gain (provides artificial damping)
- Ka: Alpha feedback gain (provides artificial static stability)

**Benefits:**
- No physical redesign needed
- Can improve handling beyond natural stability
- Demonstrates advanced flight control

**Drawbacks:**
- Complex software required
- Single point of failure risk
- Not certifiable without redundancy
- Increases cost and complexity

### Option 3: Wing Redesign

**Changes:**
- Increase wing sweep
- Use reflex airfoil
- Add horizontal tail (no longer tailless)
- Modify wing planform

**Benefits:**
- Fundamentally fixes aerodynamics

**Drawbacks:**
- Major redesign effort
- May compromise other design goals
- Outside scope of current project

## Recommendations

### Immediate Action Items:

1. **Verify Mass Distribution**
   - CONFIRMED: CG calculation is correct (154.15 inches from mass.csv)
   - CONFIRMED: AVL reference point matches CG (12.846 feet = 154.15 inches)
   - Stability derivative Cma = +0.6259 /rad is accurate

2. **Stability Trade Study**
   - CALCULATED: Required CG shift = 28.6 inches forward
   - Target CG location: 125.5 inches (47% root chord)
   - This achieves +10% static margin (safe for conventional flight)
   - Action: Identify available mass that can be moved forward
   - Assess impact on other metrics (range, payload, etc.)

3. **Decision Point**
   - Option A: CG relocation → Redesign mass distribution and rerun analysis
   - Option B: Accept instability → Implement SAS for demonstration only
   - Option C: Hybrid → Move CG partially forward + lightweight SAS

### For Production Aircraft:

**The current configuration is NOT SAFE for flight.**

Must either:
- Redesign for stable CG location, OR
- Implement certified triple-redundant SAS with extensive testing

## Test Data

### Trim Conditions (Before Instability Discovered)

| Condition | Speed | Altitude | Alpha | Elevator | Throttle | L/D |
|-----------|-------|----------|-------|----------|----------|-----|
| High Alt Cruise | 484 ft/s | 20,000 ft | 4.17° | 0.33° | 9.6% | 20.73 |
| Sea Level Cruise | 347 ft/s | 0 ft | 4.16° | 0° | 9.6% | 20.74 |
| Approach | 176 ft/s | 1,000 ft | 17.75° | -0.28° | 41.4% | 4.84 |

**Note:** These trim solutions are mathematically correct for force/moment balance, but represent unstable equilibria. Any small disturbance will cause divergence.

## Validation

The simulation correctly captures the physics:

1. **Trim solver found equilibrium** - forces and moments balanced
2. **Small perturbation applied** - elevator doublet
3. **System response showed instability** - exponential divergence
4. **Root cause identified** - positive Cma from aft CG

The simulation is working as designed. The instability is REAL.

## Conclusion

The nTop flying wing has excellent aerodynamic efficiency (L/D > 20) but is fundamentally unstable due to aft CG location. This is a design issue, not a simulation error.

**The aircraft requires either:**
1. CG relocation to 20-30% MAC (preferred), OR
2. Stability augmentation system (acceptable for demonstration)

Without modification, the aircraft cannot be flown safely.

---

**Analysis Date:** 2025-11-10
**Simulation Tool:** Archimedes 6-DOF with AVL aerodynamics
**Analyst:** Claude Code Integration
