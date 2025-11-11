# nTop Vehicle Simulation Plan - F-16 Style

Complete plan to run full 6-DOF simulations like the F-16 example in Archimedes.

## Overview

Create a complete flight simulation framework including:
1. Full aerodynamic database from AVL
2. Trim solver for equilibrium conditions
3. Multiple flight scenarios (doublets, maneuvers)
4. Analysis and visualization

## Phase 1: Complete AVL Analysis (30-60 minutes)

### 1.1 Alpha Sweep
**Goal:** Get aerodynamic coefficients across full angle of attack range

**Alpha range:** -10° to 45° (12-24 points)
**Beta:** 0° (symmetric flight)

**Coefficients to extract:**
- CL, CD, Cm (longitudinal)
- Stability derivatives: CLα, CDα, Cmα, CLq, Cmq

**Implementation:**
```python
# Create alpha sweep script
alpha_values = np.linspace(-10, 45, 24)
for alpha in alpha_values:
    run_avl(alpha=alpha, beta=0)
    extract_coefficients()
```

**AVL Commands:**
```
LOAD ntop_wing.avl
MASS ntop_wing.mass
OPER
A
A {alpha}
X
ST
st_alpha_{alpha}.txt

```

### 1.2 Beta Sweep
**Goal:** Get lateral-directional derivatives

**Beta range:** -30° to 30° (7-13 points)
**Alpha:** 0°, 5°, 10° (representative conditions)

**Coefficients to extract:**
- CY, Cl, Cn (lateral-directional)
- Stability derivatives: CYβ, Clβ, Cnβ, Clp, Cnr, Clr, Cnp

### 1.3 Control Surface Effectiveness
**Goal:** Get control derivatives

**Deflections to test:**
- Elevator: -24° to 24°
- Aileron: -20° to 20°
- Rudder: -30° to 30°

**Derivatives to extract:**
- CLδe, Cmδe (elevator)
- Clδa, Cnδa (aileron)
- CYδr, Cnδr (rudder)

## Phase 2: AVL Output Parsing (1-2 hours)

### 2.1 Parse Stability Derivatives File

**AVL "ST" output format:**
```
Stability-axis derivatives...

 CLa =   4.5678   per radian
 Cma =  -1.2345   per radian
 CLq =   8.9012   per radian
 Cmq = -12.3456   per radian
```

**Parser implementation:**
```python
def parse_avl_stability_output(filename):
    """Parse AVL ST output file."""
    derivatives = {}

    with open(filename, 'r') as f:
        for line in f:
            # Parse lines like: " CLa =   4.5678   per radian"
            if '=' in line:
                parts = line.split('=')
                key = parts[0].strip()
                value = float(parts[1].split()[0])
                derivatives[key] = value

    return derivatives
```

### 2.2 Parse Total Forces File

**AVL "FT" output format:**
```
CLtot =   0.29246
CDtot =   0.00898
Cmtot =   0.05577
```

**Already working** - see `ntop/data/generated/avl_ft.txt`

### 2.3 Create Structured Database

**Output format:** CSV or NPZ with complete aero data
```python
{
    'alpha': [...],           # Angle of attack array
    'beta': [...],            # Sideslip angle array
    'CL': [...],              # Lift coefficient
    'CD': [...],              # Drag coefficient
    'Cm': [...],              # Pitch moment
    'CY': [...],              # Side force
    'Cl': [...],              # Roll moment
    'Cn': [...],              # Yaw moment
    'CLa': [...],             # Stability derivatives
    'Cma': [...],
    # ... etc
}
```

## Phase 3: Update Aero Deck (1-2 hours)

### 3.1 Implement from_avl_data()

**File:** `ntop/aero_deck.py`

```python
@classmethod
def from_avl_data(cls, avl_data_file: Path) -> AeroDeck:
    """Create aero deck from parsed AVL data."""

    # Load parsed AVL results
    data = pd.read_csv(avl_data_file)

    # Create interpolation axes
    alpha_vector = data['alpha'].unique()
    beta_vector = data['beta'].unique()

    # Build coefficient tables
    # CL, CD, Cm vs alpha
    # CY, Cl, Cn vs beta
    # Control derivatives

    # Create AeroDeck with real data
    return cls(
        alpha_vector=alpha_vector,
        beta_vector=beta_vector,
        cx_data=...,  # From AVL CD
        cz_data=...,  # From AVL CL
        cm_data=...,
        # etc
    )
```

### 3.2 Validate Aero Deck

**Checks:**
- [ ] CL increases linearly with alpha (up to stall)
- [ ] CLα ≈ 4-6 per radian (typical for this AR)
- [ ] Cm has right sign (pitch stability)
- [ ] Cmα < 0 (statically stable)
- [ ] CD increases with alpha²
- [ ] Span efficiency e ≈ 0.9-0.99

**Validation script:**
```python
def validate_aero_deck(deck):
    # Check CL vs alpha is monotonic
    assert np.all(np.diff(deck.cz_data) < 0)  # CZ = -CL

    # Check CLα magnitude
    CLa = np.gradient(-deck.cz_data, np.deg2rad(deck.alpha_vector))
    assert 4.0 < CLa[5] < 7.0  # At mid-range alpha

    # Check static stability
    Cma = np.gradient(deck.cm_data[:,2], np.deg2rad(deck.alpha_vector))
    assert np.all(Cma < 0)  # Statically stable
```

## Phase 4: Trim Solver (2-3 hours)

### 4.1 Implement Trim Function

**File:** `ntop/trim.py` (new file, based on F-16 example)

```python
def trim_vehicle(
    vehicle: NTopVehicle,
    altitude: float,
    velocity: float,
    flight_path_angle: float = 0.0,
    turn_rate: float = 0.0,
) -> TrimResult:
    """Find trim condition for specified flight condition.

    Args:
        vehicle: Vehicle model
        altitude: Altitude [ft]
        velocity: True airspeed [ft/s]
        flight_path_angle: Climb angle [deg]
        turn_rate: Turn rate [deg/s]

    Returns:
        TrimResult with trimmed state, controls, and residuals
    """

    # Define trim variables: [alpha, elevator, throttle]
    def trim_residual(z):
        alpha, elevator, throttle = z

        # Build state at trim
        state = create_state(
            altitude=altitude,
            velocity=velocity,
            alpha=alpha,
            gamma=flight_path_angle,
        )

        # Build controls
        controls = vehicle.Input(
            throttle=throttle,
            elevator=elevator,
            aileron=0.0,
            rudder=0.0,
        )

        # Evaluate dynamics
        x_dot = vehicle.dynamics(0.0, state, controls)

        # Trim requires zero accelerations
        residual = np.array([
            x_dot.v_B[2],  # Zero vertical acceleration (Fz = 0)
            x_dot.w_B[1],  # Zero pitch acceleration (M = 0)
            x_dot.v_B[0],  # Zero axial acceleration (Fx = 0)
        ])

        return residual

    # Initial guess
    z0 = np.array([
        5.0,   # alpha [deg]
        0.0,   # elevator [deg]
        0.5,   # throttle [0-1]
    ])

    # Solve
    z_trim = arc.root(trim_residual, z0)

    # Build trim result
    ...

    return TrimResult(...)
```

### 4.2 Trim Result Structure

```python
@struct
class TrimResult:
    """Trim solution."""
    state: NTopVehicle.State
    controls: NTopVehicle.Input
    alpha: float  # deg
    elevator: float  # deg
    throttle: float  # 0-1
    residual_norm: float
    converged: bool
```

### 4.3 Test Trim Solver

**Test conditions:**
```python
# Level flight cruise
trim_cruise = trim_vehicle(
    vehicle, altitude=20000, velocity=550, flight_path_angle=0
)

# Climb
trim_climb = trim_vehicle(
    vehicle, altitude=15000, velocity=450, flight_path_angle=5
)

# Descent
trim_descent = trim_vehicle(
    vehicle, altitude=10000, velocity=300, flight_path_angle=-3
)
```

## Phase 5: Simulation Scenarios (2-3 hours)

### 5.1 Doublet Inputs (like F-16 example)

**File:** `ntop/scenarios.py`

```python
def elevator_doublet(
    vehicle: NTopVehicle,
    trim_result: TrimResult,
    amplitude: float = 5.0,  # deg
    duration: float = 2.0,   # s
    t_sim: float = 60.0,     # s
):
    """Simulate elevator doublet response."""

    # Define control schedule
    def control_schedule(t):
        elevator = trim_result.controls.elevator
        if 5.0 < t < 5.0 + duration/2:
            elevator += amplitude
        elif 5.0 + duration/2 < t < 5.0 + duration:
            elevator -= amplitude

        return vehicle.Input(
            throttle=trim_result.controls.throttle,
            elevator=elevator,
            aileron=0.0,
            rudder=0.0,
        )

    # Simulate
    t_eval = np.linspace(0, t_sim, 600)
    states = simulate_with_schedule(vehicle, trim_result.state, control_schedule, t_eval)

    return t_eval, states
```

### 5.2 Other Scenarios

**Aileron roll:**
```python
def aileron_roll(vehicle, trim_result, rate=30):  # deg/s
    """Coordinated aileron roll."""
```

**Steady turn:**
```python
def steady_turn(vehicle, trim_result, turn_rate=3):  # deg/s
    """Coordinated turn at constant altitude."""
```

**Vertical climb:**
```python
def vertical_climb(vehicle, trim_result):
    """Transition to vertical climb."""
```

## Phase 6: Analysis & Visualization (2-3 hours)

### 6.1 Flight Data Analysis

**Extract key metrics:**
```python
def analyze_maneuver(t, states):
    """Analyze maneuver characteristics."""

    # Extract time histories
    altitude = [-s.pos[2] for s in states]
    velocity = [np.linalg.norm(s.v_B) for s in states]
    alpha = [np.arctan2(s.v_B[2], s.v_B[0]) for s in states]

    # Compute derived quantities
    load_factor = compute_load_factor(states)
    flight_path = compute_flight_path(states)

    # Find peaks, settling time, etc.
    metrics = {
        'peak_alpha': np.max(alpha),
        'peak_load_factor': np.max(load_factor),
        'settling_time': find_settling_time(alpha),
    }

    return metrics
```

### 6.2 Plotting (F-16 Style)

**File:** `ntop/plotting.py`

```python
def plot_doublet_response(t, states, metrics):
    """Create F-16-style doublet response plots."""

    fig, axes = plt.subplots(4, 2, figsize=(12, 10))

    # Altitude
    axes[0, 0].plot(t, altitude)
    axes[0, 0].set_ylabel('Altitude [ft]')

    # Velocity
    axes[0, 1].plot(t, velocity)
    axes[0, 1].set_ylabel('Velocity [ft/s]')

    # Alpha
    axes[1, 0].plot(t, alpha)
    axes[1, 0].set_ylabel('Alpha [deg]')
    axes[1, 0].axhline(metrics['peak_alpha'], ls='--', color='r')

    # Pitch rate
    axes[1, 1].plot(t, pitch_rate)
    axes[1, 1].set_ylabel('Pitch rate [deg/s]')

    # Elevator
    axes[2, 0].plot(t, elevator)
    axes[2, 0].set_ylabel('Elevator [deg]')

    # Pitch angle
    axes[2, 1].plot(t, pitch)
    axes[2, 1].set_ylabel('Pitch [deg]')

    # Load factor
    axes[3, 0].plot(t, load_factor)
    axes[3, 0].set_ylabel('Load factor [g]')

    # Flight path
    axes[3, 1].plot(t, flight_path)
    axes[3, 1].set_ylabel('Flight path [deg]')

    plt.tight_layout()
    return fig
```

### 6.3 3D Trajectory Visualization

```python
def plot_3d_trajectory(states):
    """Plot 3D flight path."""

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')

    # Extract positions
    x = [s.pos[0] for s in states]
    y = [s.pos[1] for s in states]
    z = [-s.pos[2] for s in states]  # Convert NED to altitude

    ax.plot(x, y, z)
    ax.set_xlabel('X [ft]')
    ax.set_ylabel('Y [ft]')
    ax.set_zlabel('Altitude [ft]')

    return fig
```

## Phase 7: Complete Example (1 hour)

### 7.1 Main Simulation Script

**File:** `ntop/run_f16_style_sim.py`

```python
#!/usr/bin/env python
"""Complete F-16-style simulation for nTop vehicle."""

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

from ntop_vehicle import NTopVehicle
from trim import trim_vehicle
from scenarios import elevator_doublet, aileron_roll
from plotting import plot_doublet_response, plot_3d_trajectory

def main():
    print("="*70)
    print("nTop Vehicle - F-16 Style Simulation")
    print("="*70)

    # Load vehicle with real AVL data
    data_dir = Path(__file__).parent / "data"
    vehicle = NTopVehicle.from_ntop_data(data_dir)

    print("\nVehicle loaded:")
    print(f"  Mass: {vehicle.m:.2f} slug")
    print(f"  Wing area: {vehicle.geometry.S:.2f} ft²")

    # Find trim condition
    print("\nFinding trim for cruise...")
    trim_cruise = trim_vehicle(
        vehicle,
        altitude=20000,
        velocity=550,
        flight_path_angle=0,
    )

    print(f"  Trimmed at alpha = {trim_cruise.alpha:.2f}°")
    print(f"  Elevator = {trim_cruise.elevator:.2f}°")
    print(f"  Throttle = {trim_cruise.throttle:.3f}")

    # Run elevator doublet
    print("\nRunning elevator doublet...")
    t, states = elevator_doublet(
        vehicle, trim_cruise, amplitude=5.0, duration=2.0, t_sim=30.0
    )

    # Analyze
    print("\nAnalyzing response...")
    metrics = analyze_maneuver(t, states)
    print(f"  Peak alpha: {metrics['peak_alpha']:.2f}°")
    print(f"  Peak load factor: {metrics['peak_load_factor']:.2f} g")
    print(f"  Settling time: {metrics['settling_time']:.1f} s")

    # Plot
    print("\nGenerating plots...")
    fig1 = plot_doublet_response(t, states, metrics)
    fig1.savefig('doublet_response.png', dpi=150)

    fig2 = plot_3d_trajectory(states)
    fig2.savefig('trajectory_3d.png', dpi=150)

    plt.show()

    print("\n" + "="*70)
    print("Simulation complete!")
    print("="*70)

if __name__ == "__main__":
    main()
```

## Timeline & Effort

**Total estimated time: 8-12 hours**

| Phase | Task | Time | Difficulty |
|-------|------|------|------------|
| 1 | AVL alpha/beta sweeps | 1-2h | Easy |
| 2 | Parse AVL output | 1-2h | Medium |
| 3 | Update aero deck | 1-2h | Medium |
| 4 | Implement trim solver | 2-3h | Hard |
| 5 | Create scenarios | 2-3h | Medium |
| 6 | Analysis & plotting | 2-3h | Easy |
| 7 | Integration & testing | 1h | Easy |

## Success Criteria

- [ ] AVL runs complete for alpha sweep
- [ ] All stability derivatives extracted
- [ ] Aero deck passes validation checks
- [ ] Trim solver converges for multiple conditions
- [ ] Elevator doublet shows reasonable response
- [ ] Plots match F-16 example quality
- [ ] Full simulation runs without errors

## Next Immediate Steps

1. **Start with AVL sweep** (easiest, most critical)
2. **Parse output** (enables everything else)
3. **Update aero deck** (critical path)
4. **Then trim solver** (blocks simulations)

Would you like me to start implementing any of these phases?
