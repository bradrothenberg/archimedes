# SPDX-FileCopyrightText: 2025 nTop Integration
# SPDX-License-Identifier: GPL-3.0-or-later

"""Simulation interface for nTop vehicle.

This module provides simulation utilities for the nTop vehicle across
different flight regimes: climb, cruise, and landing.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

import archimedes as arc
from archimedes.spatial import Quaternion

from ntop_vehicle import NTopVehicle


@dataclass
class FlightRegime:
    """Flight regime specification."""

    name: str
    altitude: float  # Altitude [ft]
    velocity: float  # True airspeed [ft/s]
    climb_angle: float = 0.0  # Flight path angle [deg]
    description: str = ""


# Standard flight regimes for Mach 0.5 at 20,000 ft
CRUISE = FlightRegime(
    name="cruise",
    altitude=20000.0,
    velocity=550.0,  # ~Mach 0.5 at 20k ft
    climb_angle=0.0,
    description="Level cruise at Mach 0.5, 20,000 ft",
)

CLIMB = FlightRegime(
    name="climb",
    altitude=15000.0,
    velocity=450.0,
    climb_angle=5.0,
    description="Climb at 5° flight path angle",
)

LANDING = FlightRegime(
    name="landing",
    altitude=500.0,
    velocity=200.0,
    climb_angle=-3.0,
    description="Landing approach at -3° glide slope",
)


def create_initial_state(
    vehicle: NTopVehicle,
    regime: FlightRegime,
    alpha_deg: float = 2.0,
    heading_deg: float = 0.0,
) -> NTopVehicle.State:
    """Create initial state for specified flight regime.

    Args:
        vehicle: Vehicle model
        regime: Flight regime specification
        alpha_deg: Initial angle of attack [deg]
        heading_deg: Initial heading [deg]

    Returns:
        Initial vehicle state
    """
    # Convert angles to radians
    alpha = np.deg2rad(alpha_deg)
    gamma = np.deg2rad(regime.climb_angle)
    heading = np.deg2rad(heading_deg)

    # Compute pitch angle from alpha and flight path angle
    # theta = alpha + gamma
    theta = alpha + gamma

    # Initial attitude (NED frame)
    # Roll=0, Pitch=theta, Yaw=heading
    att = Quaternion.from_euler(np.array([0.0, theta, heading]))

    # Velocity in body frame
    # For small angles: u ≈ V*cos(alpha), w ≈ V*sin(alpha)
    u = regime.velocity * np.cos(alpha)
    w = regime.velocity * np.sin(alpha)
    v = 0.0  # No sideslip
    v_B = np.array([u, v, w])

    # Initial position (NED frame)
    # Start at specified altitude
    pos = np.array([0.0, 0.0, -regime.altitude])

    # Zero angular rates initially
    w_B = np.zeros(3)

    # Initial aero state
    aero_state = vehicle.aero.State()

    return vehicle.State(
        pos=pos,
        att=att,
        v_B=v_B,
        w_B=w_B,
        aero=aero_state,
        throttle=0.5,
    )


def simulate_flight(
    vehicle: NTopVehicle,
    initial_state: NTopVehicle.State,
    control_input: NTopVehicle.Input,
    t_span: tuple[float, float] = (0.0, 60.0),
    dt: float = 0.01,
) -> tuple[np.ndarray, list[NTopVehicle.State]]:
    """Simulate vehicle flight with constant control inputs.

    Args:
        vehicle: Vehicle model
        initial_state: Initial state
        control_input: Control inputs (held constant)
        t_span: Time span [s]
        dt: Time step for output [s]

    Returns:
        Tuple of (time_array, states_list)
    """
    print(f"\nSimulating from t={t_span[0]:.1f}s to t={t_span[1]:.1f}s...")

    # Flatten initial state for ODE solver
    x0_flat, unravel = arc.tree.ravel(initial_state)

    # Define dynamics function with flattened states
    def dynamics_flat(t, x_flat):
        x = unravel(x_flat)
        x_dot = vehicle.dynamics(t, x, control_input)
        x_dot_flat, _ = arc.tree.ravel(x_dot)
        return x_dot_flat

    # Time points for output
    t_eval = np.arange(t_span[0], t_span[1], dt)

    # Integrate
    xs_flat = arc.odeint(
        dynamics_flat,
        t_span=t_span,
        x0=x0_flat,
        t_eval=t_eval,
    )

    # Unravel states
    states = arc.vmap(unravel)(xs_flat.T)

    print(f"Simulation complete. {len(t_eval)} time points.")

    return t_eval, states


def analyze_flight_data(
    vehicle: NTopVehicle,
    t_array: np.ndarray,
    states: list[NTopVehicle.State],
) -> dict:
    """Extract and analyze flight data from simulation results.

    Args:
        vehicle: Vehicle model
        t_array: Time array [s]
        states: List of vehicle states

    Returns:
        Dictionary with flight data arrays
    """
    n = len(t_array)

    # Allocate arrays
    altitude = np.zeros(n)
    velocity = np.zeros(n)
    alpha = np.zeros(n)
    beta = np.zeros(n)
    pitch = np.zeros(n)
    roll = np.zeros(n)
    heading = np.zeros(n)

    # Extract data
    for i, state in enumerate(states):
        # Altitude
        altitude[i] = -state.pos[2]

        # Flight condition
        condition = vehicle.flight_condition(state)
        velocity[i] = condition.vt
        alpha[i] = np.rad2deg(condition.alpha)
        beta[i] = np.rad2deg(condition.beta)

        # Attitude
        euler = state.att.as_euler()
        roll[i] = np.rad2deg(euler[0])
        pitch[i] = np.rad2deg(euler[1])
        heading[i] = np.rad2deg(euler[2])

    return {
        "time": t_array,
        "altitude": altitude,
        "velocity": velocity,
        "alpha": alpha,
        "beta": beta,
        "pitch": pitch,
        "roll": roll,
        "heading": heading,
    }


def print_flight_summary(data: dict):
    """Print summary of flight data.

    Args:
        data: Flight data dictionary from analyze_flight_data
    """
    print("\nFlight Summary:")
    print("=" * 60)
    print(f"Duration: {data['time'][-1]:.1f} s")
    print(f"\nAltitude:")
    print(f"  Initial: {data['altitude'][0]:.1f} ft")
    print(f"  Final:   {data['altitude'][-1]:.1f} ft")
    print(f"  Change:  {data['altitude'][-1] - data['altitude'][0]:+.1f} ft")
    print(f"\nVelocity:")
    print(f"  Initial: {data['velocity'][0]:.1f} ft/s")
    print(f"  Final:   {data['velocity'][-1]:.1f} ft/s")
    print(f"  Mean:    {np.mean(data['velocity']):.1f} ft/s")
    print(f"\nAngle of Attack:")
    print(f"  Initial: {data['alpha'][0]:.2f}°")
    print(f"  Final:   {data['alpha'][-1]:.2f}°")
    print(f"  Mean:    {np.mean(data['alpha']):.2f}°")
    print(f"\nPitch Attitude:")
    print(f"  Initial: {data['pitch'][0]:.2f}°")
    print(f"  Final:   {data['pitch'][-1]:.2f}°")
    print("=" * 60)


if __name__ == "__main__":
    print("=" * 60)
    print("nTop Vehicle Flight Simulation")
    print("=" * 60)

    # Load vehicle
    data_dir = Path(__file__).parent / "data"
    print(f"\nLoading vehicle from: {data_dir}")

    # NOTE: This will fail without archimedes installed
    # Uncomment when ready to run:
    #
    # vehicle = NTopVehicle.from_ntop_data(data_dir, max_thrust=2000.0)
    #
    # # Simulate cruise flight
    # print(f"\n{CRUISE.description}")
    # initial_state = create_initial_state(vehicle, CRUISE, alpha_deg=3.0)
    #
    # # Control inputs for level flight
    # controls = vehicle.Input(
    #     throttle=0.5,
    #     elevator=0.0,
    #     aileron=0.0,
    #     rudder=0.0,
    # )
    #
    # # Run simulation
    # t_array, states = simulate_flight(
    #     vehicle, initial_state, controls, t_span=(0.0, 30.0), dt=0.1
    # )
    #
    # # Analyze results
    # flight_data = analyze_flight_data(vehicle, t_array, states)
    # print_flight_summary(flight_data)

    print("\nSimulation script ready.")
    print("\nTo run simulations:")
    print("  1. Install Archimedes: pip install -e .")
    print("  2. Uncomment the simulation code in this file")
    print("  3. Run: python ntop/simulate.py")
    print("\nAvailable flight regimes:")
    for regime in [CRUISE, CLIMB, LANDING]:
        print(f"  - {regime.name}: {regime.description}")
