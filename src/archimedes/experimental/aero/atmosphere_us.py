"""US customary unit wrapper for StandardAtmosphere1976.

The base StandardAtmosphere1976 uses SI units (meters, Pascals, kg/m³).
This wrapper converts to/from US customary units (feet, lbf/ft², slug/ft³).
"""

from typing import Tuple
import numpy as np

from archimedes import struct
from .atmosphere import StandardAtmosphere1976 as StandardAtmosphere1976SI


@struct
class StandardAtmosphere1976:
    """U.S. Standard Atmosphere, 1976 with US customary units.

    Input: altitude in feet, velocity in ft/s
    Output: Mach number, qbar in lbf/ft²
    """

    # SI-based atmosphere model
    _atmos_si: StandardAtmosphere1976SI = StandardAtmosphere1976SI()

    # Conversion factors
    FT_TO_M: float = 0.3048  # feet to meters
    M_TO_FT: float = 3.28084  # meters to feet
    PA_TO_PSF: float = 0.020885  # Pascals to lbf/ft²
    KG_M3_TO_SLUG_FT3: float = 0.00194032  # kg/m³ to slug/ft³

    # US customary gas constant and gamma
    Rs_us: float = 1716.49  # ft²/(s²·°R) - for air
    gamma: float = 1.4

    def calc_p(self, alt_ft: float) -> float:
        """Compute pressure at altitude [lbf/ft²].

        Args:
            alt_ft: Altitude in feet

        Returns:
            Pressure in lbf/ft²
        """
        alt_m = alt_ft * self.FT_TO_M
        p_pa = self._atmos_si.calc_p(alt_m)
        return p_pa * self.PA_TO_PSF

    def calc_T(self, alt_ft: float) -> float:
        """Compute temperature at altitude [°R].

        Args:
            alt_ft: Altitude in feet

        Returns:
            Temperature in °R (Rankine)
        """
        alt_m = alt_ft * self.FT_TO_M
        T_K = self._atmos_si.calc_T(alt_m)
        return T_K * 1.8  # Kelvin to Rankine

    def calc_rho(self, alt_ft: float) -> float:
        """Compute density at altitude [slug/ft³].

        Args:
            alt_ft: Altitude in feet

        Returns:
            Density in slug/ft³
        """
        p_psf = self.calc_p(alt_ft)
        T_R = self.calc_T(alt_ft)
        return p_psf / (self.Rs_us * T_R)

    def __call__(self, Vt_fps: float, alt_ft: float) -> Tuple[float, float]:
        """Compute Mach number and dynamic pressure.

        Args:
            Vt_fps: True airspeed in ft/s
            alt_ft: Altitude in feet

        Returns:
            Tuple of (Mach number, qbar in lbf/ft²)
        """
        T_R = self.calc_T(alt_ft)
        rho_slug_ft3 = self.calc_rho(alt_ft)

        # Speed of sound in ft/s
        a_fps = np.sqrt(self.gamma * self.Rs_us * T_R)

        # Mach number
        mach = Vt_fps / a_fps

        # Dynamic pressure in lbf/ft²
        qbar = 0.5 * rho_slug_ft3 * Vt_fps**2

        return mach, qbar
