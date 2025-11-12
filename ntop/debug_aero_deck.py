#!/usr/bin/env python
"""Debug aero deck to understand 6-DOF instability."""

import numpy as np
from pathlib import Path

# Load aero deck
data_file = Path(__file__).parent / "data" / "generated" / "ntop_aero_deck.npz"
data = np.load(data_file)

print("="*70)
print("AERO DECK ANALYSIS")
print("="*70)

print("\n1. DATA STRUCTURE:")
print(f"   Keys: {list(data.keys())}")

print("\n2. DIMENSIONS:")
alpha_vec = data['alpha_vector']
print(f"   Alpha vector: {len(alpha_vec)} points")
print(f"   Range: {alpha_vec.min():.1f} to {alpha_vec.max():.1f} deg")

print("\n3. DATA SHAPES:")
for key in ['cx_data', 'cy_data', 'cz_data', 'cl_data', 'cm_data', 'cn_data']:
    if key in data:
        print(f"   {key:12s}: {data[key].shape}")

print("\n4. RATE DERIVATIVE SHAPES:")
for key in ['cxq_data', 'czq_data', 'cmq_data', 'clp_data', 'cnr_data']:
    if key in data:
        print(f"   {key:12s}: {data[key].shape}")

# Find cruise condition
idx_cruise = np.argmin(np.abs(alpha_vec - 4.35))
alpha_cruise = alpha_vec[idx_cruise]

print(f"\n5. AT CRUISE (alpha = {alpha_cruise:.2f} deg):")
print(f"   Cm  = {data['cm_data'][idx_cruise, 2]:.6f}  (moment coeff at neutral elevator)")
print(f"   Cmq = {data['cmq_data'][idx_cruise]:.6f}  (pitch damping)")

# Check Cm vs alpha (derivative)
if len(alpha_vec) > 1:
    dalpha = alpha_vec[1] - alpha_vec[0]
    Cm_vals = data['cm_data'][:, 2]  # Neutral elevator
    dCm_dalpha = np.gradient(Cm_vals, dalpha)
    Cma_numeric = dCm_dalpha[idx_cruise] * (180/np.pi)  # Convert to per radian
    print(f"   Cma = {Cma_numeric:.6f} /rad  (numerical derivative dCm/dalpha)")

    if Cma_numeric > 0:
        print(f"   [WARNING] Cma is POSITIVE = UNSTABLE!")
    else:
        print(f"   [OK] Cma is NEGATIVE = STABLE")

print("\n6. Cm vs ALPHA (all points, neutral elevator):")
print("   Alpha[deg]    Cm")
print("   " + "-"*30)
for i in range(len(alpha_vec)):
    print(f"   {alpha_vec[i]:7.2f}     {data['cm_data'][i, 2]:8.5f}")

print("\n7. CHECKING FOR SIGN ISSUES:")
# CL should be positive at positive alpha
idx_pos = np.argmin(np.abs(alpha_vec - 5.0))
CL_at_5deg = -data['cz_data'][idx_pos, 2]  # CL = -Cz in stability axes
print(f"   At alpha=5°: CL = {CL_at_5deg:.4f}")
if CL_at_5deg > 0:
    print(f"   [OK] CL is positive at positive alpha")
else:
    print(f"   [ERROR] CL is negative - possible sign error!")

# Cm should be trimmed near zero at cruise
Cm_trim = data['cm_data'][idx_cruise, 2]
if abs(Cm_trim) < 0.05:
    print(f"   [OK] Cm near zero at cruise ({Cm_trim:.6f})")
else:
    print(f"   [WARNING] Cm far from zero at cruise ({Cm_trim:.6f})")

print("\n" + "="*70)
