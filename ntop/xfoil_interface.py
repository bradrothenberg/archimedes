# SPDX-FileCopyrightText: 2025 nTop Integration
# SPDX-License-Identifier: GPL-3.0-or-later

"""XFOIL interface for 2D airfoil viscous analysis.

This module runs XFOIL analyses to compute airfoil section properties
including viscous effects for drag polar generation.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from geometry import WingGeometry, WingSection


@dataclass
class XFOILConfiguration:
    """XFOIL analysis configuration."""

    # Reynolds number range for flight conditions
    # Mach 0.5 at 20,000 ft: Re ~ 10-15 million for typical chords
    reynolds_numbers: list[float] = None

    # Mach number
    mach: float = 0.5

    # Angle of attack range
    alpha_start: float = -10.0  # degrees
    alpha_end: float = 25.0  # degrees
    alpha_step: float = 0.5  # degrees

    # XFOIL panel parameters
    n_panels: int = 160  # Number of panels

    # Convergence parameters
    n_iter: int = 200  # Maximum iterations

    def __post_init__(self):
        """Set default Reynolds numbers if not provided."""
        if self.reynolds_numbers is None:
            # For Mach 0.5 at 20,000 ft, typical Re for various chord lengths
            # Re = rho * V * c / mu
            # At 20,000 ft: rho = 0.001267 slug/ft³, mu = 3.324e-7 slug/(ft·s)
            # V = 550 ft/s (Mach 0.5)
            self.reynolds_numbers = [
                2e6,
                5e6,
                10e6,
                15e6,
            ]  # Representative range


@dataclass
class AirfoilPolar:
    """Airfoil polar data from XFOIL."""

    reynolds_number: float
    mach: float
    alpha: np.ndarray  # Angle of attack [deg]
    cl: np.ndarray  # Lift coefficient
    cd: np.ndarray  # Drag coefficient
    cm: np.ndarray  # Moment coefficient
    cdp: np.ndarray  # Profile drag coefficient


class XFOILInterface:
    """Interface for running XFOIL analyses."""

    def __init__(
        self,
        output_dir: str | Path,
        xfoil_executable: str = "xfoil",
    ):
        """Initialize XFOIL interface.

        Args:
            output_dir: Directory for XFOIL input/output files
            xfoil_executable: Path to XFOIL executable (default: 'xfoil' in PATH)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.xfoil_executable = xfoil_executable

    def generate_airfoil_file(
        self,
        section: WingSection,
        n_points: int = 100,
        filename: str = "airfoil.dat",
    ) -> Path:
        """Generate airfoil coordinate file for XFOIL.

        Args:
            section: Wing section to extract airfoil from
            n_points: Number of points
            filename: Output filename

        Returns:
            Path to airfoil file
        """
        filepath = self.output_dir / filename

        # For now, generate NACA 0012 coordinates
        # TODO: Extract actual airfoil from nTop geometry
        with open(filepath, "w") as f:
            f.write("NACA 0012\n")

            # Generate NACA 0012 coordinates (simplified)
            x_upper = np.linspace(0, 1, n_points // 2)
            x_lower = np.linspace(1, 0, n_points // 2)

            # NACA 0012 thickness distribution
            t = 0.12  # 12% thickness
            for x in x_upper:
                y = (
                    5
                    * t
                    * (
                        0.2969 * np.sqrt(x)
                        - 0.1260 * x
                        - 0.3516 * x**2
                        + 0.2843 * x**3
                        - 0.1015 * x**4
                    )
                )
                f.write(f"{x:.6f}  {y:.6f}\n")

            for x in x_lower:
                y = (
                    -5
                    * t
                    * (
                        0.2969 * np.sqrt(x)
                        - 0.1260 * x
                        - 0.3516 * x**2
                        + 0.2843 * x**3
                        - 0.1015 * x**4
                    )
                )
                f.write(f"{x:.6f}  {y:.6f}\n")

        return filepath

    def run_xfoil_polar(
        self,
        airfoil_file: Path,
        config: XFOILConfiguration,
        reynolds_number: float,
    ) -> AirfoilPolar | None:
        """Run XFOIL polar analysis at specified Reynolds number.

        Args:
            airfoil_file: Path to airfoil coordinates file
            config: XFOIL configuration
            reynolds_number: Reynolds number for analysis

        Returns:
            AirfoilPolar object with results, or None if failed
        """
        # Output file for polar data
        polar_file = self.output_dir / f"polar_re{reynolds_number:.0e}.txt"

        # Generate XFOIL command file
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".txt"
        ) as cmd_file:
            cmd_file.write(f"LOAD {airfoil_file}\n")
            cmd_file.write("\n")  # Accept default name
            cmd_file.write("PANE\n")  # Generate panels
            cmd_file.write("OPER\n")  # Enter OPER menu
            cmd_file.write(f"VISC {reynolds_number:.0f}\n")  # Set Reynolds number
            cmd_file.write(f"MACH {config.mach}\n")  # Set Mach number
            cmd_file.write(f"ITER {config.n_iter}\n")  # Set max iterations
            cmd_file.write("PACC\n")  # Polar accumulation
            cmd_file.write(f"{polar_file}\n")  # Polar save file
            cmd_file.write("\n")  # Polar dump file (none)

            # Alpha sequence
            cmd_file.write(
                f"ASEQ {config.alpha_start} {config.alpha_end} {config.alpha_step}\n"
            )

            cmd_file.write("PACC\n")  # End polar accumulation
            cmd_file.write("\n")  # Quit OPER
            cmd_file.write("QUIT\n")  # Quit XFOIL

            cmd_filename = cmd_file.name

        # Run XFOIL
        try:
            with open(cmd_filename, "r") as cmd_in:
                result = subprocess.run(
                    [self.xfoil_executable],
                    stdin=cmd_in,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

            # Parse results
            if polar_file.exists():
                polar = self._parse_xfoil_polar(
                    polar_file, reynolds_number, config.mach
                )
                print(
                    f"XFOIL completed for Re={reynolds_number:.2e}, "
                    f"{len(polar.alpha) if polar else 0} points"
                )
                return polar
            else:
                print(f"XFOIL polar file not generated for Re={reynolds_number:.2e}")
                return None

        except Exception as e:
            print(f"Error running XFOIL at Re={reynolds_number:.2e}: {e}")
            return None
        finally:
            # Clean up command file
            Path(cmd_filename).unlink(missing_ok=True)

    def _parse_xfoil_polar(
        self, polar_file: Path, reynolds_number: float, mach: float
    ) -> AirfoilPolar | None:
        """Parse XFOIL polar output file.

        Args:
            polar_file: Path to XFOIL polar file
            reynolds_number: Reynolds number
            mach: Mach number

        Returns:
            AirfoilPolar object or None if parsing failed
        """
        try:
            # Read XFOIL polar file (skip header lines)
            with open(polar_file, "r") as f:
                lines = f.readlines()

            # Find start of data (after header)
            data_start = 0
            for i, line in enumerate(lines):
                if "alpha" in line.lower() and "CL" in line:
                    data_start = i + 2  # Skip header and dashes
                    break

            # Parse data
            data = []
            for line in lines[data_start:]:
                if line.strip():
                    try:
                        values = line.split()
                        if len(values) >= 7:
                            alpha = float(values[0])
                            cl = float(values[1])
                            cd = float(values[2])
                            cdp = float(values[3])
                            cm = float(values[4])
                            data.append([alpha, cl, cd, cdp, cm])
                    except ValueError:
                        continue

            if not data:
                return None

            data = np.array(data)
            return AirfoilPolar(
                reynolds_number=reynolds_number,
                mach=mach,
                alpha=data[:, 0],
                cl=data[:, 1],
                cd=data[:, 2],
                cdp=data[:, 3],
                cm=data[:, 4],
            )

        except Exception as e:
            print(f"Error parsing XFOIL polar: {e}")
            return None

    def run_section_analysis(
        self,
        wing_geometry: WingGeometry,
        config: XFOILConfiguration,
        stations: list[float] = None,
    ) -> dict[float, list[AirfoilPolar]]:
        """Run XFOIL analysis for multiple wing sections.

        Args:
            wing_geometry: Wing geometry
            config: XFOIL configuration
            stations: List of spanwise stations [ft] (default: use geometry sections)

        Returns:
            Dictionary mapping station -> list of polars (one per Re)
        """
        if stations is None:
            # Use existing section y-stations
            stations = [s.y_station for s in wing_geometry.sections]

        results = {}

        for station in stations:
            print(f"\nAnalyzing station y={station:.3f} ft")
            section = wing_geometry.get_section_at_station(station)

            # Generate airfoil file
            airfoil_file = self.generate_airfoil_file(
                section, filename=f"airfoil_y{abs(station):.2f}.dat"
            )

            # Run analysis for each Reynolds number
            polars = []
            for re in config.reynolds_numbers:
                polar = self.run_xfoil_polar(airfoil_file, config, re)
                if polar is not None:
                    polars.append(polar)

            if polars:
                results[station] = polars

        # Save summary
        self._save_summary(results)

        return results

    def _save_summary(self, results: dict[float, list[AirfoilPolar]]):
        """Save summary of XFOIL results to CSV."""
        summary_data = []

        for station, polars in results.items():
            for polar in polars:
                for i in range(len(polar.alpha)):
                    summary_data.append(
                        {
                            "station": station,
                            "Re": polar.reynolds_number,
                            "Mach": polar.mach,
                            "alpha": polar.alpha[i],
                            "cl": polar.cl[i],
                            "cd": polar.cd[i],
                            "cdp": polar.cdp[i],
                            "cm": polar.cm[i],
                        }
                    )

        if summary_data:
            df = pd.DataFrame(summary_data)
            output_file = self.output_dir / "xfoil_summary.csv"
            df.to_csv(output_file, index=False)
            print(f"\nSaved XFOIL summary to: {output_file}")


if __name__ == "__main__":
    from geometry import load_ntop_data

    # Load nTop data
    data_dir = Path(__file__).parent / "data"
    wing, mass = load_ntop_data(data_dir)

    # Create XFOIL interface
    output_dir = Path(__file__).parent / "data" / "generated"
    xfoil = XFOILInterface(output_dir)

    # Run analysis for a few representative sections
    config = XFOILConfiguration()

    print("\nXFOIL Analysis Configuration:")
    print(f"  Mach: {config.mach}")
    print(f"  Reynolds numbers: {config.reynolds_numbers}")
    print(f"  Alpha range: {config.alpha_start}° to {config.alpha_end}°")
    print(f"  Alpha step: {config.alpha_step}°")

    # Select a few representative stations
    stations = [0.0, 5.0, 10.0]  # Root, mid-span, near tip
    print(f"\nAnalyzing stations: {stations} ft")

    print("\nNote: Run with actual XFOIL executable to generate data")
    print("Example: xfoil < commands.txt")
