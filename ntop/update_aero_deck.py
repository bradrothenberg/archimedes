#!/usr/bin/env python
"""Update aero deck with real AVL data.

This script loads the AVL alpha sweep data and creates a complete
aerodynamic deck for use in the 6-DOF simulation.
"""

from pathlib import Path
import numpy as np
import pandas as pd
from aero_deck import AeroDeck


def update_aero_deck_from_avl(avl_csv_path: Path, elevon_csv_path: Path, output_path: Path):
    """Update aero deck with real AVL data from alpha sweep and elevon sweep.

    Args:
        avl_csv_path: Path to avl_alpha_sweep.csv
        elevon_csv_path: Path to avl_elevon_sweep.csv
        output_path: Path to save updated ntop_aero_deck.npz
    """
    print("="*70)
    print("Updating Aero Deck with AVL Data + Elevon Control Derivatives")
    print("="*70)
    print(f"Loading AVL data from: {avl_csv_path}")
    print(f"Loading elevon data from: {elevon_csv_path}")

    # Load AVL data
    df = pd.read_csv(avl_csv_path)
    df_elevon = pd.read_csv(elevon_csv_path)

    print(f"Loaded {len(df)} alpha sweep data points")
    print(f"Alpha range: {df['alpha'].min():.1f}° to {df['alpha'].max():.1f}°")
    print(f"Loaded {len(df_elevon)} elevon sweep data points")
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

    # Cx data: add elevon (elevator mode) effect from sweep data
    # Extract dCx/de from symmetric elevon data
    df_sym = df_elevon[df_elevon['elevon_mode'] == 'symmetric']

    # Extract dCx/de at the elevon sweep alphas, then interpolate
    elevon_alphas = sorted(df_sym['alpha'].unique())
    dCx_de_at_elevon_alphas = []

    for alpha in elevon_alphas:
        df_alpha = df_sym[df_sym['alpha'] == alpha]
        if len(df_alpha) > 1:
            elevon_def = df_alpha['elevon_L'].values
            CX_vals = df_alpha['CX'].values
            dCx_de = np.polyfit(elevon_def, CX_vals, 1)[0]
        else:
            dCx_de = 0.0
        dCx_de_at_elevon_alphas.append(dCx_de)

    # Interpolate to full alpha vector
    dCx_de_values = np.interp(alpha_vector, elevon_alphas, dCx_de_at_elevon_alphas)

    # Build cx_data as function of (alpha, elevator)
    # CX(alpha, elev) = CX_base(alpha) + dCx_de(alpha) * elev
    cx_data = np.zeros((n_alpha, n_elev))
    for i in range(n_alpha):
        for j in range(n_elev):
            cx_data[i, j] = CX[i] + dCx_de_values[i] * elevator_vector[j]

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

    # Pitching moment: add elevon (elevator mode) control effectiveness
    # cm_data needs shape (n_alpha, n_elev)
    Cm = df['Cm'].values

    # Extract dCm/de at elevon sweep alphas, then interpolate
    dCm_de_at_elevon_alphas = []
    for alpha in elevon_alphas:
        df_alpha = df_sym[df_sym['alpha'] == alpha]
        if len(df_alpha) > 1:
            elevon_def = df_alpha['elevon_L'].values
            Cm_vals = df_alpha['Cm'].values
            dCm_de = np.polyfit(elevon_def, Cm_vals, 1)[0]
        else:
            dCm_de = 0.0
        dCm_de_at_elevon_alphas.append(dCm_de)

    # Interpolate to full alpha vector
    dCm_de_values = np.interp(alpha_vector, elevon_alphas, dCm_de_at_elevon_alphas)

    # Build cm_data: Cm(alpha, elev) = Cm_base(alpha) + dCm_de(alpha) * elev
    cm_data = np.zeros((n_alpha, n_elev))
    for i in range(n_alpha):
        for j in range(n_elev):
            cm_data[i, j] = Cm[i] + dCm_de_values[i] * elevator_vector[j]

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
    # Extract from antisymmetric elevon data (roll control)
    df_anti = df_elevon[df_elevon['elevon_mode'] == 'antisymmetric']

    # dCl/da (roll control) - elevon differential creates rolling moment
    # Extract at elevon alphas, then interpolate
    dCl_da_at_elevon_alphas = []
    dCn_da_at_elevon_alphas = []

    for alpha in elevon_alphas:
        df_alpha = df_anti[df_anti['alpha'] == alpha]
        if len(df_alpha) > 1:
            # Elevon differential = 2 * elevon_L (since R = -L)
            elevon_diff = 2 * df_alpha['elevon_L'].values
            Cl_vals = df_alpha['Cl'].values
            Cn_vals = df_alpha['Cn'].values
            dCl_da = np.polyfit(elevon_diff, Cl_vals, 1)[0]
            dCn_da = np.polyfit(elevon_diff, Cn_vals, 1)[0]
        else:
            dCl_da = 0.0015  # Default
            dCn_da = 0.0
        dCl_da_at_elevon_alphas.append(dCl_da)
        dCn_da_at_elevon_alphas.append(dCn_da)

    # Interpolate to full alpha vector
    dCl_da_values = np.interp(alpha_vector, elevon_alphas, dCl_da_at_elevon_alphas)
    dCn_da_values = np.interp(alpha_vector, elevon_alphas, dCn_da_at_elevon_alphas)

    # Shape (n_alpha, n_beta) = (24, 2)
    dlda_data = np.zeros((n_alpha, n_beta))
    dnda_data = np.zeros((n_alpha, n_beta))
    for i in range(n_alpha):
        dlda_data[i, :] = dCl_da_values[i]
        dnda_data[i, :] = dCn_da_values[i]

    # Rudder derivatives: placeholder (no rudder in current model)
    dldr_data = np.full((n_alpha, n_beta), 0.01)   # Roll due to rudder
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
    print("Control effectiveness (at alpha=5°):")
    idx_5deg = np.argmin(np.abs(alpha_vector - 5.0))
    print(f"  dCm/de = {dCm_de_values[idx_5deg]:.4f} /deg (pitch)")
    print(f"  dCl/da = {dlda_data[idx_5deg, 0]:.4f} /deg (roll)")
    print()
    print("Notes:")
    print("  - Force/moment coefficients are from AVL (inviscid)")
    print("  - Stability derivatives extracted from AVL output")
    print("  - Lateral coefficients estimated from stability derivatives (CYb, Clb, Cnb)")
    print("  - Control derivatives from elevon sweep (pitch & roll control)")
    print("  - Full beta sweep not yet run (using linearized approximation)")
    print("  - Rudder derivatives are placeholder (no rudder in current model)")
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
    elevon_csv = data_dir / "avl_elevon_sweep.csv"
    output_npz = data_dir / "ntop_aero_deck.npz"

    # Update aero deck
    aero_deck = update_aero_deck_from_avl(avl_csv, elevon_csv, output_npz)
