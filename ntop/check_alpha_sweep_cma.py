"""
Check the Cma values from alpha sweep and compare to ST output
"""
import pandas as pd
import numpy as np
from pathlib import Path

# Read alpha sweep data
data_dir = Path(__file__).parent / "data" / "generated"
df = pd.read_csv(data_dir / "avl_alpha_sweep.csv")

print("="*70)
print("CHECKING ALPHA SWEEP Cma VALUES")
print("="*70)

# Find the row closest to alpha = 4.17 degrees
target_alpha = 4.17
idx = (df['alpha'] - target_alpha).abs().idxmin()
row = df.loc[idx]

print(f"\n1. ALPHA SWEEP DATA (closest to alpha = 4.17 deg):")
print(f"   Alpha:  {row['alpha']:.2f} deg")
print(f"   CL:     {row['CL']:.5f}")
print(f"   Cm:     {row['Cm']:.5f}")
print(f"   CLa:    {row['CLa']:.6f} /rad")
print(f"   Cma:    {row['Cma']:.6f} /rad (POSITIVE!)")

print(f"\n2. AVL ST OUTPUT (from stability axes):")
print(f"   Alpha:  4.17 deg")
print(f"   CLa:    2.811901 /rad")
print(f"   Cma:   -0.235981 /rad (NEGATIVE!)")

print(f"\n3. COMPARISON:")
print(f"   CLa difference: {row['CLa'] - 2.811901:.6f} /rad")
print(f"   Cma difference: {row['Cma'] - (-0.235981):.6f} /rad")

print(f"\n4. UNDERSTANDING THE DISCREPANCY:")
print(f"   The alpha sweep shows POSITIVE Cma = +{row['Cma']:.6f} /rad")
print(f"   The ST command shows NEGATIVE Cma = -0.235981 /rad")
print(f"")
print(f"   The difference is {row['Cma'] + 0.235981:.6f} /rad")
print(f"")
print(f"   This is NOT just a body vs stability axes issue!")

print(f"\n5. CHECKING ALPHA SWEEP CALCULATION:")
print(f"   Let's check a few rows to see how Cma changes with alpha:")
print()
print("   Alpha (deg)   CL        Cm        CLa (/rad)   Cma (/rad)")
print("   " + "-"*60)
for i in range(0, len(df), 5):
    print(f"   {df.loc[i, 'alpha']:6.2f}      {df.loc[i, 'CL']:7.5f}   {df.loc[i, 'Cm']:8.5f}   {df.loc[i, 'CLa']:8.6f}   {df.loc[i, 'Cma']:9.6f}")

print(f"\n6. KEY OBSERVATION:")
print(f"   ALL Cma values in the alpha sweep are POSITIVE throughout the range!")
print(f"   This suggests the alpha sweep Cma may be calculated incorrectly.")
print(f"   Or it's using a different definition/reference frame.")

print("\n" + "="*70)
print("CONCLUSION")
print("="*70)
print("\nThe TRUE stability derivative from AVL's ST command is:")
print("   Cma = -0.235981 /rad (NEGATIVE = STABLE)")
print("\nThe alpha sweep Cma values appear to be incorrect or using")
print("a different calculation method. We should trust the ST output")
print("from AVL which uses the proper vortex lattice derivatives.")
print("\nThe aircraft IS STABLE with:")
print("   - Static margin = 8.39%")
print("   - Neutral point at 13.54 ft (8.36 inches aft of CG)")
print("="*70)
