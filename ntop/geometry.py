# SPDX-FileCopyrightText: 2025 nTop Integration
# SPDX-License-Identifier: GPL-3.0-or-later

"""Geometry processing for nTop exported data.

This module loads and processes wing geometry data exported from nTop,
converting it to formats suitable for AVL and XFOIL analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class MassProperties:
    """Mass properties from nTop export."""

    mass: float  # Mass [slug] - converted from nTop
    cg: np.ndarray  # Center of gravity [ft] - shape (3,)
    inertia: np.ndarray  # Inertia tensor [slug·ft²] - shape (3, 3)

    @classmethod
    def from_csv(cls, filepath: str | Path) -> MassProperties:
        """Load mass properties from nTop CSV export.

        Args:
            filepath: Path to mass.csv file

        Returns:
            MassProperties object with values in imperial units
        """
        df = pd.read_csv(filepath)

        # Extract values (nTop exports in specific column order)
        mass_lbf = df["avl_mass"].values[0]  # Force [lbf]
        cg_x = df["avl_CGx"].values[0]  # inches
        cg_y = df["avl_CGy"].values[0]  # inches
        cg_z = df["avl_CGz"].values[0]  # inches
        Ixx = df["avl_Ixx"].values[0]  # lbf·in²
        Iyy = df["avl_Iyy"].values[0]  # lbf·in²
        Izz = df["avl_Izz"].values[0]  # lbf·in²

        # Convert to imperial units used in Archimedes
        GRAV_FTS2 = 32.17  # ft/s²
        IN_TO_FT = 1.0 / 12.0

        mass_slug = mass_lbf / GRAV_FTS2
        cg_ft = np.array([cg_x, cg_y, cg_z]) * IN_TO_FT

        # Convert inertia: lbf·in² -> slug·ft²
        # I[slug·ft²] = I[lbf·in²] / g[ft/s²] * (1/12)²
        inertia_conversion = (IN_TO_FT**2) / GRAV_FTS2
        inertia_slug_ft2 = np.array(
            [[Ixx, 0.0, 0.0], [0.0, Iyy, 0.0], [0.0, 0.0, Izz]]
        ) * inertia_conversion

        return cls(mass=mass_slug, cg=cg_ft, inertia=inertia_slug_ft2)


@dataclass
class WingSection:
    """A single wing section defined by LE and TE points."""

    y_station: float  # Spanwise station [ft]
    le_point: np.ndarray  # Leading edge (x, y, z) [ft]
    te_point: np.ndarray  # Trailing edge (x, y, z) [ft]
    chord: float  # Local chord length [ft]

    @property
    def quarter_chord(self) -> np.ndarray:
        """Quarter-chord point."""
        return self.le_point + 0.25 * (self.te_point - self.le_point)

    @property
    def mid_chord(self) -> np.ndarray:
        """Mid-chord point."""
        return 0.5 * (self.le_point + self.te_point)


@dataclass
class WingGeometry:
    """Complete wing geometry from nTop export."""

    sections: list[WingSection]  # Wing sections from root to tip
    reference_area: float  # Reference area [ft²]
    span: float  # Wing span [ft]
    mean_chord: float  # Mean aerodynamic chord [ft]
    aspect_ratio: float  # Aspect ratio

    @classmethod
    def from_csv(
        cls, le_filepath: str | Path, te_filepath: str | Path
    ) -> WingGeometry:
        """Load wing geometry from nTop CSV exports.

        Args:
            le_filepath: Path to LEpts.csv file
            te_filepath: Path to TEpts.csv file

        Returns:
            WingGeometry object with computed geometric properties
        """
        # Load CSV files
        le_df = pd.read_csv(le_filepath)
        te_df = pd.read_csv(te_filepath)

        # Convert from inches to feet
        IN_TO_FT = 1.0 / 12.0
        le_points = le_df[["x", "y", "z"]].values * IN_TO_FT
        te_points = te_df[["x", "y", "z"]].values * IN_TO_FT

        # Create wing sections
        sections = []
        for le_pt, te_pt in zip(le_points, te_points):
            y_station = le_pt[1]  # y-coordinate
            chord = np.linalg.norm(te_pt - le_pt)
            section = WingSection(
                y_station=y_station,
                le_point=le_pt,
                te_point=te_pt,
                chord=chord,
            )
            sections.append(section)

        # Sort sections by spanwise station (should already be sorted)
        sections.sort(key=lambda s: abs(s.y_station))

        # Compute geometric properties
        span = cls._compute_span(sections)
        reference_area = cls._compute_reference_area(sections)
        mean_chord = cls._compute_mean_chord(sections, reference_area)
        aspect_ratio = span**2 / reference_area if reference_area > 0 else 0.0

        return cls(
            sections=sections,
            reference_area=reference_area,
            span=span,
            mean_chord=mean_chord,
            aspect_ratio=aspect_ratio,
        )

    @staticmethod
    def _compute_span(sections: list[WingSection]) -> float:
        """Compute total wing span."""
        y_stations = [s.y_station for s in sections]
        return max(y_stations) - min(y_stations)

    @staticmethod
    def _compute_reference_area(sections: list[WingSection]) -> float:
        """Compute reference area using trapezoidal rule."""
        # Sort sections by y-station
        sorted_sections = sorted(sections, key=lambda s: s.y_station)

        area = 0.0
        for i in range(len(sorted_sections) - 1):
            s1 = sorted_sections[i]
            s2 = sorted_sections[i + 1]
            dy = abs(s2.y_station - s1.y_station)
            avg_chord = 0.5 * (s1.chord + s2.chord)
            area += avg_chord * dy

        return area

    @staticmethod
    def _compute_mean_chord(
        sections: list[WingSection], reference_area: float
    ) -> float:
        """Compute mean aerodynamic chord (MAC).

        This is a simplified calculation using the reference area.
        For more accurate MAC, would need integration of c² over span.
        """
        sorted_sections = sorted(sections, key=lambda s: s.y_station)
        y_stations = [s.y_station for s in sections]
        span = max(y_stations) - min(y_stations)

        if span > 0:
            return reference_area / span
        return 0.0

    def get_section_at_station(self, y: float) -> WingSection:
        """Get wing section at specified spanwise station (interpolated)."""
        sorted_sections = sorted(self.sections, key=lambda s: s.y_station)
        y_stations = [s.y_station for s in sorted_sections]

        # Find bounding sections
        for i in range(len(sorted_sections) - 1):
            if y_stations[i] <= y <= y_stations[i + 1]:
                s1 = sorted_sections[i]
                s2 = sorted_sections[i + 1]

                # Linear interpolation
                t = (y - y_stations[i]) / (y_stations[i + 1] - y_stations[i])
                le_point = (1 - t) * s1.le_point + t * s2.le_point
                te_point = (1 - t) * s1.te_point + t * s2.te_point
                chord = np.linalg.norm(te_point - le_point)

                return WingSection(
                    y_station=y,
                    le_point=le_point,
                    te_point=te_point,
                    chord=chord,
                )

        # If outside range, return nearest section
        if y < y_stations[0]:
            return sorted_sections[0]
        return sorted_sections[-1]

    def extract_airfoil_coordinates(
        self, section: WingSection, n_points: int = 100
    ) -> np.ndarray:
        """Extract airfoil coordinates at a wing section.

        For now, assumes a simple straight line from LE to TE.
        In practice, you'd want to extract actual airfoil shape from nTop.

        Args:
            section: Wing section
            n_points: Number of points to generate

        Returns:
            Array of (x, z) coordinates normalized by chord, shape (n_points, 2)
        """
        # Simple placeholder: straight line (would need actual airfoil data)
        # Normalized coordinates (x/c, z/c)
        x = np.linspace(0, 1, n_points)
        z = np.zeros_like(x)  # Flat plate for now

        return np.column_stack([x, z])

    def summary(self) -> str:
        """Generate a summary string of the wing geometry."""
        lines = [
            "Wing Geometry Summary",
            "=" * 50,
            f"Number of sections: {len(self.sections)}",
            f"Wing span: {self.span:.3f} ft",
            f"Reference area: {self.reference_area:.3f} ft²",
            f"Mean aerodynamic chord: {self.mean_chord:.3f} ft",
            f"Aspect ratio: {self.aspect_ratio:.3f}",
            "",
            "Section Details:",
        ]

        for i, section in enumerate(self.sections):
            lines.append(
                f"  Section {i}: y={section.y_station:.3f} ft, "
                f"chord={section.chord:.3f} ft"
            )

        return "\n".join(lines)


def load_ntop_data(data_dir: str | Path) -> tuple[WingGeometry, MassProperties]:
    """Load all nTop exported data.

    Args:
        data_dir: Path to directory containing LEpts.csv, TEpts.csv, mass.csv

    Returns:
        Tuple of (WingGeometry, MassProperties)
    """
    data_dir = Path(data_dir)

    wing_geometry = WingGeometry.from_csv(
        le_filepath=data_dir / "LEpts.csv",
        te_filepath=data_dir / "TEpts.csv",
    )

    mass_properties = MassProperties.from_csv(filepath=data_dir / "mass.csv")

    return wing_geometry, mass_properties


if __name__ == "__main__":
    # Test loading
    import sys

    if len(sys.argv) > 1:
        data_dir = sys.argv[1]
    else:
        # Default to ntop/data directory
        data_dir = Path(__file__).parent / "data"

    wing, mass = load_ntop_data(data_dir)

    print(wing.summary())
    print()
    print("Mass Properties:")
    print(f"  Mass: {mass.mass:.3f} slug")
    print(f"  CG: {mass.cg}")
    print(f"  Inertia:\n{mass.inertia}")
