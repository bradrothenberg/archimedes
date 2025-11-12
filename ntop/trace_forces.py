#!/usr/bin/env python
"""Trace force computation in detail."""

import numpy as np
from pathlib import Path

from geometry import WingGeometry, MassProperties
from aero_deck import AeroDeck
from ntop_aero import NTopAero, NTopAeroInput, NTopAeroState, FlightCondition
from ntop_vehicle import NTopVehicle, NTopVehicleGeometry
from archimedes.experimental.aero import ConstantGravity
from archimedes.experimental.aero.atmosphere_us import StandardAtmosphere1976

# Load data
data_dir = Path(__file__).parent / "data"
wing = WingGeometry.from_csv(data_dir / "LEpts.csv", data_dir / "TEpts.csv")
mass_props = MassProperties.from_csv(data_dir / "mass.csv")
aero_deck = AeroDeck.load(data_dir / "generated" / "ntop_aero_deck.npz")

# Create aero model
aero = NTopAero(aero_deck, wing)

# Flight condition
V = 484.0  # ft/s
altitude = 20000.0  # ft
alpha = np.deg2rad(4.17)

# Atmospheric conditions
atmos = StandardAtmosphere1976()
mach, qbar = atmos(V, altitude)

print("="*70)
print("FORCE TRACE")
print("="*70)

print(f"\nFlight condition:")
print(f"  V = {V:.1f} ft/s")
print(f"  h = {altitude:.0f} ft")
print(f"  alpha = {np.rad2deg(alpha):.2f} deg")
print(f"  mach = {mach:.3f}")
print(f"  qbar = {qbar:.2f} lbf/ft^2")

# Create aero input
aero_input = NTopAeroInput(
    condition=FlightCondition(
        alt=altitude,
        vt=V,
        alpha=alpha,
        beta=0.0,
        mach=mach,
        qbar=qbar,
    ),
    w_B=np.array([0.0, 0.0, 0.0]),
    elevator=0.33,
    aileron=0.0,
    rudder=0.0,
    xcg=0.25,
)

# Get aero output
state = NTopAeroState()
output = aero.output(0.0, state, aero_input)

print(f"\nAero coefficients:")
print(f"  Cx = {output.CF_B[0]:.6f}")
print(f"  Cy = {output.CF_B[1]:.6f}")
print(f"  Cz = {output.CF_B[2]:.6f}")
print(f"  Cl = {output.CM_B[0]:.6f}")
print(f"  Cm = {output.CM_B[1]:.6f}")
print(f"  Cn = {output.CM_B[2]:.6f}")

# Convert to forces
S = wing.reference_area
b = wing.span
cbar = wing.mean_chord

F_aero_x = qbar * S * output.CF_B[0]
F_aero_y = qbar * S * output.CF_B[1]
F_aero_z = qbar * S * output.CF_B[2]

M_aero_l = qbar * S * b * output.CM_B[0]
M_aero_m = qbar * S * cbar * output.CM_B[1]
M_aero_n = qbar * S * b * output.CM_B[2]

print(f"\nAero forces [lbf]:")
print(f"  Fx = {F_aero_x:.2f}")
print(f"  Fy = {F_aero_y:.2f}")
print(f"  Fz = {F_aero_z:.2f}")
print(f"  |F_aero| = {np.sqrt(F_aero_x**2 + F_aero_y**2 + F_aero_z**2):.2f}")

print(f"\nAero moments [ft-lbf]:")
print(f"  L = {M_aero_l:.2f}")
print(f"  M = {M_aero_m:.2f}")
print(f"  N = {M_aero_n:.2f}")

# Thrust
thrust = 0.096 * 3600
F_eng_x = thrust
print(f"\nEngine thrust [lbf]:")
print(f"  Fx = {F_eng_x:.2f}")

# Gravity (need to transform to body frame)
weight = mass_props.mass * 32.174  # lbf
theta = alpha  # Level flight
R_IB = np.array([
    [np.cos(theta), 0, np.sin(theta)],
    [0, 1, 0],
    [-np.sin(theta), 0, np.cos(theta)]
])
F_grav_I = np.array([0, 0, weight])  # Down in inertial frame
F_grav_B = R_IB.T @ F_grav_I

print(f"\nGravity force [lbf]:")
print(f"  Weight = {weight:.1f}")
print(f"  Fx = {F_grav_B[0]:.2f}")
print(f"  Fy = {F_grav_B[1]:.2f}")
print(f"  Fz = {F_grav_B[2]:.2f}")

# Total forces
F_total_x = F_aero_x + F_eng_x + F_grav_B[0]
F_total_y = F_aero_y + F_grav_B[1]
F_total_z = F_aero_z + F_grav_B[2]

print(f"\nTotal forces [lbf]:")
print(f"  Fx = {F_total_x:.2f}")
print(f"  Fy = {F_total_y:.2f}")
print(f"  Fz = {F_total_z:.2f}")

# Accelerations (F = ma)
mass_slug = mass_props.mass
ax = F_total_x / mass_slug
ay = F_total_y / mass_slug
az = F_total_z / mass_slug

print(f"\nAccelerations [ft/s^2]:")
print(f"  ax = {ax:.2f}")
print(f"  ay = {ay:.2f}")
print(f"  az = {az:.2f}")

# Pitch acceleration (M = I*alpha)
Iyy = mass_props.inertia[1,1]  # slug-ft^2
q_dot = M_aero_m / Iyy

print(f"\nPitch:")
print(f"  Iyy = {Iyy:.2f} slug-ft^2")
print(f"  M = {M_aero_m:.2f} ft-lbf")
print(f"  q_dot = {q_dot:.2f} rad/s^2")

print("\n" + "="*70)
if abs(az) > 100:
    print("[ERROR] Normal acceleration is huge!")
    print(f"  az = {az:.1f} ft/s^2 = {az/32.174:.1f} g")
    print(f"  This suggests a problem with:")
    print(f"    - Sign conventions")
    print(f"    - Cz sign (should be negative for positive lift)")
    print(f"    - Coordinate frame transformations")
if abs(q_dot) > 10:
    print("[ERROR] Pitch acceleration is huge!")
    print(f"  q_dot = {q_dot:.1f} rad/s^2")
print("="*70)
