# SPDX-FileCopyrightText: 2025 nTop Integration
# SPDX-License-Identifier: GPL-3.0-or-later

"""nTop + AVL + XFOIL integration with Archimedes 6-DOF simulator."""

from .aero_deck import AeroDeck
from .avl_interface import AVLConfiguration, AVLInterface
from .geometry import MassProperties, WingGeometry, WingSection, load_ntop_data
from .ntop_aero import FlightCondition, NTopAero
from .ntop_vehicle import NTopVehicle
from .simulate import CLIMB, CRUISE, LANDING, FlightRegime
from .xfoil_interface import XFOILConfiguration, XFOILInterface

__all__ = [
    # Geometry
    "WingGeometry",
    "WingSection",
    "MassProperties",
    "load_ntop_data",
    # AVL
    "AVLInterface",
    "AVLConfiguration",
    # XFOIL
    "XFOILInterface",
    "XFOILConfiguration",
    # Aerodynamics
    "AeroDeck",
    "NTopAero",
    "FlightCondition",
    # Vehicle
    "NTopVehicle",
    # Simulation
    "FlightRegime",
    "CRUISE",
    "CLIMB",
    "LANDING",
]
