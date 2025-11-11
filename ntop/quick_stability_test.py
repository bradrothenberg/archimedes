#!/usr/bin/env python
"""Quick stability test - just verify aircraft doesn't diverge."""

from pathlib import Path
import numpy as np
from scipy.integrate import solve_ivp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from run_ntop_sim import create_vehicle, create_trim_state

def main():
    print("="*70)
    print("QUICK STABILITY TEST - New Aero Deck")
    print("="*70)

    # Create vehicle with new aero deck
    data_dir = Path(__file__).parent / "data"
    vehicle = create_vehicle(data_dir, max_thrust=3600.0)

    # Cruise condition (same as before)
    V_ktas = 287.0  # KTAS
    V_fps = V_ktas * 1.68781  # ft/s
    altitude_ft = 20000.0

    # Use the trim alpha from AVL (4.17 degrees)
    alpha_deg = 4.17
    alpha_rad = np.deg2rad(alpha_deg)
    theta_rad = alpha_rad  # Level flight

    print(f"\nFlight condition:")
    print(f"  Velocity: {V_ktas:.1f} KTAS ({V_fps:.1f} ft/s)")
    print(f"  Altitude: {altitude_ft:.0f} ft")
    print(f"  Alpha: {alpha_deg:.2f}°")
    print(f"  Theta: {np.rad2deg(theta_rad):.2f}°")

    # Create initial state
    state0 = create_trim_state(vehicle, V_fps, altitude_ft, alpha_rad, theta_rad)

    # Add small pitch perturbation (1 degree)
    perturbation_deg = 1.0
    print(f"\nApplying +{perturbation_deg}° pitch perturbation...")

    from archimedes.spatial import Quaternion
    euler_perturb = np.array([np.deg2rad(perturbation_deg), 0, 0])
    q_perturb = Quaternion.from_euler(euler_perturb, 'xyz')
    state0 = state0.replace(q_IB=q_perturb * state0.q_IB)

    # Simulate for 30 seconds
    t_span = (0, 30)
    t_eval = np.linspace(0, 30, 300)

    print("\nIntegrating equations of motion (30 seconds)...")

    # Zero control inputs
    ctrl = vehicle.Control(throttle=0.0, elevator=0.0, aileron=0.0, rudder=0.0)

    def derivatives(t, y):
        state = vehicle.State.from_array(y)
        f, m = vehicle.total_force_moment(state, ctrl)
        xdot = vehicle.derivatives(state, f, m)
        return xdot.to_array()

    result = solve_ivp(
        derivatives,
        t_span,
        state0.to_array(),
        method='RK45',
        t_eval=t_eval,
        max_step=0.1,
        rtol=1e-6,
        atol=1e-9,
    )

    if not result.success:
        print(f"\n[FAILED] Integration failed: {result.message}")
        return

    print(f"[OK] Integration successful ({len(result.t)} points)")

    # Extract time histories
    t = result.t
    pitch = np.zeros_like(t)
    theta = np.zeros_like(t)
    alpha_hist = np.zeros_like(t)

    for i, y in enumerate(result.y.T):
        state = vehicle.State.from_array(y)
        euler = state.q_IB.to_euler('xyz')
        pitch[i] = euler[1]  # Pitch angle (theta)
        theta[i] = euler[1]

        # Calculate alpha
        v_B = state.v_B
        alpha_hist[i] = np.arctan2(v_B[2], v_B[0])

    # Convert to degrees
    pitch_deg = np.rad2deg(pitch)
    alpha_deg_hist = np.rad2deg(alpha_hist)

    # Check stability
    final_pitch = pitch_deg[-1]
    pitch_change = abs(final_pitch - pitch_deg[0])

    print("\n" + "="*70)
    print("STABILITY RESULTS")
    print("="*70)
    print(f"\nInitial pitch angle: {pitch_deg[0]:.2f}°")
    print(f"Final pitch angle:   {final_pitch:.2f}°")
    print(f"Change:              {pitch_change:.2f}°")

    if pitch_change < 5.0:
        print("\n[OK] STABLE - Pitch oscillations damped out")
        status = "STABLE"
    elif pitch_change < 20.0:
        print("\n[WARNING] MARGINAL - Pitch changed significantly")
        status = "MARGINAL"
    else:
        print("\n[FAILED] UNSTABLE - Pitch diverged!")
        status = "UNSTABLE"

    # Plot results
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

    ax1.plot(t, pitch_deg)
    ax1.set_xlabel('Time [s]')
    ax1.set_ylabel('Pitch Angle [deg]')
    ax1.set_title(f'Pitch Response to 1° Perturbation - {status}')
    ax1.grid(True)
    ax1.axhline(y=pitch_deg[0], color='r', linestyle='--', label='Initial')
    ax1.legend()

    ax2.plot(t, alpha_deg_hist)
    ax2.set_xlabel('Time [s]')
    ax2.set_ylabel('Angle of Attack [deg]')
    ax2.set_title('Alpha History')
    ax2.grid(True)
    ax2.axhline(y=4.17, color='r', linestyle='--', label='Trim alpha')
    ax2.legend()

    plt.tight_layout()
    output_file = Path(__file__).parent / "quick_stability_test.png"
    plt.savefig(output_file, dpi=150)
    print(f"\nPlot saved to: {output_file}")

    print("\n" + "="*70)
    if status == "STABLE":
        print("SUCCESS! Aircraft is STABLE with new aero deck")
    elif status == "MARGINAL":
        print("CAUTION! Aircraft stability is marginal")
    else:
        print("FAILURE! Aircraft is still UNSTABLE")
    print("="*70)

if __name__ == "__main__":
    main()
