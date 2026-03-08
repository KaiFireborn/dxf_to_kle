# DXF/SVG to KLE Converter

This tool converts keyboard layout sketches from Fusion 360 (exported as DXF or SVG) into KLE (Keyboard Layout Editor) format.

## Features

- **DXF Converter** (`converter1.py`): Extracts rounded corner squares from DXF files
  - Automatically fixes common DXF export issues from Fusion 360
  - Calculates center points and rotation values for each key
  - Outputs in KLE JSON format

- **SVG Converter** (`converter_svg.py`): Extracts rounded rectangles from SVG files
  - Parses SVG transform attributes for rotation
  - Supports namespaced SVG elements
  - Outputs in KLE JSON format

## Requirements

```bash
pip install ezdxf numpy
```

## Usage

### DXF Files

```bash
python converter1.py layout_exp.dxf
```

Output:

- Console: List of detected keys with positions and rotations
- File: `layout_exp_kle.json` - KLE format JSON

### SVG Files

```bash
python converter_svg.py layout.svg
```

Output:

- Console: List of detected keys with positions and rotations
- File: `layout_kle.json` - KLE format JSON

## Output Format

The tool outputs coordinates in KLE units (1 unit = 19.05mm):

```json
[
  { "x": -15.798, "y": 21.741, "r": 3.75 },
  { "x": -14.627, "y": 21.179, "r": -79.95 },
  ...
]
```

Where:

- `x`, `y`: Center position in KLE units
- `r`: Rotation angle in degrees (0-360)

You can copy this JSON into KLE (https://keyboard-layout-editor.com/) for visualization.

## Notes

- DXF files exported from Fusion 360 may have corruption issues (malformed group codes). The converter automatically detects and fixes these.
- For SVG files, rectangles must have `rx` or `ry` attributes to be recognized as keys.
- Rotations are extracted from SVG `transform` attributes (rotate function).
- All coordinates are converted to KLE units (1u = 19.05mm standard keyboard unit).

## Tips for Fusion 360 Export

1. Create your keyboard layout with squares of the same size with rounded corners
2. Export as DXF or SVG
3. Run the appropriate converter on the exported file
4. The resulting JSON can be used in KLE or other keyboard design tools
