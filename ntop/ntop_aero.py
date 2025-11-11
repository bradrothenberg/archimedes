# SPDX-FileCopyrightText: 2025 nTop Integration
# SPDX-License-Identifier: GPL-3.0-or-later

"""nTop aerodynamics model for Archimedes 6-DOF simulation.

This module implements a custom aerodynamics model that uses the aero deck
generated from AVL and XFOIL analyses of the nTop wing geometry.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import archimedes as arc
from archimedes import struct
from archimedes.experimental.aero import wind_frame

from aero_deck import AeroDeck

if TYPE_CHECKING:
    from geometry import WingGeometry


@struct
class FlightCondition:
    """Flight condition state."""

    alt: float  # Altitude [ft]
    vt: float  # True airspeed [ft/s]
    alpha: float  # Angle of attack [rad]
    beta: float  # Sideslip angle [rad]
    mach: float  # Mach number
    qbar: float  # Dynamic pressure [lbf/ft²]


@struct
class NTopAeroInput:
    """Input to nTop aerodynamics model."""

    condition: FlightCondition  # Flight condition
    w_B: np.ndarray  # Angular velocity in body frame (ω_B) [rad/s]
    elevator: float  # Elevator deflection [deg]
    aileron: float  # Aileron deflection [deg]
    rudder: float  # Rudder deflection [deg]
    xcg: float  # Longitudinal center of gravity [% of cbar]


@struct
class NTopAeroOutput:
    """Output from nTop aerodynamics model."""

    CF_B: np.ndarray  # Aerodynamic force coefficients in body frame
    CM_B: np.ndarray  # Aerodynamic moment coefficients in body frame


@struct
class NTopAeroState:
    """Aerodynamic state (empty for quasi-steady model)."""

    pass


class NTopAero:
    """Aerodynamics model for nTop wing using AVL/XFOIL data.

    This model follows the same interface as the F16Aero models in Archimedes,
    allowing it to be used as a drop-in replacement.
    """

    Input = NTopAeroInput
    Output = NTopAeroOutput
    State = NTopAeroState

    def __init__(
        self,
        aero_deck: AeroDeck,
        wing_geometry: WingGeometry,
    ):
        """Initialize nTop aero model.

        Args:
            aero_deck: Aerodynamic coefficient database
            wing_geometry: Wing geometry for reference parameters
        """
        self.aero_deck = aero_deck
        self.wing_geometry = wing_geometry

        # Create interpolants for all coefficients
        self._create_interpolants()

        # Reference CG for moment corrections (fraction of MAC)
        self.xcgr = 0.25  # Default to quarter-chord

    def _create_interpolants(self):
        """Create Archimedes interpolants for all aero coefficients."""
        deck = self.aero_deck

        # Force coefficients
        self.cx_interp = arc.interpolant(
            [deck.alpha_vector, deck.elevator_vector], deck.cx_data
        )
        self.cy_interp = arc.interpolant([deck.beta_vector], deck.cy_data)
        self.cz_interp = arc.interpolant([deck.alpha_vector], deck.cz_data)

        # Moment coefficients
        self.cl_interp = arc.interpolant(
            [deck.alpha_vector, deck.beta_vector], deck.cl_data
        )
        self.cm_interp = arc.interpolant(
            [deck.alpha_vector, deck.elevator_vector], deck.cm_data
        )
        self.cn_interp = arc.interpolant(
            [deck.alpha_vector, deck.beta_vector], deck.cn_data
        )

        # Damping derivatives
        self.cxq_interp = arc.interpolant([deck.alpha_vector], deck.cxq_data)
        self.cyp_interp = arc.interpolant([deck.alpha_vector], deck.cyp_data)
        self.cyr_interp = arc.interpolant([deck.alpha_vector], deck.cyr_data)
        self.czq_interp = arc.interpolant([deck.alpha_vector], deck.czq_data)
        self.clp_interp = arc.interpolant([deck.alpha_vector], deck.clp_data)
        self.clr_interp = arc.interpolant([deck.alpha_vector], deck.clr_data)
        self.cmq_interp = arc.interpolant([deck.alpha_vector], deck.cmq_data)
        self.cnp_interp = arc.interpolant([deck.alpha_vector], deck.cnp_data)
        self.cnr_interp = arc.interpolant([deck.alpha_vector], deck.cnr_data)

        # Control derivatives
        self.dlda_interp = arc.interpolant(
            [deck.alpha_vector, deck.beta_vector], deck.dlda_data
        )
        self.dldr_interp = arc.interpolant(
            [deck.alpha_vector, deck.beta_vector], deck.dldr_data
        )
        self.dnda_interp = arc.interpolant(
            [deck.alpha_vector, deck.beta_vector], deck.dnda_data
        )
        self.dndr_interp = arc.interpolant(
            [deck.alpha_vector, deck.beta_vector], deck.dndr_data
        )

    def dynamics(self, t: float, x: State, u: Input) -> State:
        """Compute aerodynamic state derivative (quasi-steady: zero)."""
        return x

    def output(self, t: float, x: State, u: Input) -> Output:
        """Compute aerodynamic force and moment coefficients.

        Args:
            t: Time [s]
            x: Aerodynamic state
            u: Input (flight condition, rates, control deflections)

        Returns:
            Output with force and moment coefficients in body frame
        """
        # Extract flight condition
        vt = u.condition.vt  # True airspeed [ft/s]
        alpha = u.condition.alpha  # Angle of attack [rad]
        beta = u.condition.beta  # Sideslip angle [rad]
        p, q, r = u.w_B  # Angular velocity in body frame (ω_B) [rad/s]

        # Convert to degrees for table lookup
        alpha_deg = np.rad2deg(alpha)
        beta_deg = np.rad2deg(beta)

        # Lookup base coefficients
        cxt = self.cx_interp(alpha_deg, u.elevator)
        cyt = self.cy_interp(beta_deg)
        czt = self.cz_interp(alpha_deg)

        # Control surface effects on moments
        dail = u.aileron / 20.0  # Normalized aileron deflection
        drdr = u.rudder / 30.0  # Normalized rudder deflection

        clt = (
            self.cl_interp(alpha_deg, beta_deg)
            + self.dlda_interp(alpha_deg, beta_deg) * dail
            + self.dldr_interp(alpha_deg, beta_deg) * drdr
        )

        cmt = self.cm_interp(alpha_deg, u.elevator)

        cnt = (
            self.cn_interp(alpha_deg, beta_deg)
            + self.dnda_interp(alpha_deg, beta_deg) * dail
            + self.dndr_interp(alpha_deg, beta_deg) * drdr
        )

        # Add damping derivatives
        tvt = 0.5 / vt  # Time scale factor
        b2v = self.wing_geometry.span * tvt
        cq = self.wing_geometry.mean_chord * q * tvt

        # Force coefficient damping
        cxt = cxt + cq * self.cxq_interp(alpha_deg)
        cyt = cyt + b2v * (
            self.cyr_interp(alpha_deg) * r + self.cyp_interp(alpha_deg) * p
        )
        czt = czt + cq * self.czq_interp(alpha_deg)

        # Moment coefficient damping
        clt = clt + b2v * (
            self.clr_interp(alpha_deg) * r + self.clp_interp(alpha_deg) * p
        )

        # Pitch moment with CG correction
        cmt = cmt + cq * self.cmq_interp(alpha_deg)
        cmt = cmt + czt * (self.xcgr - u.xcg)

        # Yaw moment with CG correction
        cnt = cnt + b2v * (
            self.cnr_interp(alpha_deg) * r + self.cnp_interp(alpha_deg) * p
        )
        cnt = (
            cnt
            - cyt
            * (self.xcgr - u.xcg)
            * self.wing_geometry.mean_chord
            / self.wing_geometry.span
        )

        # Assemble output
        CF_B = np.hstack([cxt, cyt, czt])
        CM_B = np.hstack([clt, cmt, cnt])

        return self.Output(CF_B=CF_B, CM_B=CM_B)

    def trim(self) -> State:
        """Return steady aerodynamic state (empty for quasi-steady model)."""
        return self.State()

    @classmethod
    def from_files(
        cls,
        aero_deck_file: str | Path,
        geometry_data_dir: str | Path,
    ) -> NTopAero:
        """Load nTop aero model from files.

        Args:
            aero_deck_file: Path to aero deck NPZ file
            geometry_data_dir: Path to nTop geometry data directory

        Returns:
            NTopAero instance
        """
        from geometry import load_ntop_data

        # Load aero deck
        aero_deck = AeroDeck.load(aero_deck_file)

        # Load wing geometry
        wing_geometry, _ = load_ntop_data(geometry_data_dir)

        return cls(aero_deck, wing_geometry)


if __name__ == "__main__":
    from geometry import load_ntop_data

    # Load data
    data_dir = Path(__file__).parent / "data"
    wing_geometry, mass_properties = load_ntop_data(data_dir)

    aero_deck_file = data_dir / "generated" / "ntop_aero_deck.npz"
    aero_deck = AeroDeck.load(aero_deck_file)

    # Create aero model
    ntop_aero = NTopAero(aero_deck, wing_geometry)

    print("nTop Aero Model initialized")
    print(f"  Reference area: {wing_geometry.reference_area:.2f} ft²")
    print(f"  Wing span: {wing_geometry.span:.2f} ft")
    print(f"  Mean chord: {wing_geometry.mean_chord:.2f} ft")
    print(f"  Aspect ratio: {wing_geometry.aspect_ratio:.2f}")

    # Test evaluation at a sample condition
    test_input = NTopAeroInput(
        condition=FlightCondition(
            alt=20000.0,
            vt=550.0,
            alpha=np.deg2rad(5.0),
            beta=np.deg2rad(0.0),
            mach=0.5,
            qbar=150.0,
        ),
        w_B=np.array([0.0, 0.0, 0.0]),
        elevator=0.0,
        aileron=0.0,
        rudder=0.0,
        xcg=0.25,
    )

    test_state = NTopAeroState()
    output = ntop_aero.output(0.0, test_state, test_input)

    print("\nTest evaluation at alpha=5°, beta=0°:")
    print(f"  Force coefficients (Cx, Cy, Cz): {output.CF_B}")
    print(f"  Moment coefficients (Cl, Cm, Cn): {output.CM_B}")
