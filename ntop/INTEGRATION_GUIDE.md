# nTop + AVL + XFOIL Integration Guide

Complete step-by-step guide for integrating nTop wing geometry with AVL/XFOIL aerodynamic analysis and Archimedes 6-DOF simulation.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Phase 1: Geometry Processing](#phase-1-geometry-processing)
3. [Phase 2: AVL Analysis](#phase-2-avl-analysis)
4. [Phase 3: XFOIL Analysis](#phase-3-xfoil-analysis)
5. [Phase 4: Aero Deck Generation](#phase-4-aero-deck-generation)
6. [Phase 5: Simulation](#phase-5-simulation)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Topics](#advanced-topics)

---

## Prerequisites

### Software Requirements

1. **Python 3.9+** with packages:
   - numpy
   - pandas
   - matplotlib (for plotting)

2. **Archimedes** (this repository)
   ```bash
   pip install -e .
   # or with UV:
   uv pip install -e .
   ```

3. **AVL** (Athena Vortex Lattice)
   - Download from: http://web.mit.edu/drela/Public/web/avl/
   - Ensure `avl` executable is in your PATH

4. **XFOIL** (optional, for viscous corrections)
   - Download from: https://web.mit.edu/drela/Public/web/xfoil/
   - Ensure `xfoil` executable is in your PATH

### Data Requirements

You need three CSV files exported from nTop:

- **LEpts.csv** - Leading edge points (x, y, z in inches)
- **TEpts.csv** - Trailing edge points (x, y, z in inches)
- **mass.csv** - Mass properties (mass, CG, inertia)

These should be in `ntop/data/` directory.

---

## Phase 1: Geometry Processing

### Step 1.1: Verify Data

Check that your CSV files are properly formatted:

```bash
python -c "from ntop.geometry import load_ntop_data; \
           wing, mass = load_ntop_data('ntop/data'); \
           print(wing.summary())"
```

Expected output:
```
Wing Geometry Summary
==================================================
Number of sections: 13
Wing span: 24.863 ft
Reference area: 206.319 ft²
Mean aerodynamic chord: 8.298 ft
Aspect ratio: 2.996
...
```

### Step 1.2: Generate AVL Files

```bash
python ntop/avl_interface.py
```

This creates in `ntop/data/generated/`:
- `ntop_wing.avl` - Geometry file
- `ntop_wing.mass` - Mass properties file
- `ntop_runs.run` - Run cases file

### Step 1.3: Inspect Generated Files

Open `ntop_wing.avl` to verify:
- Reference geometry (Sref, Cref, Bref)
- CG location
- Wing sections are correctly positioned

---

## Phase 2: AVL Analysis

### Step 2.1: Launch AVL

```bash
cd ntop/data/generated
avl
```

### Step 2.2: Load Geometry

In AVL:
```
LOAD ntop_wing.avl
```

Press ENTER to accept defaults.

### Step 2.3: Load Mass Properties

```
MASS ntop_wing.mass
```

### Step 2.4: Enter OPER Menu

```
OPER
```

### Step 2.5: Run Alpha Sweep

Set parameters:
```
A                    # Set alpha
A 5.0                # Set alpha = 5 degrees
X                    # eXecute
```

View results:
```
ST                   # Stability derivatives
```

### Step 2.6: Export Data

To save results for multiple alphas:

1. Create run file with alpha sweep
2. Use batch mode:
   ```
   OPER
   RUN 1            # Run case 1
   ST
   filename.txt     # Save stability derivatives
   ```

Repeat for all alpha values in range [-10, 45] degrees.

### Step 2.7: Parse AVL Output

Modify `avl_interface.py._parse_avl_results()` to extract:

- **Stability derivatives**:
  - CLα, CDα, Cmα (longitudinal)
  - Clβ, Cnβ (lateral)
  - CLq, Cmq, CLα_dot, Cmα_dot (pitch rate)
  - Clp, Cnr (roll/yaw damping)
  - Clr, Cnp (cross-coupling)

- **Control derivatives**:
  - CLδe, Cmδe (elevator)
  - Clδa, Cnδa (aileron)
  - Cyδr, Cnδr (rudder)

---

## Phase 3: XFOIL Analysis

### Step 3.1: Extract Airfoil Sections

If you have actual airfoil coordinates from nTop CAD:

1. Export airfoil coordinates at representative stations
2. Save as `.dat` files in XFOIL format:
   ```
   Airfoil Name
   x1  y1
   x2  y2
   ...
   ```

If not available, the code uses NACA 0012 as placeholder.

### Step 3.2: Run XFOIL Manually

```bash
xfoil
```

In XFOIL:
```
LOAD airfoil.dat
PANE
OPER
VISC 10e6          # Set Reynolds number
MACH 0.5           # Set Mach number
PACC               # Polar accumulation
polar.txt          # Output file
                   # (blank for dump file)
ASEQ -10 25 0.5    # Alpha sequence: -10 to 25 by 0.5 deg
PACC               # End accumulation
QUIT
```

Repeat for multiple Reynolds numbers:
- 2e6 (low speed)
- 5e6 (cruise)
- 10e6 (high speed)
- 15e6 (max performance)

### Step 3.3: Parse XFOIL Output

The polar file format:
```
Alpha    CL       CD     CDp     CM    ...
-10.0   -0.850   0.0180 0.0080  0.050
-9.5    -0.805   0.0175 0.0078  0.048
...
```

Use `xfoil_interface.py._parse_xfoil_polar()` to extract data.

---

## Phase 4: Aero Deck Generation

### Step 4.1: Combine AVL and XFOIL Data

Implement `AeroDeck.from_avl_xfoil()`:

```python
def from_avl_xfoil(cls, avl_file, xfoil_file):
    # Load AVL data
    avl_df = pd.read_csv(avl_file)

    # Load XFOIL data
    xfoil_df = pd.read_csv(xfoil_file)

    # Combine:
    # CD_total = CD_induced(AVL) + CD_profile(XFOIL)
    # CL = AVL (3D effects)
    # Cm = blend AVL and XFOIL

    # Create interpolated tables
    ...

    return cls(...)
```

### Step 4.2: Generate Aero Deck

```bash
python ntop/aero_deck.py
```

For now, this creates a placeholder deck. Once AVL/XFOIL data is available:

```python
from ntop import AeroDeck

aero_deck = AeroDeck.from_avl_xfoil(
    avl_file="ntop/data/generated/avl_results.csv",
    xfoil_file="ntop/data/generated/xfoil_summary.csv"
)

aero_deck.save("ntop/data/generated/ntop_aero_deck.npz")
```

### Step 4.3: Verify Aero Deck

Check coefficients are reasonable:

```python
import numpy as np
from ntop import AeroDeck

deck = AeroDeck.load("ntop/data/generated/ntop_aero_deck.npz")

# Check CL vs alpha
alpha_deg = deck.alpha_vector
CL = -deck.cz_data  # CL = -Cz in body frame

import matplotlib.pyplot as plt
plt.plot(alpha_deg, CL)
plt.xlabel("Alpha [deg]")
plt.ylabel("CL")
plt.grid()
plt.show()
```

Expected:
- Linear region up to ~15° with CLα ≈ 0.08/deg
- Stall beyond 15-20°
- CLmax ≈ 1.0-1.5

---

## Phase 5: Simulation

### Step 5.1: Create Vehicle

```python
from pathlib import Path
from ntop import NTopVehicle

data_dir = Path("ntop/data")
vehicle = NTopVehicle.from_ntop_data(
    data_dir,
    max_thrust=2000.0  # lbf
)
```

### Step 5.2: Set Initial Conditions

```python
from ntop import CRUISE, create_initial_state

initial_state = create_initial_state(
    vehicle,
    CRUISE,
    alpha_deg=3.0,
    heading_deg=0.0
)
```

### Step 5.3: Define Controls

```python
controls = vehicle.Input(
    throttle=0.5,      # 50% throttle
    elevator=0.0,      # deg
    aileron=0.0,       # deg
    rudder=0.0,        # deg
)
```

### Step 5.4: Run Simulation

```python
from ntop import simulate_flight, analyze_flight_data

t_array, states = simulate_flight(
    vehicle,
    initial_state,
    controls,
    t_span=(0.0, 60.0),
    dt=0.1
)

flight_data = analyze_flight_data(vehicle, t_array, states)
```

### Step 5.5: Analyze Results

```python
from ntop.simulate import print_flight_summary

print_flight_summary(flight_data)
```

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'archimedes'"

**Solution**: Install Archimedes:
```bash
pip install -e .
```

### Issue: AVL files not generating

**Solution**: Check that CSV files exist in `ntop/data/`:
```bash
ls ntop/data/*.csv
```

### Issue: AVL crashes or gives errors

**Solution**:
1. Check AVL file manually - open in text editor
2. Verify coordinates are reasonable (not NaN or extremely large)
3. Check that wing sections progress smoothly in span

### Issue: Simulation diverges

**Solutions**:
1. Check initial conditions are trim-like
2. Verify control deflections are reasonable
3. Check aero coefficients for sign errors
4. Reduce time step (dt)
5. Check mass properties units

### Issue: Unrealistic aero coefficients

**Solutions**:
1. Verify AVL geometry is correct
2. Check that reference parameters (Sref, cref, bref) are correct
3. Run AVL manually to verify results
4. Check coordinate system conventions

---

## Advanced Topics

### Custom Airfoil Shapes

To use actual nTop airfoil coordinates:

1. Export airfoil sections from nTop CAD at multiple span stations
2. Save as `.dat` files
3. Modify `geometry.py.extract_airfoil_coordinates()`:
   ```python
   def extract_airfoil_coordinates(self, section, n_points=100):
       # Load actual airfoil data
       airfoil_file = f"airfoils/section_{section.y_station:.2f}.dat"
       coords = np.loadtxt(airfoil_file, skiprows=1)
       return coords
   ```

### Control Surface Modeling

Add control surface hinges in AVL:

```
SECTION
...

CONTROL
#name   gain  Xhinge  HingeVec    SgnDup
elevator 1.0  0.75    0 1 0       1
```

### Trim Calculation

Implement trim solver:

```python
def trim_vehicle(vehicle, altitude, velocity, flight_path_angle=0):
    """Find trim state and controls."""
    import archimedes as arc

    def trim_residual(z):
        # z = [alpha, elevator, throttle]
        # Compute forces and moments
        # Return residual [Fz, M, Fx]
        ...

    z_trim = arc.root(trim_residual, z0=[5.0, 0.0, 0.5])
    return z_trim
```

### Dynamic Stability Analysis

Extract eigenvalues from linearized dynamics:

```python
def compute_stability_modes(vehicle, trim_state):
    # Linearize dynamics
    A = arc.jacobian(lambda x: vehicle.dynamics(0, x, trim_input), trim_state)

    # Compute eigenvalues
    eigenvalues, eigenvectors = np.linalg.eig(A)

    # Identify modes: phugoid, short period, dutch roll, roll, spiral
    ...
```

### Code Generation for Embedded

Generate C code for deployment:

```python
import archimedes as arc

# Create template state and input
x_template = vehicle.State(...)
u_template = vehicle.Input(...)

# Generate C code
arc.codegen(
    vehicle.dynamics,
    (x_template, u_template),
    return_names=("x_dot",),
    output_dir="generated_c"
)
```

---

## Summary Checklist

- [ ] nTop CSV files exported and in `ntop/data/`
- [ ] Archimedes installed
- [ ] AVL and XFOIL executables available
- [ ] Geometry processing verified
- [ ] AVL files generated
- [ ] AVL analysis completed
- [ ] XFOIL polars generated (optional)
- [ ] Aero deck created
- [ ] Vehicle model initialized
- [ ] Simulation runs successfully
- [ ] Results analyzed and validated

---

## Next Steps

1. **Validate against wind tunnel data** (if available)
2. **Tune aerodynamic model** based on flight test
3. **Implement control laws** (autopilot, stability augmentation)
4. **Add actuator dynamics** (rate limits, delays)
5. **Generate C code** for hardware deployment
6. **Run Monte Carlo** simulations for robustness

For questions, see [README.md](README.md) or Archimedes documentation.
