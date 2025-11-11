"""
Generate AVL geometry, mass, and run files from LE/TE point data.
"""

import pandas as pd
import numpy as np
from pathlib import Path


def generate_avl_geometry(le_file: Path, te_file: Path, mass_file: Path,
                          output_file: Path, airfoil: str = "NACA 0012",
                          use_half_wing: bool = True):
    """
    Generate AVL geometry file from leading edge and trailing edge points.

    Args:
        le_file: Path to LEpts.csv
        te_file: Path to TEpts.csv
        mass_file: Path to mass.csv (for CG reference point)
        output_file: Path to output .avl file
        airfoil: Airfoil designation
        use_half_wing: If True, use YDUPLICATE and only define half wing
    """
    # Read data
    le_df = pd.read_csv(le_file)
    te_df = pd.read_csv(te_file)
    mass_df = pd.read_csv(mass_file)

    # Convert to feet
    le_x_ft = le_df['x'].values / 12.0
    le_y_ft = le_df['y'].values / 12.0
    le_z_ft = le_df['z'].values / 12.0
    te_x_ft = te_df['x'].values / 12.0
    te_y_ft = te_df['y'].values / 12.0
    te_z_ft = te_df['z'].values / 12.0

    # Calculate chords
    chords_ft = te_x_ft - le_x_ft

    # Get CG location (reference point)
    CG_x_ft = mass_df['avl_CGx'].values[0] / 12.0
    CG_y_ft = mass_df['avl_CGy'].values[0] / 12.0
    CG_z_ft = mass_df['avl_CGz'].values[0] / 12.0

    # Calculate reference values
    bref = abs(le_y_ft.max() - le_y_ft.min())  # Full span

    # Calculate Sref by integrating trapezoids
    Sref = 0.0
    n_sections = len(le_df)
    center_idx = n_sections // 2

    # Integrate from center to tip on each side
    for i in range(center_idx, n_sections - 1):
        dy = abs(le_y_ft[i+1] - le_y_ft[i])
        c1 = chords_ft[i]
        c2 = chords_ft[i+1]
        Sref += 0.5 * (c1 + c2) * dy
    Sref *= 2  # Both sides

    # Calculate mean aerodynamic chord (area-weighted)
    cref = Sref / bref

    print(f"Wing geometry:")
    print(f"  Span (Bref): {bref:.4f} ft")
    print(f"  Area (Sref): {Sref:.4f} ft²")
    print(f"  MAC (Cref):  {cref:.4f} ft")
    print(f"  Root chord:  {chords_ft[center_idx]:.4f} ft")
    print(f"  Tip chord:   {chords_ft[0]:.4f} ft")
    print(f"  CG location: ({CG_x_ft:.4f}, {CG_y_ft:.4f}, {CG_z_ft:.4f}) ft")

    # Determine which sections to use
    if use_half_wing:
        # Use only right half (center to tip): indices center_idx to end
        section_indices = range(center_idx, n_sections)
    else:
        # Use all sections
        section_indices = range(n_sections)

    # Start building AVL file
    lines = []
    lines.append("nTop Flying Wing")
    lines.append("#Mach")
    lines.append("    0.000")
    lines.append("#IYsym   IZsym   Zsym")
    lines.append(" 0      0       0.0")
    lines.append("#Sref    Cref    Bref")
    lines.append(f"   {Sref:.4f}     {cref:.4f}     {bref:.4f}")
    lines.append("#Xref    Yref    Zref")
    lines.append(f"    {CG_x_ft:.4f}     {CG_y_ft:.4f}      {CG_z_ft:.4f}")
    lines.append("#CDp (optional)")
    lines.append("    0.00000")
    lines.append("#")
    lines.append("#" + "="*60)
    lines.append("SURFACE")
    lines.append("Wing")
    lines.append("#Nchordwise  Cspace  [Nspanwise  Sspace]")

    # For half wing, we have 7 sections (6 gaps), need at least 2 panels per gap
    # Use more panels for better resolution
    n_sections_used = len(list(section_indices))
    n_gaps = n_sections_used - 1
    n_spanwise = max(20, n_gaps * 3)  # At least 3 panels per gap
    lines.append(f"  12         1.00      {n_spanwise}        1.00")
    lines.append("#")
    lines.append("COMPONENT")
    lines.append(" 1")
    lines.append("#")

    if use_half_wing:
        lines.append("YDUPLICATE")
        lines.append("     0.0000")
        lines.append("#")

    # Add sections
    for idx in section_indices:
        lines.append("#" + "-"*17)
        lines.append("SECTION")
        lines.append("#Xle     Yle      Zle      Chord    Ainc")
        lines.append(f"  {le_x_ft[idx]:7.4f}  {le_y_ft[idx]:7.4f}  {le_z_ft[idx]:7.4f}  {chords_ft[idx]:7.4f}   0.00")
        lines.append("#")
        # Use NACA keyword for NACA airfoils (AVL generates them)
        # Use AFIL for airfoil data files
        if airfoil.startswith("NACA"):
            lines.append("NACA")
            lines.append(f" {airfoil.replace('NACA ', '')}")
        else:
            lines.append("AFIL")
            lines.append(f" {airfoil}")
        lines.append("#")

        # Add control surfaces to outer sections
        if use_half_wing:
            # For half wing, add flaperon to outer 2 sections
            if idx >= n_sections - 2:
                lines.append("CONTROL")
                lines.append("#name     gain    Xhinge  XYZhvec  SgnDup")
                lines.append(" flaperon  1.000   0.750   0.0  0.0  0.0   -1.00")
                lines.append("#")

    lines.append("")

    # Write file
    with open(output_file, 'w') as f:
        f.write('\n'.join(lines))

    print(f"\nGenerated AVL file: {output_file}")
    print(f"  Using {'half' if use_half_wing else 'full'} wing with {n_sections_used} sections")

    return Sref, cref, bref, CG_x_ft, CG_y_ft, CG_z_ft


def generate_mass_file(mass_csv: Path, output_file: Path):
    """
    Generate AVL .mass file from mass.csv

    Args:
        mass_csv: Path to mass.csv
        output_file: Path to output .mass file
    """
    # Read mass data
    mass_df = pd.read_csv(mass_csv)

    mass_lbm = mass_df['avl_mass'].values[0]
    mass_slug = mass_lbm / 32.174

    CG_x_ft = mass_df['avl_CGx'].values[0] / 12.0
    CG_y_ft = mass_df['avl_CGy'].values[0] / 12.0
    CG_z_ft = mass_df['avl_CGz'].values[0] / 12.0

    Ixx = mass_df['avl_Ixx'].values[0]
    Iyy = mass_df['avl_Iyy'].values[0]
    Izz = mass_df['avl_Izz'].values[0]

    # Products of inertia (assume zero if not present)
    Ixy = 0.0
    Ixz = 0.0
    Iyz = 0.0

    # The example file shows much smaller inertias - check if ours need conversion
    # The values in mass.csv are slug-ft^2, but they seem very large
    # Let's check if they're actually in slug-in^2 and need conversion
    scale_factor = 1.0 / (12.0 ** 2)  # Convert slug-in^2 to slug-ft^2
    Ixx_ft = Ixx * scale_factor
    Iyy_ft = Iyy * scale_factor
    Izz_ft = Izz * scale_factor

    print(f"\nMass properties:")
    print(f"  Mass: {mass_slug:.2f} slugs ({mass_lbm:.0f} lbm)")
    print(f"  CG: ({CG_x_ft:.4f}, {CG_y_ft:.4f}, {CG_z_ft:.4f}) ft")
    print(f"  Ixx: {Ixx_ft:.1f} slug-ft²")
    print(f"  Iyy: {Iyy_ft:.1f} slug-ft²")
    print(f"  Izz: {Izz_ft:.1f} slug-ft²")

    # Write mass file (single line format like example)
    lines = []
    lines.append("#  nTop Flying Wing Mass File")
    lines.append("#  Units: slugs, feet")
    lines.append("#")
    lines.append("#  mass    x       y       z       Ixx     Iyy     Izz     Ixy     Ixz     Iyz")

    mass_line = f"     {mass_slug:.6f}   {CG_x_ft:.4f}    {CG_y_ft:.4f}    {CG_z_ft:.4f}    "
    mass_line += f"{Ixx_ft:.4f}     {Iyy_ft:.4f}    {Izz_ft:.4f}        "
    mass_line += f"{Ixy:.4f}        {Ixz:.4f}        {Iyz:.4f}"
    lines.append(mass_line)

    with open(output_file, 'w') as f:
        f.write('\n'.join(lines))

    print(f"Generated mass file: {output_file}")

    return mass_slug, CG_x_ft, CG_y_ft, CG_z_ft


def generate_run_file(output_file: Path, alpha_trim: float = 4.17,
                      velocity: float = 484.0, altitude: float = 20000.0,
                      CL_trim: float = 0.244):
    """
    Generate AVL .run file with flight conditions

    Args:
        output_file: Path to output .run file
        alpha_trim: Trim angle of attack (degrees)
        velocity: Velocity (ft/s)
        altitude: Altitude (ft)
        CL_trim: Target lift coefficient
    """
    # Atmospheric properties at altitude
    if altitude <= 36089:  # Troposphere
        T = 518.67 - 0.00356616 * altitude  # Rankine
        p = 2116.22 * (T / 518.67) ** 5.2561  # psf
    else:  # Lower stratosphere
        T = 389.97  # Rankine
        p = 2116.22 * 0.2234 * np.exp((36089 - altitude) / 20806)  # psf

    rho = p / (1716.49 * T)  # slug/ft^3

    # Mach number (speed of sound = sqrt(gamma * R * T))
    a = np.sqrt(1.4 * 1716.49 * T)  # ft/s
    mach = velocity / a

    print(f"\nFlight condition:")
    print(f"  Altitude: {altitude:.0f} ft")
    print(f"  Velocity: {velocity:.1f} ft/s ({velocity * 0.5925:.0f} KTAS)")
    print(f"  Mach: {mach:.3f}")
    print(f"  Density: {rho:.6f} slug/ft³")
    print(f"  Alpha trim: {alpha_trim:.2f}°")
    print(f"  CL trim: {CL_trim:.3f}")

    lines = []
    lines.append("#-------------------------------------------------")
    lines.append("# nTop Flying Wing - AVL Run Case")
    lines.append(f"# Cruise: {altitude:.0f} ft, {velocity * 0.5925:.0f} KTAS")
    lines.append("#-------------------------------------------------")
    lines.append("")
    lines.append("# Run case 1: Cruise")
    lines.append(" ---------------------------------------------")
    lines.append(" Run case  1:   Cruise")
    lines.append("")
    lines.append(f" alpha        ->  alpha       =   {alpha_trim:.2f}    deg")
    lines.append(" beta         ->  beta        =   0.0     deg")
    lines.append(" pb/2V        ->  pb/2V       =   0.0")
    lines.append(" qc/2V        ->  qc/2V       =   0.0")
    lines.append(" rb/2V        ->  rb/2V       =   0.0")
    lines.append("")

    with open(output_file, 'w') as f:
        f.write('\n'.join(lines))

    print(f"Generated run file: {output_file}")


if __name__ == "__main__":
    # Define paths
    base_dir = Path(__file__).parent
    data_dir = base_dir / "data"
    avl_dir = base_dir / "AVL"

    le_file = data_dir / "LEpts.csv"
    te_file = data_dir / "TEpts.csv"
    mass_file = data_dir / "mass.csv"

    avl_output = avl_dir / "uav.avl"
    mass_output = avl_dir / "uav.mass"
    run_output = avl_dir / "uav.run"

    print("="*70)
    print("Generating AVL files from LE/TE point data")
    print("="*70)

    # Generate AVL geometry (using half-wing with YDUPLICATE)
    Sref, cref, bref, CG_x, CG_y, CG_z = generate_avl_geometry(
        le_file, te_file, mass_file, avl_output,
        airfoil="NACA 0012",
        use_half_wing=True
    )

    # Generate mass file
    mass_slug, CG_x, CG_y, CG_z = generate_mass_file(mass_file, mass_output)

    # Generate run file
    generate_run_file(
        run_output,
        alpha_trim=4.17,
        velocity=484.0,
        altitude=20000.0,
        CL_trim=0.244
    )

    print("\n" + "="*70)
    print("AVL files generated successfully!")
    print("="*70)
    print(f"\nTo use in AVL:")
    print(f"  cd {avl_dir}")
    print(f"  avl")
    print(f"  LOAD uav.avl")
    print(f"  MASS uav.mass")
    print(f"  OPER")
    print(f"  a a 4.17")
    print(f"  x")
