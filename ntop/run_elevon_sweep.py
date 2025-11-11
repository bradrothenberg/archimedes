#!/usr/bin/env python
"""Run AVL analysis with elevon deflections to extract control derivatives.

This script runs AVL at various alpha angles and elevon deflections to
determine the control effectiveness.
"""

import subprocess
from pathlib import Path
import numpy as np
import pandas as pd
import re


def run_avl_elevon_sweep(
    alpha_points=[0, 5, 10, 15],
    elevon_range=(-20, 20, 9),
    output_dir=None,
):
    """Run AVL with elevon deflections to get control derivatives.

    For a flying wing with elevons:
    - Symmetric deflection (both up/down) = pitch control (elevator mode)
    - Antisymmetric deflection (opposite) = roll control (aileron mode)

    Args:
        alpha_points: List of alpha values to test [deg]
        elevon_range: (start, end, num_points) for elevon deflections [deg]
        output_dir: Output directory for results

    Returns:
        DataFrame with control derivatives
    """
    if output_dir is None:
        output_dir = Path(__file__).parent / "data" / "generated"
    else:
        output_dir = Path(output_dir)

    print("="*70)
    print("AVL Elevon Sweep Analysis")
    print("="*70)
    print(f"Alpha points: {alpha_points}")
    print(f"Elevon range: {elevon_range[0]}° to {elevon_range[1]}° ({elevon_range[2]} points)")
    print(f"Output directory: {output_dir}")
    print()

    # Generate elevon deflection values
    elevon_values = np.linspace(elevon_range[0], elevon_range[1], elevon_range[2])

    results = []

    # Test 1: Symmetric elevon deflection (elevator mode)
    print("Part 1: Symmetric Elevon Deflection (Pitch Control)")
    print("-"*70)

    for alpha in alpha_points:
        for i, elev_def in enumerate(elevon_values, 1):
            print(f"[{len(results)+1}] Alpha={alpha:.1f}°, Elevon_sym={elev_def:.1f}°...", end=" ")

            ft_filename = f"ft_sym_a{alpha:.1f}_e{elev_def:.1f}.txt"
            st_filename = f"st_sym_a{alpha:.1f}_e{elev_def:.1f}.txt"

            # Symmetric: both elevons deflect the same way
            commands = [
                "LOAD ntop_wing.avl",
                "",
                "MASS ntop_wing.mass",
                "OPER",
                "A", f"A {alpha}",
                "D1", f"D1 {elev_def}",  # elevon_L
                "D2", f"D2 {elev_def}",  # elevon_R (same as L for pitch)
                "X",
                "FT", ft_filename,
                "ST", st_filename,
                "",
                "QUIT",
            ]

            cmd_file = output_dir / f"cmd_sym_a{alpha:.1f}_e{elev_def:.1f}.txt"
            with open(cmd_file, "w") as f:
                f.write("\n".join(commands))

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

                ft_file = output_dir / ft_filename
                st_file = output_dir / st_filename
                coeffs = parse_avl_total_forces(ft_file)

                if coeffs:
                    data = {
                        'alpha': alpha,
                        'elevon_mode': 'symmetric',
                        'elevon_L': elev_def,
                        'elevon_R': elev_def,
                        **coeffs,
                    }
                    results.append(data)
                    print(f"OK CL={coeffs['CL']:.4f}, Cm={coeffs['Cm']:.4f}")
                else:
                    print("FAILED")

            except Exception as e:
                print(f"ERROR: {e}")

    # Test 2: Antisymmetric elevon deflection (aileron mode)
    print()
    print("Part 2: Antisymmetric Elevon Deflection (Roll Control)")
    print("-"*70)

    for alpha in alpha_points:
        for i, elev_def in enumerate(elevon_values, 1):
            print(f"[{len(results)+1}] Alpha={alpha:.1f}°, Elevon_anti={elev_def:.1f}°...", end=" ")

            ft_filename = f"ft_anti_a{alpha:.1f}_e{elev_def:.1f}.txt"
            st_filename = f"st_anti_a{alpha:.1f}_e{elev_def:.1f}.txt"

            # Antisymmetric: elevons deflect opposite directions
            commands = [
                "LOAD ntop_wing.avl",
                "",
                "MASS ntop_wing.mass",
                "OPER",
                "A", f"A {alpha}",
                "D1", f"D1 {elev_def}",   # elevon_L up
                "D2", f"D2 {-elev_def}",  # elevon_R down (opposite)
                "X",
                "FT", ft_filename,
                "ST", st_filename,
                "",
                "QUIT",
            ]

            cmd_file = output_dir / f"cmd_anti_a{alpha:.1f}_e{elev_def:.1f}.txt"
            with open(cmd_file, "w") as f:
                f.write("\n".join(commands))

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

                ft_file = output_dir / ft_filename
                st_file = output_dir / st_filename
                coeffs = parse_avl_total_forces(ft_file)

                if coeffs:
                    data = {
                        'alpha': alpha,
                        'elevon_mode': 'antisymmetric',
                        'elevon_L': elev_def,
                        'elevon_R': -elev_def,
                        **coeffs,
                    }
                    results.append(data)
                    print(f"OK Cl={coeffs['Cl']:.4f}, Cn={coeffs['Cn']:.4f}")
                else:
                    print("FAILED")

            except Exception as e:
                print(f"ERROR: {e}")

    # Save results
    if results:
        df = pd.DataFrame(results)
        output_file = output_dir / "avl_elevon_sweep.csv"
        df.to_csv(output_file, index=False)
        print(f"\nOK Saved {len(results)} results to: {output_file}")

        # Compute control derivatives
        print("\n" + "="*70)
        print("Control Derivatives Summary")
        print("="*70)

        # Symmetric mode: dCm/d(elevon)
        df_sym = df[df['elevon_mode'] == 'symmetric']
        for alpha in alpha_points:
            df_alpha = df_sym[df_sym['alpha'] == alpha]
            if len(df_alpha) > 1:
                # Linear fit: Cm = Cm0 + dCm_de * elevon
                elevon = df_alpha['elevon_L'].values
                Cm = df_alpha['Cm'].values
                dCm_de = np.polyfit(elevon, Cm, 1)[0]
                print(f"Alpha={alpha:5.1f}°: dCm/d(elevon_sym) = {dCm_de:7.4f} /deg")

        print()

        # Antisymmetric mode: dCl/d(elevon)
        df_anti = df[df['elevon_mode'] == 'antisymmetric']
        for alpha in alpha_points:
            df_alpha = df_anti[df_anti['alpha'] == alpha]
            if len(df_alpha) > 1:
                # Linear fit: Cl = Cl0 + dCl_da * elevon_diff
                # elevon_diff = elevon_L - elevon_R = 2*elevon_L (since R = -L)
                elevon_diff = df_alpha['elevon_L'].values * 2
                Cl = df_alpha['Cl'].values
                dCl_da = np.polyfit(elevon_diff, Cl, 1)[0]
                print(f"Alpha={alpha:5.1f}°: dCl/d(elevon_anti) = {dCl_da:7.4f} /deg")

        print()
        print("="*70)
        print("SUCCESS! Elevon sweep complete")
        print("="*70)
        print()
        print("Next steps:")
        print("  1. Run: python ntop/update_aero_deck.py")
        print("  2. Implement trim solver")
        print()

        return df
    else:
        print("\nNo results obtained")
        return None


def parse_avl_total_forces(filename):
    """Parse AVL total forces output file."""
    try:
        with open(filename, 'r') as f:
            content = f.read()

        coeffs = {}

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


if __name__ == "__main__":
    # Run elevon sweep at a few alpha points
    df_elevon = run_avl_elevon_sweep(
        alpha_points=[0, 5, 10, 15],
        elevon_range=(-20, 20, 9),
    )
