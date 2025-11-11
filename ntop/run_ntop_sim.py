#!/usr/bin/env python
"""6-DOF simulation of nTop flying wing with trim and maneuvers.

This script demonstrates F-16-style 6-DOF flight dynamics simulation:
1. Find trim condition for specified flight condition
2. Simulate doublet and step inputs around trim
3. Generate time history plots of vehicle response
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import solve_ivp

import archimedes as arc
from archimedes.spatial import Quaternion

from geometry import WingGeometry, MassProperties
from aero_deck import AeroDeck
from ntop_aero import NTopAero
from ntop_vehicle import NTopVehicle, NTopVehicleGeometry
from archimedes.experimental.aero import ConstantGravity, StandardAtmosphere1976


def create_vehicle(data_dir: Path, max_thrust: float = 3600.0) -> NTopVehicle:
    """Create nTop vehicle from data files.

    Args:
        data_dir: Directory containing nTop data
        max_thrust: Maximum thrust [lbf] (default: FJ44-4A)

    Returns:
        NTopVehicle instance
    """
    # Load geometry and mass properties
    le_file = data_dir / "LEpts.csv"
    te_file = data_dir / "TEpts.csv"
    mass_file = data_dir / "mass.csv"

    wing_geom = WingGeometry.from_csv(le_file, te_file)
    mass_props = MassProperties.from_csv(mass_file)

    # Load aero deck
    generated_dir = data_dir / "generated"
    aero_deck = AeroDeck.load(generated_dir / "ntop_aero_deck.npz")

    # Create aero model
    aero = NTopAero(aero_deck, wing_geom)

    # Create vehicle geometry
    vehicle_geom = NTopVehicleGeometry(
        S=wing_geom.reference_area,
        b=wing_geom.span,
        cbar=wing_geom.mean_chord,
        AR=wing_geom.aspect_ratio,
    )

    # Create vehicle
    vehicle = NTopVehicle(
        aero=aero,
        geometry=vehicle_geom,
        m=mass_props.mass,
        J_B=mass_props.inertia,
        gravity=ConstantGravity(32.174),
        atmos=StandardAtmosphere1976(),
        xcg=0.25,
        max_thrust=max_thrust,
    )

    return vehicle


def create_trim_state(vehicle: NTopVehicle, velocity: float, altitude: float,
                     alpha: float, theta: float = None) -> NTopVehicle.State:
    """Create initial state at trim condition.

    Args:
        vehicle: Vehicle model
        velocity: True airspeed [ft/s]
        altitude: Altitude MSL [ft]
        alpha: Angle of attack [rad]
        theta: Pitch angle [rad], defaults to alpha for level flight

    Returns:
        Initial state
    """
    if theta is None:
        theta = alpha

    # Body-frame velocity from wind-frame velocity
    # In level flight: u = V*cos(alpha), w = V*sin(alpha), v = 0
    u = velocity * np.cos(alpha)
    v = 0.0
    w = velocity * np.sin(alpha)
    v_B = np.array([u, v, w])

    # Initial attitude (level flight)
    rpy = np.array([0.0, theta, 0.0])  # Roll, pitch, yaw
    att = Quaternion.from_euler(rpy)

    # Initial position (NED frame)
    pos = np.array([0.0, 0.0, -altitude])  # North, East, Down

    # Initial angular velocity (zero for steady flight)
    w_B = np.array([0.0, 0.0, 0.0])

    # Create state
    return vehicle.State(
        pos=pos,
        att=att,
        v_B=v_B,
        w_B=w_B,
    )


def doublet_input(t: float, t_start: float, t_end: float,
                 amplitude: float) -> float:
    """Generate doublet input (positive then negative pulse).

    Args:
        t: Current time [s]
        t_start: Start time [s]
        t_end: End time [s]
        amplitude: Pulse amplitude

    Returns:
        Input value
    """
    t_mid = (t_start + t_end) / 2
    if t_start <= t < t_mid:
        return amplitude
    elif t_mid <= t < t_end:
        return -amplitude
    else:
        return 0.0


def run_simulation(vehicle: NTopVehicle, x0: NTopVehicle.State,
                  u_trim: NTopVehicle.Input, t_span: tuple[float, float],
                  input_func=None) -> tuple:
    """Run 6-DOF time-domain simulation.

    Args:
        vehicle: Vehicle model
        x0: Initial state
        u_trim: Trim control inputs
        t_span: Time span (t0, tf) [s]
        input_func: Optional function(t) -> delta_u for perturbing trim inputs

    Returns:
        Tuple of (t, states) where states is a list of State objects
    """
    # Flatten initial state and get unravel function
    x0_flat, unravel_x = arc.tree.ravel(x0)

    def dynamics_wrapper(t, x_flat):
        # Unravel state
        x = unravel_x(x_flat)

        # Get control input
        u = u_trim
        if input_func is not None:
            delta_u = input_func(t)
            u = vehicle.Input(
                throttle=u_trim.throttle + delta_u.get('throttle', 0.0),
                elevator=u_trim.elevator + delta_u.get('elevator', 0.0),
                aileron=u_trim.aileron + delta_u.get('aileron', 0.0),
                rudder=u_trim.rudder + delta_u.get('rudder', 0.0),
            )

        # Compute derivative
        x_dot = vehicle.dynamics(t, x, u)
        x_dot_flat, _ = arc.tree.ravel(x_dot)

        return x_dot_flat

    # Integrate
    print(f"Running simulation from t={t_span[0]:.1f}s to t={t_span[1]:.1f}s...")
    sol = solve_ivp(dynamics_wrapper, t_span, x0_flat, method='RK45',
                   rtol=1e-6, atol=1e-9, dense_output=True)

    # Unflatten states
    states = [unravel_x(x_flat) for x_flat in sol.y.T]

    return sol.t, states


def plot_results(t: np.ndarray, states: list, trim_alpha: float,
                trim_theta: float, save_path: Path = None):
    """Generate time history plots of simulation results.

    Args:
        t: Time vector [s]
        states: List of State objects
        trim_alpha: Trim angle of attack [rad]
        trim_theta: Trim pitch angle [rad]
        save_path: Optional path to save figure
    """
    # Extract data from states
    n_pts = len(t)

    # Position (NED frame)
    pos_N = np.array([s.pos for s in states])  # (n, 3)

    # Velocity (body frame)
    v_B = np.array([s.v_B for s in states])  # (n, 3)
    u_vals = v_B[:, 0]
    v_vals = v_B[:, 1]
    w_vals = v_B[:, 2]

    # Compute alpha, beta, Vt
    Vt = np.linalg.norm(v_B, axis=1)
    alpha = np.arctan2(w_vals, u_vals)
    beta = np.arcsin(np.clip(v_vals / Vt, -1, 1))

    # Angular velocity (body frame)
    w_B = np.array([s.w_B for s in states])  # (n, 3)
    p = w_B[:, 0]
    q = w_B[:, 1]
    r = w_B[:, 2]

    # Euler angles
    rpy = np.array([s.att.as_euler() for s in states])  # (n, 3)
    phi = rpy[:, 0]
    theta = rpy[:, 1]
    psi = rpy[:, 2]

    # Create figure with subplots
    fig, axes = plt.subplots(4, 2, figsize=(12, 10))
    fig.suptitle('nTop Flying Wing - 6-DOF Simulation', fontsize=14, fontweight='bold')

    # Row 1: Position
    ax = axes[0, 0]
    ax.plot(t, pos_N[:, 0], 'b-', label='North')
    ax.plot(t, pos_N[:, 1], 'r-', label='East')
    ax.set_ylabel('Position [ft]')
    ax.set_xlabel('Time [s]')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_title('Horizontal Position (NED)')

    ax = axes[0, 1]
    ax.plot(t, -pos_N[:, 2], 'k-')  # Altitude is -z
    ax.set_ylabel('Altitude [ft]')
    ax.set_xlabel('Time [s]')
    ax.grid(True, alpha=0.3)
    ax.set_title('Altitude')

    # Row 2: Velocity
    ax = axes[1, 0]
    ax.plot(t, Vt, 'k-')
    ax.set_ylabel('True Airspeed [ft/s]')
    ax.set_xlabel('Time [s]')
    ax.grid(True, alpha=0.3)
    ax.set_title('Velocity')

    ax = axes[1, 1]
    ax.plot(t, np.rad2deg(alpha), 'b-', label='α')
    ax.plot(t, np.rad2deg(beta), 'r-', label='β')
    ax.axhline(np.rad2deg(trim_alpha), color='b', linestyle='--', alpha=0.5, label='α trim')
    ax.set_ylabel('Angle [deg]')
    ax.set_xlabel('Time [s]')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_title('Angles of Attack and Sideslip')

    # Row 3: Attitude
    ax = axes[2, 0]
    ax.plot(t, np.rad2deg(phi), 'b-', label='Roll (φ)')
    ax.plot(t, np.rad2deg(theta), 'r-', label='Pitch (θ)')
    ax.axhline(np.rad2deg(trim_theta), color='r', linestyle='--', alpha=0.5, label='θ trim')
    ax.set_ylabel('Angle [deg]')
    ax.set_xlabel('Time [s]')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_title('Attitude (Euler Angles)')

    ax = axes[2, 1]
    ax.plot(t, np.rad2deg(psi), 'k-')
    ax.set_ylabel('Yaw Angle [deg]')
    ax.set_xlabel('Time [s]')
    ax.grid(True, alpha=0.3)
    ax.set_title('Heading')

    # Row 4: Angular rates
    ax = axes[3, 0]
    ax.plot(t, np.rad2deg(p), 'b-', label='Roll rate (p)')
    ax.plot(t, np.rad2deg(q), 'r-', label='Pitch rate (q)')
    ax.set_ylabel('Rate [deg/s]')
    ax.set_xlabel('Time [s]')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_title('Angular Rates')

    ax = axes[3, 1]
    ax.plot(t, np.rad2deg(r), 'k-')
    ax.set_ylabel('Yaw Rate [deg/s]')
    ax.set_xlabel('Time [s]')
    ax.grid(True, alpha=0.3)
    ax.set_title('Yaw Rate')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved plot to: {save_path}")

    return fig


def main():
    """Run nTop flying wing simulations."""
    print("=" * 70)
    print("nTop Flying Wing - 6-DOF Flight Dynamics Simulation")
    print("=" * 70)
    print()

    # Setup
    data_dir = Path(__file__).parent / "data"
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    # Create vehicle
    print("Creating vehicle model...")
    vehicle = create_vehicle(data_dir, max_thrust=3600.0)  # Williams FJ44-4A
    print(f"  Mass: {vehicle.m:.2f} slug ({vehicle.m * 32.174:.0f} lbf)")
    print(f"  Wing area: {vehicle.geometry.S:.2f} ft^2")
    print(f"  Max thrust: {vehicle.max_thrust:.0f} lbf (Williams FJ44-4A)")
    print(f"  Thrust/Weight: {vehicle.max_thrust / (vehicle.m * 32.174):.3f}")
    print()

    # Trim condition (from trim solver with FJ44-4A thrust)
    # Cruise: 250 ft/s @ 20,000 ft
    velocity = 250.0  # ft/s
    altitude = 20000.0  # ft
    alpha_trim = np.deg2rad(16.41)  # rad
    elevator_trim = -3.89  # deg
    throttle_trim = 0.380  # 0-1

    print("Trim condition (Cruise):")
    print(f"  Velocity: {velocity:.1f} ft/s")
    print(f"  Altitude: {altitude:.0f} ft")
    print(f"  Alpha: {np.rad2deg(alpha_trim):.2f} deg")
    print(f"  Elevator: {elevator_trim:.2f} deg")
    print(f"  Throttle: {throttle_trim:.1%}")
    print(f"  CL: 0.918, CD: 0.174, L/D: 5.27")
    print()

    # Create initial state at trim
    x0 = create_trim_state(vehicle, velocity, altitude, alpha_trim)

    # Trim control inputs
    u_trim = vehicle.Input(
        throttle=throttle_trim,
        elevator=elevator_trim,
        aileron=0.0,
        rudder=0.0,
    )

    # === Scenario 1: Elevator doublet ===
    print("-" * 70)
    print("Scenario 1: Elevator Doublet (±5 deg)")
    print("-" * 70)

    def elevator_doublet(t):
        return {'elevator': doublet_input(t, 2.0, 4.0, 5.0)}

    t, states = run_simulation(vehicle, x0, u_trim, (0, 20), elevator_doublet)

    print(f"Simulation complete: {len(t)} time points")
    print()

    # Plot results
    fig1 = plot_results(t, states, alpha_trim, alpha_trim,
                       save_path=output_dir / "ntop_elevator_doublet.png")

    # === Scenario 2: Aileron doublet ===
    print("-" * 70)
    print("Scenario 2: Aileron Doublet (±10 deg)")
    print("-" * 70)

    def aileron_doublet(t):
        return {'aileron': doublet_input(t, 2.0, 4.0, 10.0)}

    t, states = run_simulation(vehicle, x0, u_trim, (0, 20), aileron_doublet)

    print(f"Simulation complete: {len(t)} time points")
    print()

    # Plot results
    fig2 = plot_results(t, states, alpha_trim, alpha_trim,
                       save_path=output_dir / "ntop_aileron_doublet.png")

    print("=" * 70)
    print("Simulations complete!")
    print("=" * 70)
    print()
    print("Generated plots:")
    print(f"  - {output_dir / 'ntop_elevator_doublet.png'}")
    print(f"  - {output_dir / 'ntop_aileron_doublet.png'}")
    print()

    plt.show()


if __name__ == "__main__":
    main()
