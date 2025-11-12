#!/usr/bin/env python
"""Create animated visualization of 6-DOF simulation."""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from pathlib import Path
from scipy.integrate import solve_ivp

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import archimedes as arc

from run_ntop_sim import create_vehicle, create_trim_state

print("="*70)
print("Creating 6-DOF Simulation Animation")
print("="*70)

# Create vehicle
data_dir = Path(__file__).parent / "data"
vehicle = create_vehicle(data_dir, max_thrust=3600.0)

# Trim condition
velocity = 484.0  # ft/s
altitude = 20000.0  # ft
alpha_trim = np.deg2rad(4.17)
elevator_trim = 0.33
throttle_trim = 0.096

print(f"\nSimulation parameters:")
print(f"  Velocity: {velocity:.1f} ft/s")
print(f"  Altitude: {altitude:.0f} ft")
print(f"  Duration: 20 seconds")
print(f"  Maneuver: Elevator doublet at t=2-4s")

# Create initial state
x0 = create_trim_state(vehicle, velocity, altitude, alpha_trim)
u_trim = vehicle.Input(
    throttle=throttle_trim,
    elevator=elevator_trim,
    aileron=0.0,
    rudder=0.0,
)

# Elevator doublet function
def doublet_input(t, t_start, t_end, amplitude):
    if t < t_start:
        return 0.0
    elif t < (t_start + t_end) / 2:
        return amplitude
    elif t < t_end:
        return -amplitude
    else:
        return 0.0

def elevator_doublet(t):
    return {'elevator': doublet_input(t, 2.0, 4.0, 5.0)}

# Run simulation
print("\nRunning simulation...")
x0_flat, unravel_x = arc.tree.ravel(x0)

def dynamics_wrapper(t, x_flat):
    x = unravel_x(x_flat)
    delta_u = elevator_doublet(t)
    u = vehicle.Input(
        throttle=u_trim.throttle + delta_u.get('throttle', 0.0),
        elevator=u_trim.elevator + delta_u.get('elevator', 0.0),
        aileron=u_trim.aileron + delta_u.get('aileron', 0.0),
        rudder=u_trim.rudder + delta_u.get('rudder', 0.0),
    )
    x_dot = vehicle.dynamics(t, x, u)
    x_dot_flat, _ = arc.tree.ravel(x_dot)
    return x_dot_flat

t_span = (0, 20)
t_eval = np.linspace(0, 20, 200)  # 200 frames
sol = solve_ivp(dynamics_wrapper, t_span, x0_flat, method='RK45',
               t_eval=t_eval, rtol=1e-6, atol=1e-9)

states = [unravel_x(x_flat) for x_flat in sol.y.T]
t = sol.t

print(f"Simulation complete: {len(t)} frames")

# Extract data
pos = np.array([s.pos for s in states])
v_B = np.array([s.v_B for s in states])
alts = -pos[:, 2]
Vt = np.linalg.norm(v_B, axis=1)
alpha = np.arctan2(v_B[:, 2], v_B[:, 0])

# Extract attitude
pitch = np.zeros_like(t)
for i, s in enumerate(states):
    euler = s.att.as_euler('xyz')
    pitch[i] = euler[1]

# Control input history
elev = np.array([u_trim.elevator + doublet_input(ti, 2.0, 4.0, 5.0) for ti in t])

print("\nCreating animation frames...")

# Create figure with 3D trajectory and time histories
fig = plt.figure(figsize=(16, 9))
gs = fig.add_gridspec(2, 3, hspace=0.3, wspace=0.3)

# 3D trajectory
ax_3d = fig.add_subplot(gs[:, 0], projection='3d')

# Time histories
ax_alt = fig.add_subplot(gs[0, 1])
ax_pitch = fig.add_subplot(gs[1, 1])
ax_alpha = fig.add_subplot(gs[0, 2])
ax_elev = fig.add_subplot(gs[1, 2])

def init():
    # 3D trajectory setup
    ax_3d.set_xlabel('East [ft]')
    ax_3d.set_ylabel('North [ft]')
    ax_3d.set_zlabel('Altitude [ft]')
    ax_3d.set_title('3D Flight Path')

    # Time history setups
    ax_alt.set_xlabel('Time [s]')
    ax_alt.set_ylabel('Altitude [ft]')
    ax_alt.grid(True, alpha=0.3)

    ax_pitch.set_xlabel('Time [s]')
    ax_pitch.set_ylabel('Pitch [deg]')
    ax_pitch.grid(True, alpha=0.3)

    ax_alpha.set_xlabel('Time [s]')
    ax_alpha.set_ylabel('Alpha [deg]')
    ax_alpha.grid(True, alpha=0.3)

    ax_elev.set_xlabel('Time [s]')
    ax_elev.set_ylabel('Elevator [deg]')
    ax_elev.grid(True, alpha=0.3)

    return []

def update(frame):
    # Clear axes
    ax_3d.clear()
    ax_alt.clear()
    ax_pitch.clear()
    ax_alpha.clear()
    ax_elev.clear()

    # Current time
    t_curr = t[frame]

    # 3D trajectory up to current time
    ax_3d.plot(pos[:frame+1, 1], pos[:frame+1, 0], alts[:frame+1],
              'b-', linewidth=2, label='Flight path')
    ax_3d.scatter(pos[frame, 1], pos[frame, 0], alts[frame],
                 c='r', s=100, marker='o', label='Aircraft')
    ax_3d.set_xlabel('East [ft]')
    ax_3d.set_ylabel('North [ft]')
    ax_3d.set_zlabel('Altitude [ft]')
    ax_3d.set_title(f'3D Flight Path (t={t_curr:.1f}s)', fontweight='bold')
    ax_3d.legend()

    # Set consistent view
    ax_3d.set_xlim([-500, 500])
    ax_3d.set_ylim([0, 10000])
    ax_3d.set_zlim([12000, 20500])

    # Altitude history
    ax_alt.plot(t[:frame+1], alts[:frame+1], 'b-', linewidth=2)
    ax_alt.plot(t[frame], alts[frame], 'ro', markersize=8)
    ax_alt.set_xlim([0, 20])
    ax_alt.set_ylim([12000, 20500])
    ax_alt.set_xlabel('Time [s]')
    ax_alt.set_ylabel('Altitude [ft]')
    ax_alt.set_title('Altitude')
    ax_alt.grid(True, alpha=0.3)

    # Pitch history
    ax_pitch.plot(t[:frame+1], np.rad2deg(pitch[:frame+1]), 'b-', linewidth=2)
    ax_pitch.plot(t[frame], np.rad2deg(pitch[frame]), 'ro', markersize=8)
    ax_pitch.axhline(y=np.rad2deg(alpha_trim), color='k', linestyle='--',
                    alpha=0.5, label='Trim')
    ax_pitch.set_xlim([0, 20])
    ax_pitch.set_ylim([-70, 10])
    ax_pitch.set_xlabel('Time [s]')
    ax_pitch.set_ylabel('Pitch [deg]')
    ax_pitch.set_title('Pitch Angle')
    ax_pitch.grid(True, alpha=0.3)
    ax_pitch.legend()

    # Alpha history
    ax_alpha.plot(t[:frame+1], np.rad2deg(alpha[:frame+1]), 'b-', linewidth=2)
    ax_alpha.plot(t[frame], np.rad2deg(alpha[frame]), 'ro', markersize=8)
    ax_alpha.axhline(y=np.rad2deg(alpha_trim), color='k', linestyle='--',
                    alpha=0.5, label='Trim')
    ax_alpha.set_xlim([0, 20])
    ax_alpha.set_ylim([-15, 15])
    ax_alpha.set_xlabel('Time [s]')
    ax_alpha.set_ylabel('Alpha [deg]')
    ax_alpha.set_title('Angle of Attack')
    ax_alpha.grid(True, alpha=0.3)
    ax_alpha.legend()

    # Elevator history
    ax_elev.plot(t[:frame+1], elev[:frame+1], 'g-', linewidth=2)
    ax_elev.plot(t[frame], elev[frame], 'ro', markersize=8)
    ax_elev.set_xlim([0, 20])
    ax_elev.set_ylim([-6, 8])
    ax_elev.set_xlabel('Time [s]')
    ax_elev.set_ylabel('Elevator [deg]')
    ax_elev.set_title('Elevator Input')
    ax_elev.grid(True, alpha=0.3)

    # Add status text
    fig.suptitle(f'nTop Flying Wing - 6-DOF Simulation | Time: {t_curr:.2f}s',
                fontsize=14, fontweight='bold')

    return []

print("Generating animation...")
anim = FuncAnimation(fig, update, frames=len(t), init_func=init,
                    blit=False, repeat=True, interval=100)

# Save as GIF
output_file = Path(__file__).parent / "output" / "ntop_simulation.gif"
output_file.parent.mkdir(exist_ok=True)

print(f"Saving animation to {output_file}...")
writer = PillowWriter(fps=10)
anim.save(output_file, writer=writer)

print(f"\n[OK] Animation saved: {output_file}")
print(f"     Frames: {len(t)}")
print(f"     Duration: 20 seconds")
print(f"     FPS: 10")
print("="*70)
