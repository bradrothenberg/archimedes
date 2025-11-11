# SPDX-FileCopyrightText: 2025 nTop Integration
# SPDX-License-Identifier: GPL-3.0-or-later

"""Aerodynamic deck combining AVL and XFOIL data.

This module combines inviscid 3D data from AVL with viscous 2D corrections
from XFOIL to create a complete aerodynamic database for the nTop wing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class AeroDeck:
    """Complete aerodynamic database for nTop wing.

    This combines:
    - AVL: 3D inviscid lift, induced drag, moments, stability derivatives
    - XFOIL: 2D viscous profile drag corrections
    """

    # Lookup table axes
    alpha_vector: np.ndarray  # Angle of attack [deg]
    beta_vector: np.ndarray  # Sideslip angle [deg]
    elevator_vector: np.ndarray  # Elevator deflection [deg]
    aileron_vector: np.ndarray  # Aileron deflection [deg]
    rudder_vector: np.ndarray  # Rudder deflection [deg]

    # Force coefficients (body axis)
    cx_data: np.ndarray  # Axial force coefficient
    cy_data: np.ndarray  # Side force coefficient
    cz_data: np.ndarray  # Normal force coefficient

    # Moment coefficients (body axis)
    cl_data: np.ndarray  # Rolling moment coefficient
    cm_data: np.ndarray  # Pitching moment coefficient
    cn_data: np.ndarray  # Yawing moment coefficient

    # Stability derivatives (as functions of alpha)
    cxq_data: np.ndarray  # Pitch rate derivative for Cx
    cyp_data: np.ndarray  # Roll rate derivative for Cy
    cyr_data: np.ndarray  # Yaw rate derivative for Cy
    czq_data: np.ndarray  # Pitch rate derivative for Cz
    clp_data: np.ndarray  # Roll rate derivative for Cl
    clr_data: np.ndarray  # Yaw rate derivative for Cl
    cmq_data: np.ndarray  # Pitch rate derivative for Cm
    cnp_data: np.ndarray  # Roll rate derivative for Cn
    cnr_data: np.ndarray  # Yaw rate derivative for Cn

    # Control derivatives
    dlda_data: np.ndarray  # dCl/d(aileron) as function of (alpha, beta)
    dldr_data: np.ndarray  # dCl/d(rudder) as function of (alpha, beta)
    dnda_data: np.ndarray  # dCn/d(aileron) as function of (alpha, beta)
    dndr_data: np.ndarray  # dCn/d(rudder) as function of (alpha, beta)

    @classmethod
    def generate_placeholder(cls) -> AeroDeck:
        """Generate placeholder aero deck with reasonable values.

        This creates a basic aero deck based on typical subsonic aircraft
        characteristics until actual AVL/XFOIL data is computed.
        """
        # Define axes
        alpha_vector = np.array([-10, -5, 0, 5, 10, 15, 20, 25, 30, 35, 40, 45])
        beta_vector = np.array([0, 5, 10, 15, 20, 25, 30])
        elevator_vector = np.array([-24, -12, 0, 12, 24])
        aileron_vector = np.array([-20, -10, 0, 10, 20])
        rudder_vector = np.array([-30, -15, 0, 15, 30])

        n_alpha = len(alpha_vector)
        n_beta = len(beta_vector)
        n_elev = len(elevator_vector)

        # Generate placeholder lift data (simple linear + stall)
        CL_alpha = 0.08  # per degree
        CL0 = 0.0
        alpha_stall = 15.0

        cz_data_1d = np.zeros(n_alpha)
        for i, alpha in enumerate(alpha_vector):
            if alpha < alpha_stall:
                CL = CL0 + CL_alpha * alpha
            else:
                # Post-stall: gradual reduction
                CL_max = CL0 + CL_alpha * alpha_stall
                CL = CL_max * (1.0 - 0.05 * (alpha - alpha_stall))
            cz_data_1d[i] = -CL  # Cz = -CL in body axes

        # Cx data (drag-like, function of alpha and elevator)
        cx_data = np.zeros((n_alpha, n_elev))
        for i, alpha in enumerate(alpha_vector):
            alpha_rad = np.deg2rad(alpha)
            CD0 = 0.02  # Parasite drag
            K = 0.05  # Induced drag factor
            CL = -cz_data_1d[i]
            CD = CD0 + K * CL**2
            cx_data[i, :] = -CD + 0.001 * elevator_vector  # Small elevator effect

        # Cy data (sideslip and controls)
        cy_data = np.zeros(n_beta)
        for i, beta in enumerate(beta_vector):
            cy_data[i] = -0.01 * beta  # Cy_beta ~ -0.01/deg

        # Cz already defined above as function of alpha
        cz_data = cz_data_1d

        # Rolling moment (function of alpha, beta)
        cl_data = np.zeros((n_alpha, n_beta))
        for i, alpha in enumerate(alpha_vector):
            for j, beta in enumerate(beta_vector):
                cl_data[i, j] = -0.001 * beta  # Cl_beta (dihedral effect)

        # Pitching moment (function of alpha, elevator)
        cm_data = np.zeros((n_alpha, n_elev))
        Cm_alpha = -0.02  # per degree (stable)
        Cm0 = 0.05
        for i, alpha in enumerate(alpha_vector):
            for j, elev in enumerate(elevator_vector):
                cm_data[i, j] = Cm0 + Cm_alpha * alpha - 0.015 * elev

        # Yawing moment (function of alpha, beta)
        cn_data = np.zeros((n_alpha, n_beta))
        for i, alpha in enumerate(alpha_vector):
            for j, beta in enumerate(beta_vector):
                cn_data[i, j] = 0.001 * beta  # Cn_beta (weathercock stability)

        # Damping derivatives (function of alpha)
        cxq_data = np.zeros(n_alpha)
        cyp_data = np.full(n_alpha, -0.15)
        cyr_data = np.full(n_alpha, 0.25)
        czq_data = np.full(n_alpha, -8.0)  # Cz_q
        clp_data = np.full(n_alpha, -0.4)  # Roll damping
        clr_data = np.full(n_alpha, 0.15)  # Roll due to yaw rate
        cmq_data = np.full(n_alpha, -12.0)  # Pitch damping
        cnp_data = np.full(n_alpha, -0.05)  # Yaw due to roll rate
        cnr_data = np.full(n_alpha, -0.3)  # Yaw damping

        # Control derivatives (function of alpha, beta)
        dlda_data = np.full((n_alpha, n_beta), -0.05)  # Roll due to aileron
        dldr_data = np.full((n_alpha, n_beta), 0.01)  # Roll due to rudder
        dnda_data = np.full((n_alpha, n_beta), -0.002)  # Adverse yaw
        dndr_data = np.full((n_alpha, n_beta), -0.08)  # Yaw due to rudder

        return cls(
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

    @classmethod
    def from_avl_xfoil(
        cls, avl_file: str | Path, xfoil_file: str | Path
    ) -> AeroDeck:
        """Combine AVL and XFOIL data into aero deck.

        Args:
            avl_file: Path to AVL results CSV
            xfoil_file: Path to XFOIL results CSV

        Returns:
            AeroDeck with combined data
        """
        # TODO: Implement actual data loading and combination
        # For now, return placeholder
        print("Note: Using placeholder aero deck")
        print(
            "      Run AVL and XFOIL analyses, then implement "
            "AeroDeck.from_avl_xfoil()"
        )
        return cls.generate_placeholder()

    def save(self, filepath: str | Path):
        """Save aero deck to file (NPZ format)."""
        filepath = Path(filepath)
        np.savez(
            filepath,
            alpha_vector=self.alpha_vector,
            beta_vector=self.beta_vector,
            elevator_vector=self.elevator_vector,
            aileron_vector=self.aileron_vector,
            rudder_vector=self.rudder_vector,
            cx_data=self.cx_data,
            cy_data=self.cy_data,
            cz_data=self.cz_data,
            cl_data=self.cl_data,
            cm_data=self.cm_data,
            cn_data=self.cn_data,
            cxq_data=self.cxq_data,
            cyp_data=self.cyp_data,
            cyr_data=self.cyr_data,
            czq_data=self.czq_data,
            clp_data=self.clp_data,
            clr_data=self.clr_data,
            cmq_data=self.cmq_data,
            cnp_data=self.cnp_data,
            cnr_data=self.cnr_data,
            dlda_data=self.dlda_data,
            dldr_data=self.dldr_data,
            dnda_data=self.dnda_data,
            dndr_data=self.dndr_data,
        )
        print(f"Saved aero deck to: {filepath}")

    @classmethod
    def load(cls, filepath: str | Path) -> AeroDeck:
        """Load aero deck from file."""
        data = np.load(filepath)
        return cls(
            alpha_vector=data["alpha_vector"],
            beta_vector=data["beta_vector"],
            elevator_vector=data["elevator_vector"],
            aileron_vector=data["aileron_vector"],
            rudder_vector=data["rudder_vector"],
            cx_data=data["cx_data"],
            cy_data=data["cy_data"],
            cz_data=data["cz_data"],
            cl_data=data["cl_data"],
            cm_data=data["cm_data"],
            cn_data=data["cn_data"],
            cxq_data=data["cxq_data"],
            cyp_data=data["cyp_data"],
            cyr_data=data["cyr_data"],
            czq_data=data["czq_data"],
            clp_data=data["clp_data"],
            clr_data=data["clr_data"],
            cmq_data=data["cmq_data"],
            cnp_data=data["cnp_data"],
            cnr_data=data["cnr_data"],
            dlda_data=data["dlda_data"],
            dldr_data=data["dldr_data"],
            dnda_data=data["dnda_data"],
            dndr_data=data["dndr_data"],
        )


if __name__ == "__main__":
    # Generate placeholder aero deck
    aero_deck = AeroDeck.generate_placeholder()

    # Save to file
    output_dir = Path(__file__).parent / "data" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    aero_deck.save(output_dir / "ntop_aero_deck.npz")

    print("\nAero Deck Summary:")
    print(f"  Alpha range: {aero_deck.alpha_vector[0]}° to "
          f"{aero_deck.alpha_vector[-1]}°")
    print(f"  Beta range: {aero_deck.beta_vector[0]}° to "
          f"{aero_deck.beta_vector[-1]}°")
    print(f"  Number of alpha points: {len(aero_deck.alpha_vector)}")
    print(f"  Number of beta points: {len(aero_deck.beta_vector)}")
