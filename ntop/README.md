# nTop + AVL + XFOIL Integration with Archimedes 6-DOF Simulator

This directory contains the integration of nTop wing geometry with AVL (Athena Vortex Lattice) and XFOIL aerodynamic analysis tools, implemented within the Archimedes 6-DOF simulation framework.

## Overview

The integration pipeline:

1. **nTop Geometry Export** → Leading edge points, trailing edge points, and mass properties (CSV files)
2. **AVL Analysis** → 3D inviscid aerodynamics, stability derivatives
3. **XFOIL Analysis** → 2D viscous airfoil analysis, drag polars
4. **Aero Deck** → Combined aerodynamic database
5. **Archimedes Simulation** → Full 6-DOF flight dynamics

## Files

### Core Modules

- **`geometry.py`** - Loads and processes nTop CSV data (LEpts, TEpts, mass properties)
- **`avl_interface.py`** - Generates AVL input files and runs AVL analyses
- **`xfoil_interface.py`** - Generates XFOIL input and runs 2D airfoil analyses
- **`aero_deck.py`** - Combines AVL/XFOIL data into unified aerodynamic database
- **`ntop_aero.py`** - Custom aerodynamics model for Archimedes using aero deck
- **`ntop_vehicle.py`** - Complete vehicle configuration with mass/geometry/aero
- **`simulate.py`** - Simulation interface for various flight regimes

### Data Files

- **`data/LEpts.csv`** - Leading edge points from nTop (inches)
- **`data/TEpts.csv`** - Trailing edge points from nTop (inches)
- **`data/mass.csv`** - Mass properties from nTop (lbf, inches)
- **`data/generated/`** - Generated AVL/XFOIL input/output files

## Quick Start

### 1. Install Archimedes

From the repository root:

```bash
pip install -e .
```

Or with UV:

```bash
uv pip install -e .
```

### 2. Generate AVL Input Files

```bash
python ntop/avl_interface.py
```

This creates:
- `ntop/data/generated/ntop_wing.avl` - AVL geometry file
- `ntop/data/generated/ntop_wing.mass` - AVL mass properties file
- `ntop/data/generated/ntop_runs.run` - AVL run cases

### 3. Run AVL Analysis

```bash
cd ntop/data/generated
avl ntop_wing.avl
```

Within AVL:
```
LOAD ntop_wing.avl
MASS ntop_wing.mass
OPER
```

Then run alpha sweeps and save stability derivatives.

### 4. Run XFOIL Analysis (Optional)

For viscous corrections:

```bash
python ntop/xfoil_interface.py
```

This will generate airfoil polars at various Reynolds numbers.

### 5. Generate Aero Deck

```bash
python ntop/aero_deck.py
```

Creates `ntop/data/generated/ntop_aero_deck.npz` with all aerodynamic coefficients.

### 6. Run Simulation

```bash
python ntop/simulate.py
```

Or in Python:

```python
from pathlib import Path
from ntop.ntop_vehicle import NTopVehicle
from ntop.simulate import CRUISE, create_initial_state, simulate_flight

# Load vehicle
data_dir = Path("ntop/data")
vehicle = NTopVehicle.from_ntop_data(data_dir, max_thrust=2000.0)

# Create initial state for cruise
initial_state = create_initial_state(vehicle, CRUISE, alpha_deg=3.0)

# Define controls
controls = vehicle.Input(throttle=0.5, elevator=0.0, aileron=0.0, rudder=0.0)

# Simulate
t_array, states = simulate_flight(vehicle, initial_state, controls, t_span=(0, 30))
```

## Vehicle Configuration

### Geometry (from nTop)
- **Reference Area**: 206.3 ft²
- **Wing Span**: 24.9 ft
- **Mean Chord**: 8.3 ft
- **Aspect Ratio**: 3.0
- **Number of Sections**: 13

### Mass Properties (from nTop)
- **Mass**: 229 slug (7,365 lbf weight)
- **CG Location**: [12.85, -0.001, 0.044] ft
- **Inertia**:
  - Ixx: 19,239 slug·ft²
  - Iyy: 2,251 slug·ft²
  - Izz: 21,490 slug·ft²

## Flight Regimes

### Cruise
- Altitude: 20,000 ft
- Velocity: 550 ft/s (~Mach 0.5)
- Flight path angle: 0°

### Climb
- Altitude: 15,000 ft
- Velocity: 450 ft/s
- Flight path angle: +5°

### Landing
- Altitude: 500 ft
- Velocity: 200 ft/s
- Flight path angle: -3° (glide slope)

## Coordinate Systems

### nTop Export
- Units: inches (converted to feet)
- Frame: As exported from nTop

### AVL
- Right-handed coordinate system
- X: streamwise (forward)
- Y: spanwise (right wing positive)
- Z: vertical (up positive)

### Archimedes Body Frame
- Consistent with AVL convention
- X: forward, Y: right, Z: down (NED-aligned body frame)

## Aerodynamic Model

The aerodynamic model includes:

### Force Coefficients
- **Cx(α, δe)** - Axial force (drag-like)
- **Cy(β, δa, δr)** - Side force
- **Cz(α, δe)** - Normal force (lift-like)

### Moment Coefficients
- **Cl(α, β, δa, δr)** - Rolling moment
- **Cm(α, δe)** - Pitching moment
- **Cn(α, β, δa, δr)** - Yawing moment

### Damping Derivatives
- **Cxq, Czq, Cmq** - Pitch rate derivatives
- **Cyp, Clp, Cnp** - Roll rate derivatives
- **Cyr, Clr, Cnr** - Yaw rate derivatives

### Control Derivatives
- **dCl/dδa, dCn/dδa** - Aileron effectiveness
- **dCl/dδr, dCn/dδr** - Rudder effectiveness
- **dCx/dδe, dCz/dδe, dCm/dδe** - Elevator effectiveness

## Next Steps

### To Use Real AVL/XFOIL Data

1. Run AVL analyses as described above
2. Parse AVL output files (modify `avl_interface.py._parse_avl_results()`)
3. Run XFOIL for representative sections
4. Implement `AeroDeck.from_avl_xfoil()` to combine data
5. Regenerate aero deck

### To Add Control Surface Actuators

Follow the F-16 example:
```python
from archimedes import struct, field

@struct
class ActuatorConfig:
    rate_limit: float = 60.0  # deg/s
    position_limit: float = 25.0  # deg
```

### To Implement Trim

The vehicle can be trimmed for steady flight conditions:

```python
from ntop.trim import trim_vehicle

trim_result = trim_vehicle(
    vehicle=vehicle,
    altitude=20000.0,
    velocity=550.0,
    flight_path_angle=0.0,
)
```

## References

- **AVL**: [MIT AVL User Guide](http://web.mit.edu/drela/Public/web/avl/)
- **XFOIL**: [XFOIL Documentation](https://web.mit.edu/drela/Public/web/xfoil/)
- **Archimedes**: [Documentation](https://pinetreelabs.github.io/archimedes/)

## Notes

- Current implementation uses NACA 0012 placeholder airfoils
- To use actual nTop airfoil shapes, extract section coordinates from CAD
- AVL output parsing needs to be customized based on actual AVL output format
- XFOIL integration can be extended for more detailed viscous analysis

## Contact

For questions about this integration, refer to the Archimedes documentation or the nTop technical team.
