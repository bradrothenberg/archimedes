"""
Run AVL and extract stability derivatives including neutral point
"""
import subprocess
from pathlib import Path

def run_avl_stability(avl_dir: Path):
    """Run AVL and get stability derivatives"""

    # Commands to send to AVL
    commands = [
        "LOAD uav.avl\n",
        "MASS uav.mass\n",
        "OPER\n",
        "a a 4.17\n",
        "x\n",
        "ST\n",
        "\n",  # Empty line for filename prompt (output to screen)
        "quit\n",
        "quit\n"
    ]

    # Run AVL
    process = subprocess.Popen(
        ['avl'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=avl_dir,
        text=True
    )

    # Send commands
    input_text = ''.join(commands)
    stdout, stderr = process.communicate(input=input_text, timeout=30)

    # Save output
    output_file = avl_dir / 'stability_output.txt'
    with open(output_file, 'w') as f:
        f.write(stdout)

    print(f"Output saved to: {output_file}")

    # Parse for neutral point
    lines = stdout.split('\n')
    in_stability = False
    for i, line in enumerate(lines):
        if 'Neutral point' in line or 'Xnp' in line:
            print(f"\nFound neutral point reference:")
            print(line)
            if i+1 < len(lines):
                print(lines[i+1])
        if 'Cma' in line:
            print(f"\nFound Cma reference:")
            print(line)
        if 'Static margin' in line:
            print(f"\nFound static margin:")
            print(line)

    return stdout

if __name__ == "__main__":
    avl_dir = Path(__file__).parent / "AVL"
    output = run_avl_stability(avl_dir)
