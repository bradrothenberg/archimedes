#!/usr/bin/env python
"""Run complete AVL analysis sweep for nTop wing.

This script runs AVL for a full alpha sweep and extracts all aerodynamic
coefficients and stability derivatives needed for the aero deck.
"""

import subprocess
from pathlib import Path
import numpy as np
import pandas as pd
import re


def run_avl_alpha_sweep(
    alpha_range=(-10, 45, 24),
    beta=0.0,
    output_dir=None,
):
    """Run AVL for complete alpha sweep.

    Args:
        alpha_range: (start, end, num_points) for alpha sweep
        beta: Sideslip angle [deg]
        output_dir: Output directory for results

    Returns:
        DataFrame with all coefficients and derivatives
    """
    if output_dir is None:
        output_dir = Path(__file__).parent / "data" / "generated"
    else:
        output_dir = Path(output_dir)

    avl_file = output_dir / "ntop_wing.avl"
    mass_file = output_dir / "ntop_wing.mass"

    print("="*70)
    print("AVL Alpha Sweep Analysis")
    print("="*70)
    print(f"Alpha range: {alpha_range[0]}° to {alpha_range[1]}° ({alpha_range[2]} points)")
    print(f"Beta: {beta}°")
    print(f"Output directory: {output_dir}")
    print()

    # Generate alpha values
    alpha_values = np.linspace(alpha_range[0], alpha_range[1], alpha_range[2])

    results = []

    for i, alpha in enumerate(alpha_values, 1):
        print(f"[{i}/{len(alpha_values)}] Running alpha = {alpha:.1f}°...", end=" ")

        # Create AVL command file with RELATIVE paths (AVL runs in output_dir)
        ft_filename = f"ft_a{alpha:.1f}.txt"
        st_filename = f"st_a{alpha:.1f}.txt"

        commands = [
            "LOAD ntop_wing.avl",
            "",  # Accept name
            "MASS ntop_wing.mass",
            "OPER",
            "A",  # Set alpha
            f"A {alpha}",
            "B",  # Set beta
            f"B {beta}",
            "X",  # Execute
            "FT",  # Total forces
            ft_filename,
            "ST",  # Stability derivatives
            st_filename,
            "",  # Back to OPER
            "QUIT",
        ]

        cmd_file = output_dir / f"cmd_a{alpha:.1f}.txt"
        with open(cmd_file, "w") as f:
            f.write("\n".join(commands))

        # Run AVL
        try:
            with open(cmd_file, "r") as cmd_in:
                result = subprocess.run(
                    ["avl"],
                    stdin=cmd_in,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=output_dir,
                )

            # Parse results (now look for files in output_dir)
            ft_file = output_dir / ft_filename
            st_file = output_dir / st_filename
            coeffs = parse_avl_total_forces(ft_file)
            derivs = parse_avl_stability_derivatives(st_file)

            if coeffs and derivs:
                # Combine results
                data = {
                    'alpha': alpha,
                    'beta': beta,
                    **coeffs,
                    **derivs,
                }
                results.append(data)
                print(f"OK CL={coeffs['CL']:.4f}, CD={coeffs['CD']:.4f}")
            else:
                print("FAILED Parse failed")

        except Exception as e:
            print(f"ERROR: {e}")

    # Save results
    if results:
        df = pd.DataFrame(results)
        output_file = output_dir / "avl_alpha_sweep.csv"
        df.to_csv(output_file, index=False)
        print(f"\nOK Saved {len(results)} results to: {output_file}")
        print("\nSummary:")
        print(df[['alpha', 'CL', 'CD', 'Cm', 'CLa', 'Cma']].to_string(index=False))
        return df
    else:
        print("\n✗ No results obtained")
        return None


def parse_avl_total_forces(filename):
    """Parse AVL total forces output file.

    Args:
        filename: Path to FT output file

    Returns:
        Dictionary of force coefficients
    """
    try:
        with open(filename, 'r') as f:
            content = f.read()

        coeffs = {}

        # Parse main coefficients
        patterns = {
            'CL': r'CLtot\s*=\s*([-\d.]+)',
            'CD': r'CDtot\s*=\s*([-\d.]+)',
            'Cm': r'Cmtot\s*=\s*([-\d.]+)',
            'CX': r'CXtot\s*=\s*([-\d.]+)',
            'CY': r'CYtot\s*=\s*([-\d.]+)',
            'CZ': r'CZtot\s*=\s*([-\d.]+)',
            'Cl': r'Cltot\s*=\s*([-\d.]+)',
            'Cn': r'Cntot\s*=\s*([-\d.]+)',
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                coeffs[key] = float(match.group(1))

        return coeffs if coeffs else None

    except Exception as e:
        print(f"Error parsing {filename}: {e}")
        return None


def parse_avl_stability_derivatives(filename):
    """Parse AVL stability derivatives output file.

    Args:
        filename: Path to ST output file

    Returns:
        Dictionary of stability derivatives
    """
    try:
        with open(filename, 'r') as f:
            content = f.read()

        derivs = {}

        # Parse stability derivatives
        # Format: "CLa   =   4.567890"
        patterns = {
            'CLa': r'CLa\s*=\s*([-\d.]+)',
            'Cma': r'Cma\s*=\s*([-\d.]+)',
            'CYb': r'CYb\s*=\s*([-\d.]+)',
            'Clb': r'Clb\s*=\s*([-\d.]+)',
            'Cnb': r'Cnb\s*=\s*([-\d.]+)',
            'CLq': r'CLq\s*=\s*([-\d.]+)',
            'Cmq': r'Cmq\s*=\s*([-\d.]+)',
            'Clp': r'Clp\s*=\s*([-\d.]+)',
            'Cnp': r'Cnp\s*=\s*([-\d.]+)',
            'Clr': r'Clr\s*=\s*([-\d.]+)',
            'Cnr': r'Cnr\s*=\s*([-\d.]+)',
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                derivs[key] = float(match.group(1))

        return derivs if derivs else None

    except Exception as e:
        print(f"Error parsing {filename}: {e}")
        return None


def run_avl_beta_sweep(
    beta_range=(-30, 30, 13),
    alpha=5.0,
    output_dir=None,
):
    """Run AVL for beta sweep (lateral-directional).

    Args:
        beta_range: (start, end, num_points) for beta sweep
        alpha: Angle of attack [deg]
        output_dir: Output directory for results

    Returns:
        DataFrame with lateral-directional coefficients
    """
    if output_dir is None:
        output_dir = Path(__file__).parent / "data" / "generated"
    else:
        output_dir = Path(output_dir)

    print("\n" + "="*70)
    print("AVL Beta Sweep Analysis")
    print("="*70)
    print(f"Beta range: {beta_range[0]}° to {beta_range[1]}° ({beta_range[2]} points)")
    print(f"Alpha: {alpha}°")
    print()

    beta_values = np.linspace(beta_range[0], beta_range[1], beta_range[2])

    results = []

    for i, beta in enumerate(beta_values, 1):
        print(f"[{i}/{len(beta_values)}] Running beta = {beta:.1f}°...", end=" ")

        # Similar to alpha sweep but varying beta
        # Implementation similar to above...

        # For now, placeholder
        print("(placeholder)")

    return pd.DataFrame(results) if results else None


if __name__ == "__main__":
    # Run alpha sweep
    df_alpha = run_avl_alpha_sweep(
        alpha_range=(-10, 45, 24),
        beta=0.0,
    )

    if df_alpha is not None:
        print("\n" + "="*70)
        print("SUCCESS! AVL alpha sweep complete.")
        print("="*70)
        print("\nNext steps:")
        print("  1. Review: ntop/data/generated/avl_alpha_sweep.csv")
        print("  2. Run: python ntop/update_aero_deck.py")
        print("  3. Then: python ntop/run_f16_style_sim.py")
    else:
        print("\nFailed to complete AVL sweep.")
        print("Check AVL installation and file paths.")
