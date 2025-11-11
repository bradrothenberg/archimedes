# Quick simulation test
from pathlib import Path
import numpy as np

from ntop_vehicle import NTopVehicle
from simulate import CRUISE, create_initial_state, simulate_flight, analyze_flight_data, print_flight_summary

# Load vehicle
data_dir = Path(__file__).parent / "data"
print("Loading vehicle...")
vehicle = NTopVehicle.from_ntop_data(data_dir, max_thrust=2000.0)

print("\nVehicle loaded successfully!")
print(f"  Mass: {vehicle.m:.2f} slug")
print(f"  Wing area: {vehicle.geometry.S:.2f} ft²")
print(f"  Wing span: {vehicle.geometry.b:.2f} ft")

# Create initial state
print(f"\nSetting up {CRUISE.name} flight...")
initial_state = create_initial_state(vehicle, CRUISE, alpha_deg=3.0)

# Define controls
controls = vehicle.Input(
    throttle=0.5,
    elevator=0.0,
    aileron=0.0,
    rudder=0.0,
)

# Run short simulation
print("\nRunning 10-second simulation...")
t_array, states = simulate_flight(
    vehicle, initial_state, controls, t_span=(0.0, 10.0), dt=0.1
)

# Analyze results
flight_data = analyze_flight_data(vehicle, t_array, states)
print_flight_summary(flight_data)

print("\n" + "="*60)
print("SUCCESS! Simulation completed.")
print("="*60)
