#!/usr/bin/env python
"""Debug forces and moments computation."""

import numpy as np
from pathlib import Path

from run_ntop_sim import create_vehicle, create_trim_state

# Create vehicle
data_dir = Path(__file__).parent / "data"
vehicle = create_vehicle(data_dir, max_thrust=3600.0)

# Test condition
velocity = 484.0  # ft/s
altitude = 20000.0  # ft
alpha_trim = np.deg2rad(4.17)  # rad

state = create_trim_state(vehicle, velocity, altitude, alpha_trim)

# Test several elevator settings
print("="*70)
print("FORCES AND MOMENTS vs ELEVATOR")
print("="*70)

for elev in [-5, -2, 0, 0.33, 2, 5]:
    ctrl = vehicle.Input(
        throttle=0.096,
        elevator=elev,
        aileron=0.0,
        rudder=0.0,
    )

    xdot = vehicle.dynamics(0.0, state, ctrl)

    print(f"\nElevator = {elev:+5.2f} deg:")
    print(f"  q_dot (pitch accel) = {xdot.w_B[1]:10.4f} rad/s^2")
    print(f"  az (normal accel)   = {xdot.v_B[2]:10.4f} ft/s^2")

print("\n" + "="*70)
print("The elevator that produces q_dot ≈ 0 is the trim elevator")
print("="*70)
