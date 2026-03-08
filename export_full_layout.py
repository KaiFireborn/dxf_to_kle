import ezdxf
import numpy as np
import math
import sys
import json
import os
import tempfile
import matplotlib.pyplot as plt
import matplotlib.patches as patches

KLE_UNIT_MM = 19.05
SWITCH_SIZE_MM = 14.0
MIN_SHAPE_SIZE_MM = 7.6
DEDUP_TOLERANCE = 0.01


def polygon_center(points):
    """Get bounding box center of polygon (handles rounded corners correctly)."""
    pts = np.array(points)
    xs = pts[:, 0]
    ys = pts[:, 1]
    return (np.min(xs) + np.max(xs)) / 2, (np.min(ys) + np.max(ys)) / 2


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

    if content == original_content:
        return filename

    fd, temp_path = tempfile.mkstemp(suffix=".dxf", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        return temp_path
    except Exception as e:
        print(f"Error writing fixed DXF: {e}")
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
    """Extract center and rotation from LWPOLYLINE."""
    points = [(v[0], v[1]) for v in entity.get_points()]
    if len(points) < 4:
        return None

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)

    if width < MIN_SHAPE_SIZE_MM or height < MIN_SHAPE_SIZE_MM:
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
    """Reorder keys using nearest-neighbor traversal so adjacent keys are spatially close."""
    if not keys:
        return keys, []

    ordered = []
    remaining = list(range(len(keys)))
    current_idx = min(remaining, key=lambda i: spatial_distance(keys[i], (0, 0, 0)))
    ordered.append(current_idx)
    remaining.remove(current_idx)

    while remaining:
        nearest_idx = min(
            remaining, key=lambda i: spatial_distance(keys[current_idx], keys[i])
        )
        ordered.append(nearest_idx)
        remaining.remove(nearest_idx)
        current_idx = nearest_idx

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
    return [{"x": round(x, 6), "y": round(y, 6), "r": round(r, 2)} for x, y, r in keys]


def visualize_layout(keys, output_file_path, key_size_u=None):
    """Visualize keyboard layout. key_size_u=None uses 14mm/19.05mm; 1.0 uses full 1u keycaps."""
    if key_size_u is None:
        key_size_u = SWITCH_SIZE_MM / KLE_UNIT_MM
        facecolor = "lightblue"
        indicator_color = "r-"
        title = "Keyboard Layout (14mm Switches in 19.05mm Grid)"
    else:
        facecolor = "lightcoral"
        indicator_color = "darkred"
        title = "Keyboard Layout (Full 1u Keycaps)"

    try:
        fig, ax = plt.subplots(figsize=(14, 8))
        for x, y, r in keys:
            rect = patches.Rectangle(
                (x - key_size_u / 2, y - key_size_u / 2),
                key_size_u,
                key_size_u,
                linewidth=1.5,
                edgecolor="black",
                facecolor=facecolor,
                alpha=0.7 if key_size_u == 1.0 else 1.0,
                angle=r,
                rotation_point="center",
            )
            ax.add_patch(rect)
            line_len = key_size_u * 0.4
            angle_rad = math.radians(r)
            ax.plot(
                [x, x + line_len * math.cos(angle_rad)],
                [y, y + line_len * math.sin(angle_rad)],
                indicator_color,
                linewidth=2,
            )

        ax.set_aspect("equal")
        all_x = [k[0] for k in keys]
        all_y = [k[1] for k in keys]
        margin = 2
        ax.set_xlim(min(all_x) - margin, max(all_x) + margin)
        ax.set_ylim(min(all_y) - margin, max(all_y) + margin)
        ax.invert_yaxis()
        ax.set_xlabel("X (KLE units)")
        ax.set_ylabel("Y (KLE units)")
        ax.set_title(title)
        ax.grid(True, alpha=0.3, linestyle="-", linewidth=0.5)
        ax.set_axisbelow(True)
        plt.savefig(output_file_path, dpi=150, bbox_inches="tight")
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


def ensure_subdirs(output_dir):
    """Create subdirectories for organized export files."""
    subdirs = {}
    for subdir in ["kle", "coords", "preview"]:
        path = os.path.join(output_dir, subdir)
        os.makedirs(path, exist_ok=True)
        subdirs[subdir] = path
    return subdirs


def save_json(filepath, data):
    """Save data to JSON file."""
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def extract_keys_from_dxf(doc):
    """Extract keys from DXF document."""
    keys = []
    for entity in doc.modelspace():
        if entity.dxftype() == "LWPOLYLINE":
            result = process_polyline(entity)
            if result:
                cx, cy, rot = result
                kle_x = cx / KLE_UNIT_MM
                kle_y = cy / KLE_UNIT_MM
                rot = normalize_rotation(rot)
                keys.append((kle_x, kle_y, rot))
    return keys


def deduplicate_keys(keys):
    """Remove duplicate keys within tolerance."""
    unique = []
    for x, y, r in keys:
        if not any(
            abs(x - ux) < DEDUP_TOLERANCE and abs(y - uy) < DEDUP_TOLERANCE
            for ux, uy, _ in unique
        ):
            unique.append((x, y, r))
    return unique


def normalize_to_origin(keys):
    """Translate keys so minimum coordinates are at origin."""
    if not keys:
        return keys
    all_x = [k[0] for k in keys]
    all_y = [k[1] for k in keys]
    min_x, min_y = min(all_x), min(all_y)
    return [(x - min_x, y - min_y, r) for x, y, r in keys]


def main(filename):
    original_filename = filename
    filename = fix_dxf_file(filename)
    output_dir = get_output_path(original_filename)
    subdirs = ensure_subdirs(output_dir)
    basename = os.path.basename(os.path.splitext(original_filename)[0])

    doc = ezdxf.readfile(filename)
    keys = extract_keys_from_dxf(doc)
    keys = deduplicate_keys(keys)
    keys = normalize_to_origin(keys)
    keys_ordered, order_indices = order_keys_spatial(keys)

    print(f"Detected {len(keys)} keys\n")
    print("Generating exports...")

    for keys_set, label in [(keys, ""), (keys_ordered, "_ordered")]:
        kle_file = os.path.join(subdirs["kle"], f"{basename}_kle{label}.json")
        save_json(kle_file, to_kle_json_format(keys_set, author="kf", name="Lieserl"))
        print(f"  kle/{os.path.basename(kle_file)}")

        coords_file = os.path.join(subdirs["coords"], f"{basename}_coords{label}.json")
        save_json(coords_file, to_simple_format(keys_set))
        print(f"  coords/{os.path.basename(coords_file)}")

        viz_file = os.path.join(subdirs["preview"], f"{basename}_layout{label}.png")
        visualize_layout(keys_set, viz_file)
        print(f"  preview/{os.path.basename(viz_file)}")

        viz_full_u_file = os.path.join(
            subdirs["preview"], f"{basename}_layout_full_u{label}.png"
        )
        visualize_layout(keys_set, viz_full_u_file, key_size_u=1.0)
        print(f"  preview/{os.path.basename(viz_full_u_file)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python export_full_layout.py layout.dxf")
        sys.exit(1)

    main(sys.argv[1])
