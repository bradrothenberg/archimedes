# SPDX-FileCopyrightText: 2025 nTop Integration
# SPDX-License-Identifier: GPL-3.0-or-later

"""AVL (Athena Vortex Lattice) interface for aerodynamic analysis.

This module generates AVL input files from nTop geometry and runs
AVL batch analyses to compute aerodynamic coefficients and stability derivatives.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from geometry import MassProperties, WingGeometry


@dataclass
class AVLConfiguration:
    """AVL analysis configuration."""

    # Analysis parameters
    mach: float = 0.5  # Mach number
    altitude: float = 20000.0  # Altitude [ft]
    velocity: float = 550.0  # Velocity [ft/s]
    rho: float = 0.001267  # Density [slug/ft³] at 20,000 ft

    # Sweep ranges
    alpha_range: tuple[float, float, int] = (-10.0, 45.0, 12)  # degrees
    beta_range: tuple[float, float, int] = (-30.0, 30.0, 7)  # degrees

    # Control surface deflections
    elevator_range: tuple[float, float, int] = (-24.0, 24.0, 5)  # degrees
    aileron_range: tuple[float, float, int] = (-20.0, 20.0, 5)  # degrees
    rudder_range: tuple[float, float, int] = (-30.0, 30.0, 5)  # degrees


class AVLInterface:
    """Interface for running AVL analyses."""

    def __init__(
        self,
        wing_geometry: WingGeometry,
        mass_properties: MassProperties,
        output_dir: str | Path,
        avl_executable: str = "avl",
    ):
        """Initialize AVL interface.

        Args:
            wing_geometry: Wing geometry from nTop
            mass_properties: Mass properties from nTop
            output_dir: Directory for AVL input/output files
            avl_executable: Path to AVL executable (default: 'avl' in PATH)
        """
        self.wing_geometry = wing_geometry
        self.mass_properties = mass_properties
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.avl_executable = avl_executable

    def generate_avl_file(self, filename: str = "ntop_wing.avl") -> Path:
        """Generate AVL geometry file from nTop wing data.

        Args:
            filename: Output filename

        Returns:
            Path to generated AVL file
        """
        filepath = self.output_dir / filename

        with open(filepath, "w") as f:
            # Header
            f.write("#=========================================\n")
            f.write("# nTop Wing - AVL Geometry File\n")
            f.write("# Generated from nTop export data\n")
            f.write("#=========================================\n\n")

            # Reference geometry
            f.write(f"nTop Wing\n")
            f.write(f"#Mach\n")
            f.write(f"0.0\n")  # Will be set in run cases
            f.write(f"#IYsym   IZsym   Zsym\n")
            f.write(f"0        0       0.0\n")
            f.write(f"#Sref    Cref    Bref\n")
            f.write(
                f"{self.wing_geometry.reference_area:.6f}    "
                f"{self.wing_geometry.mean_chord:.6f}    "
                f"{self.wing_geometry.span:.6f}\n"
            )
            f.write(f"#Xref    Yref    Zref\n")
            f.write(
                f"{self.mass_properties.cg[0]:.6f}    "
                f"{self.mass_properties.cg[1]:.6f}    "
                f"{self.mass_properties.cg[2]:.6f}\n\n"
            )

            # Main wing surface
            f.write("#=========================================\n")
            f.write("SURFACE\n")
            f.write("Wing\n")
            f.write(f"#Nchordwise  Cspace  Nspanwise  Sspace\n")
            f.write(f"10           1.0     20         1.0\n\n")

            # Component descriptor (1 = conventional aircraft)
            f.write("COMPONENT\n")
            f.write("1\n\n")

            # Create wing sections (positive and negative sides)
            # Get unique y-stations (excluding center)
            sorted_sections = sorted(
                self.wing_geometry.sections, key=lambda s: s.y_station
            )

            # Separate positive and negative span
            center_section = [s for s in sorted_sections if abs(s.y_station) < 0.01]
            negative_sections = [s for s in sorted_sections if s.y_station < -0.01]
            positive_sections = [s for s in sorted_sections if s.y_station > 0.01]

            # Simplify to fewer sections for AVL (AVL needs reasonable spacing)
            # Use root, mid-span, and tip on each side
            def get_representative_sections(sections, n=3):
                """Get n evenly-spaced sections from a list."""
                if len(sections) <= n:
                    return sections
                indices = np.linspace(0, len(sections)-1, n, dtype=int)
                return [sections[i] for i in indices]

            # Get representative sections (just use tip and root)
            neg_repr = get_representative_sections(negative_sections, n=2)
            pos_repr = get_representative_sections(positive_sections, n=2)

            # Write left wing (negative y)
            for section in neg_repr:
                self._write_section(f, section)

            # Write center if exists
            if center_section:
                self._write_section(f, center_section[0])

            # Write right wing (positive y)
            for section in pos_repr:
                self._write_section(f, section)

        print(f"Generated AVL file: {filepath}")
        return filepath

    def _write_section(self, f, section):
        """Write a single wing section to AVL file."""
        f.write("#-----------------------------------------\n")
        f.write("SECTION\n")
        f.write(f"#Xle    Yle    Zle    Chord    Ainc\n")
        f.write(
            f"{section.le_point[0]:.6f}  {section.le_point[1]:.6f}  "
            f"{section.le_point[2]:.6f}  {section.chord:.6f}  0.0\n\n"
        )

        # TODO: Add AFILE directive if airfoil data available
        # For now, use NACA 0012 as placeholder
        f.write("NACA\n")
        f.write("0012\n\n")

    def generate_mass_file(self, filename: str = "ntop_wing.mass") -> Path:
        """Generate AVL mass file.

        Args:
            filename: Output filename

        Returns:
            Path to generated mass file
        """
        filepath = self.output_dir / filename

        with open(filepath, "w") as f:
            f.write("#-------------------------------------------------\n")
            f.write("# nTop Wing - AVL Mass File\n")
            f.write("#-------------------------------------------------\n")
            f.write("# Lunit = ft\n")
            f.write("# Munit = slug\n")
            f.write("# Tunit = s\n")
            f.write("#\n")
            f.write(f"#  g   =  32.17      ft/s^2\n")
            f.write("#\n")
            f.write("# m   =  mass\n")
            f.write("# Ixx,Iyy,Izz,Ixy,Iyz,Izx  =  inertias\n")
            f.write("#\n")
            f.write(
                "#  xcg,ycg,zcg  =  CG location      "
                "(Lunit,  same units as Xle,Yle,Zle)\n"
            )
            f.write("#\n")
            f.write("#-------------------------------------------------\n")
            f.write("Lunit = 1.0 ft\n")
            f.write("Munit = 1.0 slug\n")
            f.write("Tunit = 1.0 s\n")
            f.write("#\n")
            f.write("g = 32.17\n")
            f.write(f"rho = 0.001267\n")  # Standard at 20,000 ft
            f.write("#\n")
            f.write(f"#  Mass\n")
            f.write(f"{self.mass_properties.mass:.6f}\n")
            f.write("#\n")
            f.write(f"#  Inertias\n")
            I = self.mass_properties.inertia
            f.write(f"{I[0,0]:.6f}  {I[1,1]:.6f}  {I[2,2]:.6f}\n")
            f.write(f"{I[0,1]:.6f}  {I[1,2]:.6f}  {I[2,0]:.6f}\n")
            f.write("#\n")
            f.write(f"#  CG location\n")
            cg = self.mass_properties.cg
            f.write(f"{cg[0]:.6f}  {cg[1]:.6f}  {cg[2]:.6f}\n")

        print(f"Generated mass file: {filepath}")
        return filepath

    def generate_run_file(
        self, config: AVLConfiguration, filename: str = "ntop_runs.run"
    ) -> Path:
        """Generate AVL run cases file for batch execution.

        Args:
            config: AVL configuration
            filename: Output filename

        Returns:
            Path to generated run file
        """
        filepath = self.output_dir / filename

        # Generate alpha sweep values
        alpha_values = np.linspace(*config.alpha_range)

        with open(filepath, "w") as f:
            f.write("# AVL Run Cases - Alpha Sweep\n")
            f.write("# Generated for nTop wing analysis\n\n")

            for i, alpha in enumerate(alpha_values, 1):
                f.write(f" ---------------------------------------------\n")
                f.write(f" Run case  {i}:   Alpha = {alpha:.2f} deg\n\n")
                f.write(f" alpha        ->  alpha       =   {alpha:.4f}\n")
                f.write(f" beta         ->  beta        =   0.0000\n")
                f.write(f" pb/2V        ->  pb/2V       =   0.0000\n")
                f.write(f" qc/2V        ->  qc/2V       =   0.0000\n")
                f.write(f" rb/2V        ->  rb/2V       =   0.0000\n\n")

        print(f"Generated run file: {filepath}")
        return filepath

    def run_avl_batch(
        self,
        config: AVLConfiguration,
        avl_file: str | Path = None,
        mass_file: str | Path = None,
    ) -> pd.DataFrame:
        """Run AVL batch analysis.

        Args:
            config: AVL configuration
            avl_file: Path to AVL geometry file (default: use generated)
            mass_file: Path to AVL mass file (default: use generated)

        Returns:
            DataFrame with aerodynamic coefficients and derivatives
        """
        # Generate files if not provided
        if avl_file is None:
            avl_file = self.generate_avl_file()
        if mass_file is None:
            mass_file = self.generate_mass_file()

        # Generate AVL batch commands
        commands_file = self.output_dir / "avl_commands.txt"
        results_file = self.output_dir / "avl_results.txt"

        # Generate alpha sweep values
        alpha_values = np.linspace(*config.alpha_range)

        # Prepare results storage
        results = []

        for alpha in alpha_values:
            # Create command file for this alpha
            with open(commands_file, "w") as f:
                f.write(f"LOAD {avl_file}\n")
                f.write(f"MASS {mass_file}\n")
                f.write(f"OPER\n")
                f.write(f"A\n")
                f.write(f"A {alpha}\n")
                f.write(f"X\n")
                f.write(f"ST\n")
                f.write(f"{results_file}\n")
                f.write(f"\n")
                f.write(f"QUIT\n")

            # Run AVL
            try:
                with open(commands_file, "r") as cmd_in:
                    result = subprocess.run(
                        [self.avl_executable],
                        stdin=cmd_in,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                # Parse results
                coeffs = self._parse_avl_results(results_file, alpha)
                if coeffs:
                    results.append(coeffs)

            except Exception as e:
                print(f"Error running AVL at alpha={alpha:.2f}: {e}")

        # Convert to DataFrame
        if results:
            df = pd.DataFrame(results)
            output_csv = self.output_dir / "avl_coefficients.csv"
            df.to_csv(output_csv, index=False)
            print(f"Saved AVL results to: {output_csv}")
            return df
        else:
            print("No results generated from AVL")
            return pd.DataFrame()

    def _parse_avl_results(
        self, results_file: Path, alpha: float
    ) -> dict[str, float]:
        """Parse AVL results file.

        Args:
            results_file: Path to AVL stability derivatives output
            alpha: Angle of attack

        Returns:
            Dictionary of coefficients
        """
        # This is a simplified parser - actual parsing depends on AVL output format
        # Placeholder for now - would need to parse actual AVL output
        return {
            "alpha": alpha,
            "CL": 0.0,  # To be parsed
            "CD": 0.0,
            "Cm": 0.0,
            "CLa": 0.0,
            "Cma": 0.0,
        }


if __name__ == "__main__":
    from geometry import load_ntop_data

    # Load nTop data
    data_dir = Path(__file__).parent / "data"
    wing, mass = load_ntop_data(data_dir)

    # Create AVL interface
    output_dir = Path(__file__).parent / "data" / "generated"
    avl = AVLInterface(wing, mass, output_dir)

    # Generate AVL files
    avl_file = avl.generate_avl_file()
    mass_file = avl.generate_mass_file()
    run_file = avl.generate_run_file(AVLConfiguration())

    print(f"\nGenerated files in: {output_dir}")
    print("  - ntop_wing.avl (geometry)")
    print("  - ntop_wing.mass (mass properties)")
    print("  - ntop_runs.run (run cases)")
    print("\nTo run AVL:")
    print(f"  cd {output_dir}")
    print("  avl ntop_wing.avl")
