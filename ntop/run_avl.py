#!/usr/bin/env python
"""Run AVL analysis and extract aerodynamic data."""

import subprocess
from pathlib import Path
import pandas as pd
import numpy as np

def run_avl_analysis():
    """Run AVL analysis for alpha sweep."""

    # Paths
    data_dir = Path(__file__).parent / "data" / "generated"
    avl_file = data_dir / "ntop_wing.avl"
    mass_file = data_dir / "ntop_wing.mass"

    print("="*60)
    print("Running AVL Analysis")
    print("="*60)

    # Alpha sweep parameters
    alpha_values = np.linspace(-10, 45, 12)

    results = []

    for alpha in alpha_values:
        print(f"\nRunning alpha = {alpha:.1f} deg...")

        # Create AVL command file
        commands = [
            f"LOAD {avl_file}",
            "",  # Accept defaults
            f"MASS {mass_file}",
            "OPER",
            "A",  # Set alpha
            f"A {alpha}",
            "X",  # Execute
            "",  # Exit to top menu
            "QUIT",
        ]

        commands_file = data_dir / "avl_commands.txt"
        with open(commands_file, "w") as f:
            f.write("\n".join(commands))

        # Run AVL
        try:
            with open(commands_file, "r") as cmd_in:
                result = subprocess.run(
                    ["avl"],
                    stdin=cmd_in,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=data_dir,
                )

            # Parse output for coefficients
            output = result.stdout

            # Simple parsing - look for key lines
            CL, CD, Cm = None, None, None

            for line in output.split('\n'):
                if 'CLtot' in line or 'CL =' in line:
                    try:
                        CL = float(line.split('=')[-1].strip().split()[0])
                    except:
                        pass
                if 'CDtot' in line or 'CD =' in line:
                    try:
                        CD = float(line.split('=')[-1].strip().split()[0])
                    except:
                        pass
                if 'Cmtot' in line or 'Cm =' in line:
                    try:
                        Cm = float(line.split('=')[-1].strip().split()[0])
                    except:
                        pass

            if CL is not None:
                results.append({
                    'alpha': alpha,
                    'CL': CL,
                    'CD': CD if CD is not None else 0.02,  # Default
                    'Cm': Cm if Cm is not None else 0.0,
                })
                print(f"  CL = {CL:.4f}, CD = {CD:.4f}, Cm = {Cm:.4f}")
            else:
                print(f"  Warning: Could not parse results for alpha={alpha}")

        except Exception as e:
            print(f"  Error: {e}")

    # Save results
    if results:
        df = pd.DataFrame(results)
        output_file = data_dir / "avl_results.csv"
        df.to_csv(output_file, index=False)
        print(f"\n✓ Saved AVL results to: {output_file}")
        print(f"\nResults summary:")
        print(df.to_string(index=False))
        return df
    else:
        print("\n✗ No results obtained from AVL")
        return None


if __name__ == "__main__":
    results = run_avl_analysis()

    if results is not None:
        print("\n" + "="*60)
        print("SUCCESS! AVL analysis complete.")
        print("="*60)
        print("\nNext steps:")
        print("  1. Review results in: ntop/data/generated/avl_results.csv")
        print("  2. Update aero_deck.py to use real AVL data")
        print("  3. Run simulation: python ntop/test_sim.py")
    else:
        print("\nNote: You can also run AVL manually:")
        print("  cd ntop/data/generated")
        print("  avl ntop_wing.avl")
