# Simple test - just evaluate dynamics at one point
from pathlib import Path
import numpy as np

from ntop_vehicle import NTopVehicle
from simulate import CRUISE, create_initial_state

# Load vehicle
data_dir = Path(__file__).parent / "data"
print("Loading vehicle...")
vehicle = NTopVehicle.from_ntop_data(data_dir, max_thrust=2000.0)

print("\nVehicle loaded successfully!")

# Create initial state
print(f"\nSetting up {CRUISE.name} flight...")
initial_state = create_initial_state(vehicle, CRUISE, alpha_deg=3.0)

print(f"\nInitial state:")
print(f"  Position: {initial_state.pos}")
print(f"  Velocity (body): {initial_state.v_B}")
print(f"  Angular rates: {initial_state.w_B}")

# Define controls
controls = vehicle.Input(
    throttle=0.5,
    elevator=0.0,
    aileron=0.0,
    rudder=0.0,
)

# Evaluate dynamics at t=0
print(f"\nEvaluating dynamics at t=0...")
x_dot = vehicle.dynamics(0.0, initial_state, controls)

print(f"\nState derivatives:")
print(f"  Position rate: {x_dot.pos}")
print(f"  Velocity rate (body): {x_dot.v_B}")
print(f"  Angular accel: {x_dot.w_B}")

# Get flight condition
condition = vehicle.flight_condition(initial_state)
print(f"\nFlight condition:")
print(f"  Altitude: {condition.alt:.1f} ft")
print(f"  True airspeed: {condition.vt:.1f} ft/s")
print(f"  Alpha: {np.rad2deg(condition.alpha):.2f} deg")
print(f"  Beta: {np.rad2deg(condition.beta):.2f} deg")
print(f"  Mach: {condition.mach:.3f}")
print(f"  Q-bar: {condition.qbar:.1f} lbf/ft²")

print("\n" + "="*60)
print("SUCCESS! Dynamics evaluation works.")
print("="*60)
print("\nNote: For actual flight simulation, you need:")
print("  1. Run AVL to get real aerodynamic data")
print("  2. Update aero_deck with AVL results")
print("  3. Find trim conditions for stable flight")
