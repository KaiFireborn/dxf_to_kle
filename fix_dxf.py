import re


def fix_dxf(input_file, output_file):
    """Fix malformed DXF file by correcting invalid group codes."""

    with open(input_file, "r") as f:
        content = f.read()

    # Fix "44x" to "44"
    content = content.replace("44x\n", "44\n")

    # Make sure there are no other malformed group codes (2-digit number followed by letter that isn't part of a value)
    # This is a simple fix; more complex validation might be needed

    with open(output_file, "w") as f:
        f.write(content)

    print(f"Fixed DXF file saved to {output_file}")


if __name__ == "__main__":
    fix_dxf("layout_exp.dxf", "layout_exp_fixed.dxf")
