#!/usr/bin/env python
"""Test that aero model produces stable pitch moment."""

import numpy as np
from pathlib import Path

from geometry import WingGeometry, MassProperties
from aero_deck import AeroDeck
from ntop_aero import NTopAero, NTopAeroInput, NTopAeroState, FlightCondition

# Load data
data_dir = Path(__file__).parent / "data"
wing = WingGeometry.from_csv(data_dir / "LEpts.csv", data_dir / "TEpts.csv")
aero_deck = AeroDeck.load(data_dir / "generated" / "ntop_aero_deck.npz")

# Create aero model
aero = NTopAero(aero_deck, wing)

print("="*70)
print("AERO MODEL STABILITY TEST")
print("="*70)

# Test at cruise condition
alpha_cruise = 4.35  # deg
V = 484.0  # ft/s
altitude = 20000.0  # ft

# Create test input at cruise
test_input = NTopAeroInput(
    condition=FlightCondition(
        alt=altitude,
        vt=V,
        alpha=np.deg2rad(alpha_cruise),
        beta=0.0,
        mach=0.5,
        qbar=150.0,
    ),
    w_B=np.array([0.0, 0.0, 0.0]),  # No rotation
    elevator=0.0,
    aileron=0.0,
    rudder=0.0,
    xcg=0.25,
)

# Get output
state = NTopAeroState()
output = aero.output(0.0, state, test_input)

print(f"\n1. AT CRUISE (alpha = {alpha_cruise} deg, V = {V} ft/s):")
print(f"   Force coefficients (Cx, Cy, Cz): {output.CF_B}")
print(f"   Moment coefficients (Cl, Cm, Cn): {output.CM_B}")
print(f"   Cm = {output.CM_B[1]:.6f}")

if abs(output.CM_B[1]) < 0.05:
    print(f"   [OK] Cm near zero at cruise")
else:
    print(f"   [WARNING] Cm not near zero - not trimmed!")

# Test stability: increase alpha slightly and check if Cm becomes more negative
alpha_pert = 4.85  # deg (+0.5 deg perturbation)
test_input_pert = test_input.replace(
    condition=test_input.condition.replace(alpha=np.deg2rad(alpha_pert))
)

output_pert = aero.output(0.0, state, test_input_pert)
Cm_pert = output_pert.CM_B[1]
dCm_dalpha = (Cm_pert - output.CM_B[1]) / np.deg2rad(alpha_pert - alpha_cruise)

print(f"\n2. STABILITY CHECK (perturb alpha by +0.5 deg):")
print(f"   Cm at {alpha_pert} deg: {Cm_pert:.6f}")
print(f"   dCm/dalpha = {dCm_dalpha:.6f} /rad")

if dCm_dalpha < 0:
    print(f"   [OK] Cma is NEGATIVE = STABLE (restoring moment)")
else:
    print(f"   [ERROR] Cma is POSITIVE = UNSTABLE (divergent moment)!")

# Test pitch rate damping
q_test = 0.1  # rad/s
test_input_q = test_input.replace(
    w_B=np.array([0.0, q_test, 0.0])
)

output_q = aero.output(0.0, state, test_input_q)
dCm_q = output_q.CM_B[1] - output.CM_B[1]
Cmq_effective = dCm_q / (wing.mean_chord * q_test / (2 * V))

print(f"\n3. PITCH DAMPING CHECK (q = {q_test} rad/s):")
print(f"   Cm with pitch rate: {output_q.CM_B[1]:.6f}")
print(f"   Delta Cm: {dCm_q:.6f}")
print(f"   Effective Cmq: {Cmq_effective:.6f} /rad")

if Cmq_effective < 0:
    print(f"   [OK] Cmq is NEGATIVE = DAMPED")
else:
    print(f"   [ERROR] Cmq is POSITIVE = UNDAMPED!")

# Test actual aero deck values
print(f"\n4. AERO DECK VALUES:")
alpha_vec = aero_deck.alpha_vector
idx = np.argmin(np.abs(alpha_vec - alpha_cruise))
print(f"   At alpha = {alpha_vec[idx]:.2f} deg:")
print(f"   Cm (neutral elev) = {aero_deck.cm_data[idx, 2]:.6f}")
print(f"   Cmq = {aero_deck.cmq_data[idx]:.6f} /rad")

# Compute numerical Cma from aero deck
if idx > 0 and idx < len(alpha_vec) - 1:
    dalpha = alpha_vec[1] - alpha_vec[0]
    dCm = (aero_deck.cm_data[idx+1, 2] - aero_deck.cm_data[idx-1, 2])
    Cma_deck = dCm / (2 * np.deg2rad(dalpha))
    print(f"   Cma (numerical) = {Cma_deck:.6f} /rad")

print("\n" + "="*70)
print("DIAGNOSIS")
print("="*70)

if dCm_dalpha < 0 and Cmq_effective < 0:
    print("\n[OK] Aero model shows STABLE characteristics:")
    print("     - Pitch stiffness is restoring (Cma < 0)")
    print("     - Pitch damping is present (Cmq < 0)")
    print("\nIf 6-DOF simulation still diverges, check:")
    print("     - Initial trim condition")
    print("     - Sign conventions in equations of motion")
    print("     - Moment arm calculations")
else:
    print("\n[ERROR] Aero model shows UNSTABLE characteristics!")
    print("        This explains the 6-DOF divergence.")
