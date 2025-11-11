# AVL Analysis Files for nTop Flying Wing

This directory contains AVL input files ready to run in AVL (Athena Vortex Lattice).

## Files

- **uav.avl** - Geometry definition file
- **uav.mass** - Mass and inertia properties
- **uav.run** - Run cases (cruise conditions)

## Aircraft Summary

**Geometry:**
- Configuration: Flying wing (no tail)
- Span: 24.86 ft (298.4 inches)
- Root chord: 268.8 inches (22.4 ft)
- Tip chord: 2.9 inches (0.24 ft)
- Taper ratio: 0.011
- Leading edge sweep: 55.9°
- Quarter-chord sweep: 45.9°
- Reference area: 206.3 ft²
- Mean aerodynamic chord: 8.30 ft (99.6 inches)
- Aspect ratio: 3.0
- Airfoil: NACA 0012 (symmetric)

**Mass Properties:**
- Mass: 228.92 slugs (7365 lbm)
- Weight: 7365 lbf
- CG location: (12.846, -0.001, 0.044) feet
- CG location: (154.15, -0.01, 0.52) inches
- Ixx: 89,122,815 slug-ft²
- Iyy: 10,429,089 slug-ft²
- Izz: 99,551,904 slug-ft²

**Flight Condition (Cruise):**
- Altitude: 20,000 ft
- Velocity: 484 ft/s (287 KTAS, Mach 0.44)
- Density: 0.001267 slug/ft³
- Trim alpha: 4.17°
- Target CL: 0.244

## Stability Analysis Results

**CRITICAL FINDING: Aircraft is statically UNSTABLE**

From AVL analysis:
- Cma = +0.626 /rad at CG (POSITIVE = unstable)
- CLa = 3.341 /rad
- Static Margin = -18.7% MAC (NEGATIVE = unstable)

**Neutral Point Location:**
- Neutral point: 135.5 inches (50.4% root chord)
- CG location: 154.2 inches (57.3% root chord)
- **CG is 18.7 inches (18.7% MAC) AFT of neutral point**

This configuration is **unflyable without stability augmentation system (SAS)**.

## Why is the Neutral Point so Far Aft?

The neutral point at 50% chord is unusually far aft due to:

1. **Extreme sweep angle** (56° LE, 46° QC) - sweep pushes NP aft significantly
2. **Symmetric airfoil** (NACA 0012) - provides no camber-induced pitch stability
3. **Flying wing configuration** - no tail to provide restoring moment
4. **High taper ratio** (0.011) - almost delta wing planform

## Solutions

### Option 1: Relocate CG Forward (RECOMMENDED)
- Required CG shift: **28.6 inches forward**
- Target CG: 125.5 inches (47% root chord)
- This achieves +10% static margin (conventionally stable)

### Option 2: Stability Augmentation System (SAS)
- Implement fly-by-wire with pitch rate feedback
- Requires redundant sensors and actuators
- Aircraft remains inherently unstable but computer maintains control

### Option 3: Wing Redesign
- Add reflex to airfoil trailing edge
- Increase washout (twist)
- Reduce sweep angle
- May compromise performance

## How to Use in AVL

1. Start AVL:
   ```
   avl
   ```

2. Load geometry:
   ```
   LOAD uav.avl
   ```

3. Load mass properties:
   ```
   MASS uav.mass
   ```

4. Load run case:
   ```
   CASE uav.run
   ```

5. Run analysis:
   ```
   OPER
   X     (execute run case)
   ```

6. View stability derivatives:
   ```
   ST    (stability derivatives)
   ```

7. Mode analysis:
   ```
   MODE  (eigenmode analysis)
   ```

## Key AVL Commands

- `LOAD` - Load geometry file
- `MASS` - Load mass properties
- `CASE` - Load run cases
- `OPER` - Enter operating point menu
- `X` - Execute current run case
- `ST` - Show stability derivatives
- `FT` - Show total forces
- `MODE` - Dynamic stability eigenmode analysis
- `QUIT` - Exit AVL

## Expected Observations in AVL

When you run this in AVL, you should observe:

1. **Positive Cma** - Pitch stiffness derivative is positive (unstable)
2. **Negative static margin** - CG is aft of neutral point
3. **Unstable short period mode** - Positive real eigenvalue in mode analysis
4. **Cm vs alpha slope** - Positive slope indicates divergent pitch behavior

## References

- AVL User Guide: http://web.mit.edu/drela/Public/web/avl/
- Planform visualization: `../output/ntop_planform.png`
- Stability analysis report: `../STABILITY_ANALYSIS.md`
- Simulation results: `../output/ntop_elevator_doublet.png`
