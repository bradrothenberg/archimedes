"""
Analyze the neutral point discrepancy between AVL output and calculations
"""

# Data from AVL stability output at alpha = 4.17 degrees
print("="*70)
print("NEUTRAL POINT ANALYSIS")
print("="*70)

# AVL output data
CG_x = 12.846  # ft (from mass file and AVL output)
MAC = 8.2982  # ft (from AVL geometry)
Sref = 206.32  # ft^2

# From AVL ST output (STABILITY AXES):
Cma_stability = -0.235981  # /rad (NEGATIVE!)
CLa_stability = 2.811901  # /rad
Xnp_avl = 13.542505  # ft (from AVL)

print(f"\n1. AVL OUTPUT (Stability Axes):")
print(f"   Xref (CG):    {CG_x:.4f} ft")
print(f"   Xnp (AVL):    {Xnp_avl:.4f} ft")
print(f"   CLa:          {CLa_stability:.6f} /rad")
print(f"   Cma:          {Cma_stability:.6f} /rad (NEGATIVE = STABLE!)")
print(f"   MAC:          {MAC:.4f} ft")

# Calculate static margin from AVL's neutral point
SM_from_np = (Xnp_avl - CG_x) / MAC
print(f"\n2. STATIC MARGIN from AVL Neutral Point:")
print(f"   SM = (Xnp - Xcg) / MAC")
print(f"   SM = ({Xnp_avl:.4f} - {CG_x:.4f}) / {MAC:.4f}")
print(f"   SM = {SM_from_np:.6f} = {SM_from_np*100:.2f}%")
print(f"   [OK] Positive SM means STABLE (NP aft of CG)")

# Calculate Cma from neutral point using textbook formula
Cma_from_np = -CLa_stability * SM_from_np
print(f"\n3. VERIFY Cma from Neutral Point:")
print(f"   Cma = -CLa * SM")
print(f"   Cma = -{CLa_stability:.6f} * {SM_from_np:.6f}")
print(f"   Cma = {Cma_from_np:.6f} /rad")
print(f"   AVL Cma = {Cma_stability:.6f} /rad")
print(f"   Match? {abs(Cma_from_np - Cma_stability) < 0.001}")

# Calculate neutral point from Cma
Xnp_from_cma = CG_x - (Cma_stability / CLa_stability) * MAC
print(f"\n4. CALCULATE Neutral Point from Cma:")
print(f"   Xnp = Xcg - (Cma / CLa) * MAC")
print(f"   Xnp = {CG_x:.4f} - ({Cma_stability:.6f} / {CLa_stability:.6f}) * {MAC:.4f}")
print(f"   Xnp = {CG_x:.4f} - ({Cma_stability/CLa_stability:.6f}) * {MAC:.4f}")
print(f"   Xnp = {Xnp_from_cma:.4f} ft")
print(f"   AVL Xnp = {Xnp_avl:.4f} ft")
print(f"   Difference: {abs(Xnp_from_cma - Xnp_avl):.6f} ft = {abs(Xnp_from_cma - Xnp_avl)*12:.4f} inches")

print("\n" + "="*70)
print("RESOLUTION OF CONTRADICTION")
print("="*70)

print("\n5. THE KEY ISSUE:")
print("   [X] Previous alpha sweep data showed Cma = +0.6259 /rad (POSITIVE)")
print("   [OK] AVL stability axes show Cma = -0.2360 /rad (NEGATIVE)")
print("\n   THESE ARE DIFFERENT REFERENCE FRAMES!")

print("\n6. BODY AXES vs STABILITY AXES:")
print("   - Body axes: Fixed to aircraft, x-axis along fuselage")
print("   - Stability axes: Rotated by angle of attack alpha")
print("   - At alpha = 4.17°, there's a coordinate transformation")
print("")
print("   The alpha sweep likely gives BODY AXES derivatives")
print("   The ST command gives STABILITY AXES derivatives")

# Try to understand the transformation
import numpy as np
alpha_rad = np.deg2rad(4.17)
print(f"\n7. COORDINATE TRANSFORMATION:")
print(f"   alpha = {4.17:.2f}° = {alpha_rad:.6f} rad")
print(f"   For small angles, the transformation affects moment derivatives")
print(f"   Cma_body ~= Cma_stability + CLa * alpha (approximate)")
print(f"   Cma_body ~= {Cma_stability:.6f} + {CLa_stability:.6f} * {alpha_rad:.6f}")
print(f"   Cma_body ~= {Cma_stability + CLa_stability * alpha_rad:.6f} /rad")
print(f"   This is still negative, so transformation alone doesn't explain +0.6259")

print("\n8. CONCLUSION:")
print("   The aircraft IS STABLE according to AVL's stability axes analysis:")
print(f"   - Cma (stability) = {Cma_stability:.6f} /rad (NEGATIVE = stable)")
print(f"   - Static margin = {SM_from_np*100:.2f}% (POSITIVE = stable)")
print(f"   - Neutral point at {Xnp_avl:.4f} ft is {(Xnp_avl-CG_x)*12:.2f} inches AFT of CG")
print("")
print("   The positive Cma from alpha sweep needs investigation.")
print("   It may be in different coordinates or have a calculation issue.")

print("\n" + "="*70)
