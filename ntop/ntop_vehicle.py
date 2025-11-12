# SPDX-FileCopyrightText: 2025 nTop Integration
# SPDX-License-Identifier: GPL-3.0-or-later

"""nTop vehicle configuration for Archimedes 6-DOF simulation.

This module defines the complete vehicle model integrating nTop geometry,
mass properties, and aerodynamics with the Archimedes simulation framework.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import archimedes as arc
from archimedes import field, struct
from archimedes.experimental.aero import ConstantGravity
from archimedes.experimental.aero.atmosphere_us import StandardAtmosphere1976
from archimedes.spatial import RigidBody

from aero_deck import AeroDeck
from geometry import load_ntop_data
from ntop_aero import FlightCondition, NTopAero

GRAV_FTS2 = 32.17  # ft/s^2


@struct
class NTopVehicleGeometry:
    """nTop vehicle geometric parameters."""

    S: float  # Reference area [ft²]
    b: float  # Wing span [ft]
    cbar: float  # Mean aerodynamic chord [ft]
    AR: float  # Aspect ratio
    xcgr: float = 0.25  # Reference CG location (% of cbar)


@struct
class NTopVehicle:
    """Complete nTop vehicle model for 6-DOF simulation.

    This integrates:
    - Mass properties from nTop export
    - Wing geometry from nTop export
    - Aerodynamics from AVL/XFOIL analysis
    - Standard atmosphere and gravity models
    """

    # Required fields (no defaults)
    aero: NTopAero
    geometry: NTopVehicleGeometry
    m: float  # Vehicle mass [slug]
    J_B: np.ndarray  # Inertia matrix [slug·ft²] - shape (3, 3)

    # Optional fields (with defaults)
    gravity: ConstantGravity = field(default_factory=lambda: ConstantGravity(GRAV_FTS2))
    atmos: StandardAtmosphere1976 = field(default_factory=StandardAtmosphere1976)
    xcg: float = 0.25  # CG location (% of cbar)
    max_thrust: float = 1000.0  # Maximum thrust [lbf]

    @struct
    class State(RigidBody.State):
        """Vehicle state."""

        aero: NTopAero.State = field(default_factory=NTopAero.State)
        throttle: float = 0.0  # Throttle setting [0-1]

    @struct
    class Input:
        """Vehicle control inputs."""

        throttle: float  # Throttle command [0-1]
        elevator: float  # Elevator deflection [deg]
        aileron: float  # Aileron deflection [deg]
        rudder: float  # Rudder deflection [deg]

    def calc_gravity(self, x: State) -> np.ndarray:
        """Calculate gravity force in body frame.

        Args:
            x: Vehicle state

        Returns:
            Gravity force in body frame [lbf]
        """
        F_grav_N = self.m * self.gravity(x.pos)
        R_BN = x.att.as_matrix()
        F_grav_B = R_BN @ F_grav_N
        return F_grav_B

    def flight_condition(self, x: State) -> FlightCondition:
        """Compute current flight condition from state.

        Args:
            x: Vehicle state

        Returns:
            FlightCondition object
        """
        from archimedes.experimental.aero import wind_frame

        vt, alpha, beta = wind_frame(x.v_B)

        # Altitude (negative z in NED frame)
        alt = -x.pos[2]

        # Atmosphere properties
        mach, qbar = self.atmos(vt, alt)

        return FlightCondition(
            vt=vt,
            alpha=alpha,
            beta=beta,
            mach=mach,
            qbar=qbar,
            alt=alt,
        )

    def dynamics(self, t: float, x: State, u: Input) -> State:
        """Compute state time derivative.

        Args:
            t: Time [s]
            x: Vehicle state
            u: Control inputs

        Returns:
            State derivative
        """
        # Compute flight condition
        condition = self.flight_condition(x)

        # === Engine thrust ===
        thrust = u.throttle * self.max_thrust
        F_eng_B = np.hstack([thrust, 0.0, 0.0])
        M_eng_B = np.zeros(3)  # No engine moments for now

        # === Aerodynamics ===
        aero_input = self.aero.Input(
            condition=condition,
            w_B=x.w_B,
            elevator=u.elevator,
            aileron=u.aileron,
            rudder=u.rudder,
            xcg=self.xcg,
        )
        aero_output = self.aero.output(t, x.aero, aero_input)

        # Convert coefficients to forces/moments
        cxt, cyt, czt = aero_output.CF_B
        clt, cmt, cnt = aero_output.CM_B

        S = self.geometry.S
        b = self.geometry.b
        cbar = self.geometry.cbar

        F_aero_B = condition.qbar * S * np.stack([cxt, cyt, czt])
        M_aero_B = condition.qbar * S * np.hstack([b * clt, cbar * cmt, b * cnt])

        # === Gravity ===
        F_grav_B = self.calc_gravity(x)

        # === Net forces and moments ===
        F_B = F_aero_B + F_eng_B + F_grav_B
        M_B = M_aero_B + M_eng_B

        # Rigid body dynamics
        rb_input = RigidBody.Input(
            F_B=F_B,
            M_B=M_B,
            m=self.m,
            J_B=self.J_B,
        )
        rb_deriv = RigidBody.dynamics(t, x, rb_input)

        # Aerodynamic state derivative (quasi-steady: zero)
        aero_deriv = self.aero.dynamics(t, x.aero, aero_input)

        return self.State(
            pos=rb_deriv.pos,
            att=rb_deriv.att,
            v_B=rb_deriv.v_B,
            w_B=rb_deriv.w_B,
            aero=aero_deriv,
            throttle=u.throttle,
        )

    @classmethod
    def from_ntop_data(
        cls,
        data_dir: str | Path,
        aero_deck_file: str | Path = None,
        max_thrust: float = 1000.0,
    ) -> NTopVehicle:
        """Create vehicle model from nTop data files.

        Args:
            data_dir: Directory containing nTop CSV files
            aero_deck_file: Path to aero deck file (default: generated/ntop_aero_deck.npz)
            max_thrust: Maximum engine thrust [lbf]

        Returns:
            NTopVehicle instance
        """
        # Load geometry and mass properties
        wing_geometry, mass_properties = load_ntop_data(data_dir)

        # Load aero deck
        if aero_deck_file is None:
            aero_deck_file = Path(data_dir) / "generated" / "ntop_aero_deck.npz"
        aero_deck = AeroDeck.load(aero_deck_file)

        # Create aero model
        aero_model = NTopAero(aero_deck, wing_geometry)

        # Create geometry struct
        geometry = NTopVehicleGeometry(
            S=wing_geometry.reference_area,
            b=wing_geometry.span,
            cbar=wing_geometry.mean_chord,
            AR=wing_geometry.aspect_ratio,
        )

        return cls(
            aero=aero_model,
            geometry=geometry,
            m=mass_properties.mass,
            J_B=mass_properties.inertia,
            max_thrust=max_thrust,
        )


if __name__ == "__main__":
    # Create vehicle from nTop data
    data_dir = Path(__file__).parent / "data"

    print("Loading nTop vehicle configuration...")
    vehicle = NTopVehicle.from_ntop_data(data_dir, max_thrust=2000.0)

    print("\nVehicle Configuration:")
    print(f"  Mass: {vehicle.m:.2f} slug ({vehicle.m * GRAV_FTS2:.1f} lbf)")
    print(f"  Reference area: {vehicle.geometry.S:.2f} ft²")
    print(f"  Wing span: {vehicle.geometry.b:.2f} ft")
    print(f"  Mean chord: {vehicle.geometry.cbar:.2f} ft")
    print(f"  Aspect ratio: {vehicle.geometry.AR:.2f}")
    print(f"  Max thrust: {vehicle.max_thrust:.1f} lbf")
    print(f"\nInertia matrix [slug·ft²]:")
    print(vehicle.J_B)
