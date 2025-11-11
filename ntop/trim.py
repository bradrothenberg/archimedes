#!/usr/bin/env python
"""Trim solver for nTop flying wing.

Finds equilibrium flight conditions (alpha, elevator, throttle) for steady
level flight at specified velocity and altitude.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import numpy as np
from scipy.optimize import minimize, least_squares

from geometry import WingGeometry, MassProperties
from aero_deck import AeroDeck
from ntop_aero import NTopAero
from ntop_vehicle import NTopVehicle


@dataclass
class TrimCondition:
    """Flight condition for trim."""
    velocity: float  # True airspeed [ft/s]
    altitude: float  # Altitude MSL [ft]
    flight_path_angle: float = 0.0  # Gamma [rad], 0 for level flight
    turn_rate: float = 0.0  # Turn rate [rad/s], 0 for wings-level


@dataclass
class TrimResult:
    """Results from trim solver."""
    alpha: float  # Angle of attack [rad]
    elevator: float  # Elevator deflection [deg]
    throttle: float  # Throttle setting [0-1]

    # Residuals (should be near zero)
    lift_residual: float  # N - W [lbf]
    drag_residual: float  # T - D [lbf]
    moment_residual: float  # M [ft-lbf]

    # Aerodynamic coefficients at trim
    CL: float
    CD: float
    Cm: float

    # Flight condition
    condition: TrimCondition

    def __str__(self):
        return (
            f"Trim Solution:\n"
            f"  Alpha: {np.rad2deg(self.alpha):.2f} deg\n"
            f"  Elevator: {self.elevator:.2f} deg\n"
            f"  Throttle: {self.throttle:.3f}\n"
            f"  CL: {self.CL:.4f}\n"
            f"  CD: {self.CD:.4f}\n"
            f"  L/D: {self.CL/self.CD:.2f}\n"
            f"Residuals:\n"
            f"  Lift: {self.lift_residual:.4f} lbf\n"
            f"  Drag: {self.drag_residual:.4f} lbf\n"
            f"  Moment: {self.moment_residual:.4f} ft-lbf"
        )


class TrimSolver:
    """Trim solver for finding equilibrium flight conditions."""

    def __init__(self, vehicle: NTopVehicle, aero: NTopAero, wing_geom: WingGeometry):
        """Initialize trim solver.

        Args:
            vehicle: Vehicle model with mass properties
            aero: Aerodynamics model
            wing_geom: Wing geometry for reference values
        """
        self.vehicle = vehicle
        self.aero = aero
        self.wing_geom = wing_geom

        # Standard atmosphere at sea level
        self.rho_sl = 0.002377  # slug/ft^3

    def _get_density(self, altitude: float) -> float:
        """Get atmospheric density at altitude using simple model.

        Args:
            altitude: Altitude MSL [ft]

        Returns:
            Density [slug/ft^3]
        """
        # Simple exponential atmosphere model
        # rho = rho_0 * exp(-h / H) where H ~ 30,000 ft
        H = 30000.0  # Scale height [ft]
        return self.rho_sl * np.exp(-altitude / H)

    def _compute_forces_moments(self, x: np.ndarray, condition: TrimCondition):
        """Compute force and moment residuals for trim.

        Args:
            x: State vector [alpha, elevator, throttle]
            condition: Flight condition

        Returns:
            residuals: [lift_residual, drag_residual, moment_residual]
        """
        alpha = x[0]  # rad
        elevator = x[1]  # deg
        throttle = x[2]  # 0-1

        # Atmospheric properties
        rho = self._get_density(condition.altitude)
        V = condition.velocity
        q = 0.5 * rho * V**2  # Dynamic pressure [lb/ft^2]

        # Aerodynamic coefficients
        # For now, use simple lookup (would need full vehicle eval in real code)
        alpha_deg = np.rad2deg(alpha)

        # Get aero coefficients from deck
        aero_deck = self.aero.aero_deck

        # Interpolate CL, CD, Cm at (alpha, elevator)
        CL = np.interp(alpha_deg, aero_deck.alpha_vector, aero_deck.cz_data)
        CL = -CL  # Cz = -CL in body axes

        # Get CD from cx_data (function of alpha and elevator)
        # Note: In body axes, CX is positive drag (opposite to velocity)
        # So CD = -CX in the typical sense, but AVL's CX is already positive drag
        elev_idx = np.argmin(np.abs(aero_deck.elevator_vector - elevator))
        CD_array = aero_deck.cx_data[:, elev_idx]  # Use CX directly as drag coefficient
        CD = np.interp(alpha_deg, aero_deck.alpha_vector, CD_array)

        # Get Cm from cm_data (function of alpha and elevator)
        Cm_array = aero_deck.cm_data[:, elev_idx]
        Cm = np.interp(alpha_deg, aero_deck.alpha_vector, Cm_array)

        # Forces
        L = q * self.wing_geom.reference_area * CL  # Lift [lbf]
        D = q * self.wing_geom.reference_area * CD  # Drag [lbf]
        T = throttle * self.vehicle.max_thrust  # Thrust [lbf]
        W = self.vehicle.m * 32.174  # Weight [lbf] (mass * g)

        # Moment
        M = q * self.wing_geom.reference_area * self.wing_geom.mean_chord * Cm  # ft-lbf

        # Force balance for level flight (gamma = 0)
        # L = W
        # T = D
        lift_residual = L - W
        drag_residual = T - D
        moment_residual = M  # Should be zero for trim

        return np.array([lift_residual, drag_residual, moment_residual]), CL, CD, Cm

    def solve(self, condition: TrimCondition,
              initial_guess: np.ndarray = None) -> TrimResult:
        """Solve for trim condition.

        Args:
            condition: Flight condition to trim at
            initial_guess: Initial guess [alpha_rad, elevator_deg, throttle]
                          If None, uses reasonable defaults

        Returns:
            TrimResult with solution
        """
        print(f"Solving trim for V={condition.velocity:.1f} ft/s, h={condition.altitude:.0f} ft")

        # Initial guess if not provided
        if initial_guess is None:
            # Estimate required CL for level flight
            rho = self._get_density(condition.altitude)
            V = condition.velocity
            q = 0.5 * rho * V**2
            W = self.vehicle.m * 32.174
            CL_required = W / (q * self.wing_geom.reference_area)

            # Estimate alpha from CL (assuming CLa ~ 0.08/deg = 4.6/rad)
            CLa = 4.6  # per radian (typical for wings)
            alpha_guess = CL_required / CLa  # rad
            alpha_guess = np.clip(alpha_guess, np.deg2rad(0), np.deg2rad(15))

            # Estimate thrust/drag
            CD_est = 0.02 + 0.05 * CL_required**2  # Parabolic drag polar
            D_est = q * self.wing_geom.reference_area * CD_est
            throttle_guess = D_est / self.vehicle.max_thrust
            throttle_guess = np.clip(throttle_guess, 0.0, 1.0)

            elevator_guess = 0.0  # deg
            initial_guess = np.array([alpha_guess, elevator_guess, throttle_guess])

            print(f"  Initial guess: alpha={np.rad2deg(alpha_guess):.1f}°, elev={elevator_guess:.1f}°, throttle={throttle_guess:.3f}")

        # Bounds
        # Alpha: -5 to 20 deg (avoid stall)
        # Elevator: -24 to +24 deg
        # Throttle: 0 to 1
        bounds_lower = np.array([np.deg2rad(-5), -24, 0.0])
        bounds_upper = np.array([np.deg2rad(20), 24, 1.0])

        # Residual function for least_squares
        def residuals_func(x):
            residuals, _, _, _ = self._compute_forces_moments(x, condition)
            # Weight the residuals to get similar magnitudes
            # Lift/drag in 1000s of lbf, moment in 10000s of ft-lbf (lower weight)
            # Prioritize force balance over moment balance
            weights = np.array([1.0/1000.0, 1.0/1000.0, 1.0/10000.0])
            return weights * residuals

        # Solve using least squares with trust region reflective method
        result = least_squares(
            residuals_func,
            initial_guess,
            bounds=(bounds_lower, bounds_upper),
            method='trf',  # Trust Region Reflective
            ftol=1e-6,
            xtol=1e-6,
            gtol=1e-6,
            max_nfev=2000,
            verbose=0,
            x_scale='jac',  # Scale based on Jacobian
        )

        if not result.success:
            print(f"  Warning: Optimization did not converge: {result.message}")

        # Extract solution
        alpha_trim = result.x[0]
        elevator_trim = result.x[1]
        throttle_trim = result.x[2]

        # Compute final residuals and coefficients
        residuals, CL, CD, Cm = self._compute_forces_moments(result.x, condition)

        trim_result = TrimResult(
            alpha=alpha_trim,
            elevator=elevator_trim,
            throttle=throttle_trim,
            lift_residual=residuals[0],
            drag_residual=residuals[1],
            moment_residual=residuals[2],
            CL=CL,
            CD=CD,
            Cm=Cm,
            condition=condition,
        )

        print(f"  Alpha: {np.rad2deg(alpha_trim):.2f} deg")
        print(f"  Elevator: {elevator_trim:.2f} deg")
        print(f"  Throttle: {throttle_trim:.3f}")
        print(f"  CL: {CL:.4f}, CD: {CD:.4f}, L/D: {CL/CD:.2f}")
        print(f"  Residuals: L={residuals[0]:.2f} lbf, D={residuals[1]:.2f} lbf, M={residuals[2]:.2f} ft-lbf")

        return trim_result


if __name__ == "__main__":
    print("="*70)
    print("nTop Flying Wing Trim Solver")
    print("="*70)
    print()

    # Load geometry and mass properties
    data_dir = Path(__file__).parent / "data"
    generated_dir = data_dir / "generated"

    le_file = data_dir / "LEpts.csv"
    te_file = data_dir / "TEpts.csv"
    mass_file = data_dir / "mass.csv"

    print("Loading geometry and mass properties...")
    wing_geom = WingGeometry.from_csv(le_file, te_file)
    mass_props = MassProperties.from_csv(mass_file)

    print(f"  Reference area: {wing_geom.reference_area:.2f} ft^2")
    print(f"  Mass: {mass_props.mass:.2f} slug ({mass_props.mass * 32.174:.0f} lbf)")
    print()

    # Load aero deck
    print("Loading aero deck...")
    aero_deck = AeroDeck.load(generated_dir / "ntop_aero_deck.npz")

    # Create aero model
    aero = NTopAero(aero_deck, wing_geom)

    # Create vehicle (simplified for trim - would use full NTopVehicle for sim)
    from ntop_vehicle import NTopVehicleGeometry
    from archimedes.experimental.aero import ConstantGravity, StandardAtmosphere1976

    vehicle_geom = NTopVehicleGeometry(
        S=wing_geom.reference_area,
        b=wing_geom.span,
        cbar=wing_geom.mean_chord,
        AR=wing_geom.aspect_ratio,
    )

    vehicle = NTopVehicle(
        aero=aero,
        geometry=vehicle_geom,
        m=mass_props.mass,
        J_B=mass_props.inertia,
        gravity=ConstantGravity(32.174),
        atmos=StandardAtmosphere1976(),
        xcg=0.25,
        max_thrust=3600.0,  # Williams FJ44-4A thrust [lbf]
    )

    # Create trim solver
    solver = TrimSolver(vehicle, aero, wing_geom)

    # Test cases
    print("="*70)
    print("Trim Solutions")
    print("="*70)
    print()

    # Case 1: High altitude cruise at efficient CL
    print("Case 1: High Altitude Cruise (20,000 ft)")
    print("-"*70)
    condition1 = TrimCondition(
        velocity=484.0,  # ft/s (~286 kts) - for CL~0.25 at 20k ft
        altitude=20000.0,  # ft
    )
    trim1 = solver.solve(condition1)
    print()

    # Case 2: Sea level cruise
    print("Case 2: Sea Level Cruise")
    print("-"*70)
    condition2 = TrimCondition(
        velocity=347.0,  # ft/s (~205 kts) - for CL~0.25 at sea level
        altitude=0.0,  # ft
    )
    trim2 = solver.solve(condition2)
    print()

    # Case 3: Approach/Landing
    print("Case 3: Approach")
    print("-"*70)
    condition3 = TrimCondition(
        velocity=150.0,  # ft/s (~89 kts) - slow approach
        altitude=1000.0,  # ft
    )
    trim3 = solver.solve(condition3)
    print()

    print("="*70)
    print("Trim solver test complete!")
    print("="*70)
