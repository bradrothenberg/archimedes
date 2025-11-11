# SPDX-FileCopyrightText: 2025 nTop Integration
# SPDX-License-Identifier: GPL-3.0-or-later

"""Example simulation of nTop vehicle.

This script demonstrates the complete workflow from geometry loading
through AVL/XFOIL analysis to 6-DOF simulation.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Import ntop modules (assuming archimedes is installed)
try:
    from ntop import (
        CLIMB,
        CRUISE,
        LANDING,
        NTopVehicle,
        create_initial_state,
        simulate_flight,
        analyze_flight_data,
        print_flight_summary,
    )

    ARCHIMEDES_AVAILABLE = True
except ImportError:
    ARCHIMEDES_AVAILABLE = False
    print("Warning: Archimedes not installed. Install with: pip install -e .")


def plot_flight_data(data: dict, regime_name: str):
    """Plot flight data.

    Args:
        data: Flight data dictionary
        regime_name: Name of flight regime
    """
    fig, axes = plt.subplots(3, 2, figsize=(12, 10))
    fig.suptitle(f"Flight Simulation: {regime_name}", fontsize=16)

    t = data["time"]

    # Altitude
    axes[0, 0].plot(t, data["altitude"])
    axes[0, 0].set_ylabel("Altitude [ft]")
    axes[0, 0].set_xlabel("Time [s]")
    axes[0, 0].grid(True)

    # Velocity
    axes[0, 1].plot(t, data["velocity"])
    axes[0, 1].set_ylabel("Velocity [ft/s]")
    axes[0, 1].set_xlabel("Time [s]")
    axes[0, 1].grid(True)

    # Angle of attack
    axes[1, 0].plot(t, data["alpha"])
    axes[1, 0].set_ylabel("Angle of Attack [deg]")
    axes[1, 0].set_xlabel("Time [s]")
    axes[1, 0].grid(True)

    # Sideslip
    axes[1, 1].plot(t, data["beta"])
    axes[1, 1].set_ylabel("Sideslip [deg]")
    axes[1, 1].set_xlabel("Time [s]")
    axes[1, 1].grid(True)

    # Pitch
    axes[2, 0].plot(t, data["pitch"], label="Pitch")
    axes[2, 0].plot(t, data["roll"], label="Roll")
    axes[2, 0].set_ylabel("Attitude [deg]")
    axes[2, 0].set_xlabel("Time [s]")
    axes[2, 0].legend()
    axes[2, 0].grid(True)

    # Heading
    axes[2, 1].plot(t, data["heading"])
    axes[2, 1].set_ylabel("Heading [deg]")
    axes[2, 1].set_xlabel("Time [s]")
    axes[2, 1].grid(True)

    plt.tight_layout()
    plt.savefig(f"flight_sim_{regime_name}.png", dpi=150)
    print(f"Saved plot: flight_sim_{regime_name}.png")
    plt.show()


def run_example():
    """Run complete example simulation."""
    if not ARCHIMEDES_AVAILABLE:
        print("\nArchimedes not available. Cannot run simulation.")
        print("Install with: pip install -e .")
        return

    print("=" * 70)
    print("nTop Vehicle Simulation Example")
    print("=" * 70)

    # Load vehicle
    data_dir = Path(__file__).parent / "data"
    print(f"\nLoading vehicle from: {data_dir}")

    vehicle = NTopVehicle.from_ntop_data(data_dir, max_thrust=2000.0)

    print("\nVehicle Configuration:")
    print(f"  Mass: {vehicle.m:.2f} slug")
    print(f"  Reference area: {vehicle.geometry.S:.2f} ft²")
    print(f"  Wing span: {vehicle.geometry.b:.2f} ft")
    print(f"  Max thrust: {vehicle.max_thrust:.1f} lbf")

    # Simulate cruise flight
    print(f"\n{'-' * 70}")
    print(f"Simulating: {CRUISE.description}")
    print(f"{'-' * 70}")

    initial_state = create_initial_state(vehicle, CRUISE, alpha_deg=3.0)

    controls = vehicle.Input(
        throttle=0.5,
        elevator=0.0,
        aileron=0.0,
        rudder=0.0,
    )

    t_array, states = simulate_flight(
        vehicle, initial_state, controls, t_span=(0.0, 30.0), dt=0.1
    )

    # Analyze results
    flight_data = analyze_flight_data(vehicle, t_array, states)
    print_flight_summary(flight_data)

    # Plot results
    try:
        plot_flight_data(flight_data, "cruise")
    except Exception as e:
        print(f"Warning: Could not generate plots: {e}")

    print("\n" + "=" * 70)
    print("Simulation complete!")
    print("=" * 70)


if __name__ == "__main__":
    run_example()
