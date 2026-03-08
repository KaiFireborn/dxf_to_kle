import ezdxf
import numpy as np
import math
import sys
import json
import os
import tempfile
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# keyboard unit (1u)
KLE_UNIT_MM = 19.05


def polygon_center(points):
    """Return centroid of polygon."""
    pts = np.array(points)
    return pts.mean(axis=0)


def fix_dxf_file(filename):
    """Fix common DXF corruption issues from Fusion 360 exports."""
    try:
        with open(filename, "r") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return filename

    original_content = content
    content = content.replace("44x\n", "44\n")

    if content != original_content:
        fd, temp_path = tempfile.mkstemp(suffix=".dxf", text=True)
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
            print(f"Fixed DXF issues. Using corrected file.")
            return temp_path
        except Exception as e:
            print(f"Error writing fixed DXF: {e}")
            return filename

    return filename


def edge_orientation(points):
    """Estimate rotation from longest edge."""
    longest = 0
    angle = 0

    for i in range(len(points)):
        p1 = np.array(points[i])
        p2 = np.array(points[(i + 1) % len(points)])

        v = p2 - p1
        length = np.linalg.norm(v)

        if length > longest:
            longest = length
            angle = math.degrees(math.atan2(v[1], v[0]))

    return angle


def process_polyline(entity):
    """Extract center + rotation from LWPOLYLINE."""
    points = []

    for v in entity.get_points():
        x, y = v[0], v[1]
        points.append((x, y))

    if len(points) < 4:
        return None

    # Filter out very small shapes
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)

    min_size_mm = 7.6
    if width < min_size_mm or height < min_size_mm:
        return None

    cx, cy = polygon_center(points)
    rot = edge_orientation(points)

    return cx, cy, rot


def normalize_rotation(r):
    """Normalize rotation for square keys to [-45, 45] range."""
    r = ((r + 180) % 360) - 180

    while r > 45:
        r -= 90
    while r < -45:
        r += 90

    return r


def spatial_distance(key1, key2):
    """Calculate Euclidean distance between two keys."""
    x1, y1, _ = key1
    x2, y2, _ = key2
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def order_keys_spatial(keys):
    """Reorder keys so adjacent keys in list are spatially close (nearest-neighbor traversal)."""
    if not keys:
        return keys

    ordered = []
    remaining = list(range(len(keys)))

    # Start from the key closest to origin (0, 0)
    start_idx = min(remaining, key=lambda i: spatial_distance(keys[i], (0, 0, 0)))
    current_idx = start_idx
    ordered.append(current_idx)
    remaining.remove(current_idx)

    # Greedily add nearest unvisited key
    while remaining:
        nearest_idx = min(
            remaining, key=lambda i: spatial_distance(keys[current_idx], keys[i])
        )
        ordered.append(nearest_idx)
        remaining.remove(nearest_idx)
        current_idx = nearest_idx

    # Return keys in this spatial order with remapped IDs
    return [keys[i] for i in ordered], ordered


def to_kle_json_format(keys, author="kf", name="Keyboard Layout"):
    """Convert keys [x, y, rotation] to KLE JSON format with row-based layout.

    Each key starts its own row with absolute rx, ry (rotation center) positioning.
    """
    kle_data = [{"author": author, "name": name}]

    for idx, (x, y, r) in enumerate(keys):
        # Each key is its own row (first/only key in row)
        key_props = {
            "rx": round(x, 6),  # Rotation center x (absolute position)
            "ry": round(y, 6),  # Rotation center y (absolute position)
            "r": round(r, 2),  # Rotation angle
            "x": -0.5,  # Offset to center 1u key at rotation center
            "y": -0.5,  # Offset to center 1u key at rotation center
        }
        label = str(idx)
        kle_data.append([key_props, label])

    return kle_data


def to_simple_format(keys):
    """Convert keys to simple format: just x, y, r for each key."""
    simple_data = []
    for x, y, r in keys:
        simple_data.append(
            {
                "x": round(x, 6),
                "y": round(y, 6),
                "r": round(r, 2),
            }
        )
    return simple_data


def visualize_layout(keys, output_file_path):
    """Visualize the keyboard layout with key positions and rotations.

    Note: Keys are drawn at 14mm / 19.05mm ≈ 0.735u per KLE unit,
    representing the actual key size in the 1u spacing grid.
    """
    try:
        fig, ax = plt.subplots(figsize=(14, 8))

        # Actual key size relative to 1u (14mm in 19.05mm grid)
        key_size = 14.0 / 19.05  # ≈ 0.735u

        # Plot each key
        for x, y, r in keys:
            # Create rectangle centered at (x, y)
            rect = patches.Rectangle(
                (x - key_size / 2, y - key_size / 2),
                key_size,
                key_size,
                linewidth=1.5,
                edgecolor="black",
                facecolor="lightblue",
                angle=r,
                rotation_point="center",
            )
            ax.add_patch(rect)

            # Add rotation indicator (small line from center)
            line_len = key_size * 0.4
            angle_rad = math.radians(r)
            dx = line_len * math.cos(angle_rad)
            dy = line_len * math.sin(angle_rad)
            ax.plot([x, x + dx], [y, y + dy], "r-", linewidth=2)

        # Set aspect and limits
        ax.set_aspect("equal")
        all_x = [k[0] for k in keys]
        all_y = [k[1] for k in keys]
        margin = 2
        ax.set_xlim(min(all_x) - margin, max(all_x) + margin)
        ax.set_ylim(min(all_y) - margin, max(all_y) + margin)
        ax.invert_yaxis()

        ax.set_xlabel("X (KLE units, 1u = 19.05mm)")
        ax.set_ylabel("Y (KLE units, 1u = 19.05mm)")
        ax.set_title("Keyboard Layout Visualization (Keys are 14mm in 19.05mm grid)")

        # Add grid with 1u spacing
        ax.grid(True, alpha=0.3, linestyle="-", linewidth=0.5)
        ax.set_axisbelow(True)

        plt.savefig(output_file_path, dpi=150, bbox_inches="tight")
        print(f"Layout visualization saved to: {output_file_path}")
        plt.close()

    except Exception as e:
        print(f"Warning: Could not create visualization: {e}")


def get_output_path(filename, output_dir="output"):
    """Get the output directory path and ensure it exists."""
    # Use absolute path of the input file to ensure consistent behavior
    abs_filename = os.path.abspath(filename)
    base_dir = os.path.dirname(abs_filename)
    output_path = os.path.join(base_dir, output_dir)
    os.makedirs(output_path, exist_ok=True)
    return output_path


def output_file(output_dir, original_filename, suffix):
    """Create a filepath in the output directory."""
    basename = os.path.basename(os.path.splitext(original_filename)[0])
    return os.path.join(output_dir, basename + suffix)


def main(filename):
    original_filename = filename
    filename = fix_dxf_file(filename)

    # Create output directory
    output_dir = get_output_path(original_filename)

    doc = ezdxf.readfile(filename)
    msp = doc.modelspace()

    keys = []

    for e in msp:
        if e.dxftype() == "LWPOLYLINE":
            result = process_polyline(e)

            if result:
                cx, cy, rot = result
                # Convert DXF coordinates (in mm) to KLE units (1u = 19.05mm)
                kle_x = cx / KLE_UNIT_MM
                kle_y = cy / KLE_UNIT_MM
                rot = normalize_rotation(rot)
                keys.append((kle_x, kle_y, rot))

    # Remove duplicates
    unique_keys = []
    for x, y, r in keys:
        is_duplicate = any(
            abs(x - ux) < 0.01 and abs(y - uy) < 0.01 for ux, uy, ur in unique_keys
        )
        if not is_duplicate:
            unique_keys.append((x, y, r))

    keys = unique_keys

    print(f"\nDetected {len(keys)} keys\n")

    # Normalize coordinates (start from 0,0)
    if keys:
        all_x = [k[0] for k in keys]
        all_y = [k[1] for k in keys]
        min_x = min(all_x)
        min_y = min(all_y)

        keys = [(x - min_x, y - min_y, r) for x, y, r in keys]

    # Order keys spatially (adjacent keys in output are close together)
    keys_ordered, order_indices = order_keys_spatial(keys)

    # Export as proper KLE JSON format (original order)
    print("Generating exports...")
    kle_json = to_kle_json_format(keys, author="kf", name="Lieserl")
    kle_json_file = output_file(output_dir, original_filename, "_kle.json")
    with open(kle_json_file, "w") as f:
        json.dump(kle_json, f, indent=2)
    print(f"  KLE format JSON (original order) -> {os.path.basename(kle_json_file)}")

    # Export spatially-ordered as proper KLE JSON format
    kle_json_ordered = to_kle_json_format(
        keys_ordered, author="kf", name="Lieserl - Spatially Ordered"
    )
    kle_json_ordered_file = output_file(
        output_dir, original_filename, "_kle_ordered.json"
    )
    with open(kle_json_ordered_file, "w") as f:
        json.dump(kle_json_ordered, f, indent=2)
    print(
        f"  KLE format JSON (spatially ordered) -> {os.path.basename(kle_json_ordered_file)}"
    )

    # Export simple format (just x, y, r for each key)
    simple_json = to_simple_format(keys)
    simple_json_file = output_file(output_dir, original_filename, "_coords.json")
    with open(simple_json_file, "w") as f:
        json.dump(simple_json, f, indent=2)
    print(
        f"  Simple coords JSON (original order) -> {os.path.basename(simple_json_file)}"
    )

    simple_json_ordered = to_simple_format(keys_ordered)
    simple_json_ordered_file = output_file(
        output_dir, original_filename, "_coords_ordered.json"
    )
    with open(simple_json_ordered_file, "w") as f:
        json.dump(simple_json_ordered, f, indent=2)
    print(
        f"  Simple coords JSON (spatially ordered) -> {os.path.basename(simple_json_ordered_file)}"
    )

    # Generate visualizations
    viz_file = output_file(output_dir, original_filename, "_layout.png")
    visualize_layout(keys, viz_file)
    print(f"  Visualization (original order) -> {os.path.basename(viz_file)}")

    viz_ordered_file = output_file(output_dir, original_filename, "_layout_ordered.png")
    visualize_layout(keys_ordered, viz_ordered_file)
    print(
        f"  Visualization (spatially ordered) -> {os.path.basename(viz_ordered_file)}"
    )

    print("\n=== Key List (Original Order) ===")
    for i, (x, y, r) in enumerate(keys):
        print(
            f"{i:3d}: x={x:.3f}u ({x*KLE_UNIT_MM:.2f}mm), y={y:.3f}u ({y*KLE_UNIT_MM:.2f}mm), rotation={r:.2f}°"
        )

    print("\n=== Key List (Spatially Ordered - Adjacent Keys are Close) ===")
    for i, (x, y, r) in enumerate(keys_ordered):
        orig_id = order_indices[i]
        print(
            f"{i:3d} (was {orig_id:2d}): x={x:.3f}u ({x*KLE_UNIT_MM:.2f}mm), y={y:.3f}u ({y*KLE_UNIT_MM:.2f}mm), rotation={r:.2f}°"
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python export_full_layout.py layout.dxf")
        sys.exit(1)

    main(sys.argv[1])
