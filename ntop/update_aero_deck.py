#!/usr/bin/env python
"""Update aero deck with real AVL data.

This script loads the AVL alpha sweep data and creates a complete
aerodynamic deck for use in the 6-DOF simulation.
"""

from pathlib import Path
import numpy as np
import pandas as pd
from aero_deck import AeroDeck


def update_aero_deck_from_avl(avl_csv_path: Path, output_path: Path):
    """Update aero deck with real AVL data from alpha sweep.

    Args:
        avl_csv_path: Path to avl_alpha_sweep.csv
        output_path: Path to save updated ntop_aero_deck.npz
    """
    print("="*70)
    print("Updating Aero Deck with AVL Data")
    print("="*70)
    print(f"Loading AVL data from: {avl_csv_path}")

    # Load AVL data
    df = pd.read_csv(avl_csv_path)

    print(f"Loaded {len(df)} data points")
    print(f"Alpha range: {df['alpha'].min():.1f}° to {df['alpha'].max():.1f}°")
    print()

    # Extract alpha vector
    alpha_vector = df['alpha'].values

    # For now, we only have beta=0 data, but interpolants need at least 2 points
    # Add a small second beta point with approximately zero lateral effects
    beta_vector = np.array([0.0, 1.0])

    # Define control surface deflection ranges (placeholder - no control surfaces in AVL model yet)
    elevator_vector = np.array([-24, -12, 0, 12, 24])
    aileron_vector = np.array([-20, -10, 0, 10, 20])
    rudder_vector = np.array([-30, -15, 0, 15, 30])

    n_alpha = len(alpha_vector)
    n_beta = len(beta_vector)
    n_elev = len(elevator_vector)

    # Convert AVL data to body axis coefficients
    # AVL outputs CL, CD which are in wind axes
    # Need to convert to body axis: CX, CZ

    print("Converting to body axis coefficients...")

    # Body axis force coefficients
    CL = df['CL'].values
    CD = df['CD'].values
    alpha_rad = np.deg2rad(alpha_vector)

    # CX = CD * cos(alpha) - CL * sin(alpha)  (approximately -CD for small alpha)
    # CZ = -CD * sin(alpha) - CL * cos(alpha) (approximately -CL for small alpha)
    # But AVL already gives us CX, CZ in body axes!
    CX = df['CX'].values
    CZ = df['CZ'].values

    # Cx data: for now, no elevator effect (would need AVL runs with elevator)
    # Just replicate CX for each elevator setting
    cx_data = np.tile(CX[:, np.newaxis], (1, n_elev))

    # Cy data: only indexed by beta (not alpha)
    # cy_data shape should be (n_beta,) = (2,)
    # Use CYb from AVL to estimate: CY ≈ CYb * beta
    # Average CYb across all alphas (should be fairly constant)
    CYb_avg = df['CYb'].mean()  # per degree
    cy_data = CYb_avg * beta_vector  # CY at each beta

    # Cz data: just alpha dependence for now
    cz_data = CZ

    # Rolling moment: shape (n_alpha, n_beta) = (24, 2)
    # Use Clb to estimate: Cl ≈ Clb * beta
    Clb = df['Clb'].values  # Shape (24,) - varies with alpha
    cl_data = np.zeros((n_alpha, n_beta))
    for i in range(n_alpha):
        cl_data[i, :] = Clb[i] * beta_vector

    # Pitching moment: replicate for each elevator setting
    # cm_data needs shape (n_alpha, n_elev)
    Cm = df['Cm'].values
    cm_data = np.tile(Cm[:, np.newaxis], (1, n_elev))

    # Yawing moment: shape (n_alpha, n_beta) = (24, 2)
    # Use Cnb to estimate: Cn ≈ Cnb * beta
    Cnb = df['Cnb'].values  # Shape (24,) - varies with alpha
    cn_data = np.zeros((n_alpha, n_beta))
    for i in range(n_alpha):
        cn_data[i, :] = Cnb[i] * beta_vector

    # Damping derivatives (all functions of alpha)
    # CLq is given by AVL, need to convert to Czq
    CLq = df['CLq'].values
    Cmq = df['Cmq'].values

    # Czq ≈ -CLq (assuming small alpha)
    czq_data = -CLq
    cmq_data = Cmq

    # For Cxq, use approximation: Cxq ≈ 0 (small for most aircraft)
    cxq_data = np.zeros(n_alpha)

    # Lateral-directional damping derivatives from AVL
    # These are per-radian rates
    clp_data = df['Clp'].values  # Roll damping
    clr_data = df['Clr'].values  # Roll due to yaw rate
    cnp_data = df['Cnp'].values  # Yaw due to roll rate
    cnr_data = df['Cnr'].values  # Yaw damping

    cyp_data = np.zeros(n_alpha)  # AVL doesn't output Cyp directly
    cyr_data = np.zeros(n_alpha)  # AVL doesn't output Cyr directly

    # Control derivatives (function of alpha, beta)
    # We don't have control surfaces in AVL model yet, so use placeholder
    # These should come from AVL runs with control deflections
    # Shape should be (n_alpha, n_beta) = (24, 2)
    dlda_data = np.full((n_alpha, n_beta), -0.05)  # Roll due to aileron
    dldr_data = np.full((n_alpha, n_beta), 0.01)   # Roll due to rudder
    dnda_data = np.full((n_alpha, n_beta), -0.002) # Adverse yaw
    dndr_data = np.full((n_alpha, n_beta), -0.08)  # Yaw due to rudder

    print("Creating AeroDeck object...")

    # Create AeroDeck
    aero_deck = AeroDeck(
        alpha_vector=alpha_vector,
        beta_vector=beta_vector,
        elevator_vector=elevator_vector,
        aileron_vector=aileron_vector,
        rudder_vector=rudder_vector,
        cx_data=cx_data,
        cy_data=cy_data,
        cz_data=cz_data,
        cl_data=cl_data,
        cm_data=cm_data,
        cn_data=cn_data,
        cxq_data=cxq_data,
        cyp_data=cyp_data,
        cyr_data=cyr_data,
        czq_data=czq_data,
        clp_data=clp_data,
        clr_data=clr_data,
        cmq_data=cmq_data,
        cnp_data=cnp_data,
        cnr_data=cnr_data,
        dlda_data=dlda_data,
        dldr_data=dldr_data,
        dnda_data=dnda_data,
        dndr_data=dndr_data,
    )

    # Save to file
    aero_deck.save(output_path)

    print()
    print("="*70)
    print("Aero Deck Summary (Real AVL Data)")
    print("="*70)
    print(f"Alpha range: {alpha_vector[0]:.1f}° to {alpha_vector[-1]:.1f}°")
    print(f"Number of alpha points: {n_alpha}")
    print(f"Beta range: {beta_vector[0]:.1f}° to {beta_vector[-1]:.1f}° ({n_beta} points)")
    print()
    print("Coefficient ranges:")
    print(f"  CL: {CL.min():.3f} to {CL.max():.3f}")
    print(f"  CD: {CD.min():.4f} to {CD.max():.4f}")
    print(f"  Cm: {Cm.min():.3f} to {Cm.max():.3f}")
    print(f"  CLa: {df['CLa'].min():.2f} to {df['CLa'].max():.2f} /rad")
    print(f"  Cma: {df['Cma'].min():.2f} to {df['Cma'].max():.2f} /rad")
    print()
    print("Damping derivatives (at alpha=5°):")
    idx_5deg = np.argmin(np.abs(alpha_vector - 5.0))
    print(f"  Czq = {czq_data[idx_5deg]:.2f} /rad")
    print(f"  Cmq = {cmq_data[idx_5deg]:.2f} /rad")
    print(f"  Clp = {clp_data[idx_5deg]:.3f} /rad")
    print(f"  Cnr = {cnr_data[idx_5deg]:.3f} /rad")
    print()
    print("Notes:")
    print("  - Force/moment coefficients are from AVL (inviscid)")
    print("  - Stability derivatives extracted from AVL output")
    print("  - Lateral coefficients estimated from stability derivatives (CYb, Clb, Cnb)")
    print("  - Control derivatives are placeholders (need AVL runs with controls)")
    print("  - Full beta sweep not yet run (using linearized approximation)")
    print()
    print("="*70)
    print("SUCCESS! Aero deck updated with real AVL data")
    print("="*70)
    print()
    print("Next steps:")
    print("  1. Optional: Run beta sweep for better lateral-directional data")
    print("  2. Run: python ntop/run_f16_style_sim.py")
    print("  3. Or implement trim solver first: python ntop/trim.py")
    print()

    return aero_deck


if __name__ == "__main__":
    # Paths
    data_dir = Path(__file__).parent / "data" / "generated"
    avl_csv = data_dir / "avl_alpha_sweep.csv"
    output_npz = data_dir / "ntop_aero_deck.npz"

    # Update aero deck
    aero_deck = update_aero_deck_from_avl(avl_csv, output_npz)
