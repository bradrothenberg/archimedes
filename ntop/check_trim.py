#!/usr/bin/env python
"""Check if hardcoded trim condition is actually trimmed."""

import numpy as np
from pathlib import Path

from run_ntop_sim import create_vehicle, create_trim_state

# Create vehicle
data_dir = Path(__file__).parent / "data"
vehicle = create_vehicle(data_dir, max_thrust=3600.0)

# Hardcoded trim from run_ntop_sim.py
velocity = 484.0  # ft/s
altitude = 20000.0  # ft
alpha_trim = np.deg2rad(4.17)  # rad
elevator_trim = 0.33  # deg
throttle_trim = 0.096  # 0-1

print("="*70)
print("TRIM CONDITION VERIFICATION")
print("="*70)

print(f"\nHardcoded trim values:")
print(f"  Velocity: {velocity:.1f} ft/s")
print(f"  Altitude: {altitude:.0f} ft")
print(f"  Alpha: {np.rad2deg(alpha_trim):.2f} deg")
print(f"  Elevator: {elevator_trim:.2f} deg")
print(f"  Throttle: {throttle_trim:.3f}")

# Create trim state
state = create_trim_state(vehicle, velocity, altitude, alpha_trim)

# Create trim control input
ctrl = vehicle.Input(
    throttle=throttle_trim,
    elevator=elevator_trim,
    aileron=0.0,
    rudder=0.0,
)

# Compute state derivative
xdot = vehicle.dynamics(0.0, state, ctrl)

print(f"\nState derivatives (should all be near zero for trim):")
print(f"  d(vel)/dt   = {xdot.v_B}")
print(f"  d(omega)/dt = {xdot.w_B}")

# Check if trimmed
vel_accel_mag = np.linalg.norm(xdot.v_B)
ang_accel_mag = np.linalg.norm(xdot.w_B)

print(f"\nTrim check:")
print(f"  |d(vel)/dt|   = {vel_accel_mag:.4f} ft/s^2")
print(f"  |d(omega)/dt| = {ang_accel_mag:.4f} rad/s^2")

# For a 100 lb aircraft
weight = vehicle.m * 32.174  # slug * ft/s^2 = lbf
print(f"  Weight = {weight:.1f} lbf")

# Acceleration tolerance (expect < 1 ft/s^2 for good trim)
if vel_accel_mag < 1.0:
    print(f"  [OK] Linear acceleration < 1 ft/s^2")
else:
    print(f"  [ERROR] Linear acceleration = {vel_accel_mag:.2f} ft/s^2 - NOT TRIMMED!")

if ang_accel_mag < 0.1:
    print(f"  [OK] Angular acceleration < 0.1 rad/s^2")
else:
    print(f"  [WARNING] Angular acceleration = {ang_accel_mag:.2f} rad/s^2 - may not be trimmed!")

# Check individual components
print(f"\nLinear acceleration components [ft/s^2]:")
print(f"  ax (axial)  = {xdot.v_B[0]:8.4f}  (should be ~0 for trim)")
print(f"  ay (side)   = {xdot.v_B[1]:8.4f}  (should be ~0)")
print(f"  az (normal) = {xdot.v_B[2]:8.4f}  (should be ~0 for level flight)")

print(f"\nAngular acceleration components [rad/s^2]:")
print(f"  p_dot (roll)  = {xdot.w_B[0]:8.4f}  (should be ~0)")
print(f"  q_dot (pitch) = {xdot.w_B[1]:8.4f}  (should be ~0 for trimmed pitch)")
print(f"  r_dot (yaw)   = {xdot.w_B[2]:8.4f}  (should be ~0)")

print("\n" + "="*70)
if vel_accel_mag < 1.0 and ang_accel_mag < 0.1:
    print("RESULT: Condition appears to be TRIMMED")
else:
    print("RESULT: Condition is NOT TRIMMED - this explains the divergence!")
    print("\nThe simulation starts with unbalanced forces/moments,")
    print("causing immediate departure from the intended flight path.")
print("="*70)
