from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT / "transit_nexus_v3.json"
BLEND_PATH = ROOT / "transit_nexus_v3.blend"
GAMEPLAY_PATH = ROOT / "transit_nexus_v3_gameplay.png"
SHOWCASE_PATH = ROOT / "transit_nexus_v3_showcase.png"
LAYOUT_PATH = ROOT / "transit_nexus_v3_layout.png"


def read_plan() -> dict:
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def material(name: str, color: tuple[float, float, float, float], metallic: float = 0.0, roughness: float = 0.5, emission: tuple[float, float, float, float] | None = None, emission_strength: float = 0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
        if emission:
            emission_input = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
            if emission_input:
                emission_input.default_value = emission
            strength_input = bsdf.inputs.get("Emission Strength")
            if strength_input:
                strength_input.default_value = emission_strength
    return mat


def collection(name: str):
    result = bpy.data.collections.get(name)
    if result is None:
        result = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(result)
    return result


def move_to_collection(obj, target) -> None:
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    target.objects.link(obj)


def cube(name: str, location: tuple[float, float, float], dimensions: tuple[float, float, float], mat, target, bevel: float = 0.0):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    move_to_collection(obj, target)
    if bevel:
        modifier = obj.modifiers.new("Soft industrial edges", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
    return obj


def cylinder(name: str, location: tuple[float, float, float], radius: float, depth: float, mat, target, vertices: int = 32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    move_to_collection(obj, target)
    bevel = obj.modifiers.new("Rounded technical edge", "BEVEL")
    bevel.width = min(0.08, depth * 0.3)
    bevel.segments = 2
    return obj


def cell_center(cell: tuple[int, int], cell_world: float) -> tuple[float, float]:
    return ((cell[0] + 0.5) * cell_world, (cell[1] + 0.5) * cell_world)


def add_light(name: str, location: tuple[float, float, float], color: tuple[float, float, float], energy: float, radius: float, target):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.color = color
    data.shape = "DISK"
    data.size = radius
    obj = bpy.data.objects.new(name, data)
    target.objects.link(obj)
    obj.location = location
    return obj


def look_at(obj, target: tuple[float, float, float]) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_camera(name: str, location: tuple[float, float, float], target: tuple[float, float, float], ortho_scale: float, target_collection):
    data = bpy.data.cameras.new(name)
    data.type = "ORTHO"
    data.ortho_scale = ortho_scale
    camera = bpy.data.objects.new(name, data)
    target_collection.objects.link(camera)
    camera.location = location
    look_at(camera, target)
    return camera


def build_scene(plan: dict) -> None:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for datablocks in (bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGBA"
    scene.world.color = (0.005, 0.012, 0.025)
    scene.view_settings.look = "AgX - Medium High Contrast"

    ground_collection = collection("01_Ground_Grid")
    route_collection = collection("02_Spiral_Lane")
    decor_collection = collection("03_Corporate_Industrial_Decor")
    light_collection = collection("04_Lighting")
    camera_collection = collection("05_Cameras")

    navy = material("Navy floor", (0.018, 0.055, 0.082, 1), metallic=0.35, roughness=0.42)
    buildable_mat = material("Buildable blue steel", (0.028, 0.095, 0.13, 1), metallic=0.5, roughness=0.38)
    blocked_mat = material("Blocked anthracite", (0.065, 0.075, 0.10, 1), metallic=0.75, roughness=0.32)
    road_mat = material("Spiral lane", (0.035, 0.18, 0.23, 1), metallic=0.5, roughness=0.28)
    cyan_mat = material("Cyan lane edge", (0.01, 0.35, 0.43, 1), metallic=0.25, roughness=0.2, emission=(0.01, 0.55, 0.7, 1), emission_strength=4.0)
    violet_mat = material("Violet corporate accent", (0.20, 0.035, 0.36, 1), metallic=0.45, roughness=0.25, emission=(0.38, 0.04, 0.8, 1), emission_strength=3.5)
    orange_mat = material("Orange warning", (0.75, 0.18, 0.025, 1), metallic=0.35, roughness=0.3, emission=(0.9, 0.08, 0.015, 1), emission_strength=2.5)
    core_mat = material("Corporate core", (0.22, 0.20, 0.08, 1), metallic=0.7, roughness=0.25, emission=(0.8, 0.42, 0.04, 1), emission_strength=2.5)
    metal_mat = material("Industrial metal", (0.12, 0.15, 0.19, 1), metallic=0.85, roughness=0.3)

    cols = int(plan["grid"]["columns"])
    rows = int(plan["grid"]["rows"])
    cell_world = float(plan["grid"]["cell_size_world"])
    route = {tuple(cell) for cell in plan["route"]["cells"]}
    blocked = {tuple(cell) for cell in plan["areas"]["blocked_cells"]}
    buildable = {tuple(cell) for cell in plan["areas"]["buildable_cells"]}
    base = tuple(plan["base"]["cell"])
    turn_cells = {tuple(cell) for cell in plan["route"]["turn_cells"]}

    for y in range(rows):
        for x in range(cols):
            cell = (x, y)
            cx, cy = cell_center(cell, cell_world)
            if cell in route:
                tile_mat = navy
            elif cell in blocked:
                tile_mat = blocked_mat
            elif cell in buildable:
                tile_mat = buildable_mat
            else:
                tile_mat = navy
            cube(f"Cell_{x:02d}_{y:02d}", (cx, cy, -0.18), (cell_world * 0.98, cell_world * 0.98, 0.36), tile_mat, ground_collection, bevel=0.08)
            if cell in blocked and (x + y) % 2 == 0:
                cube(f"WarningStripe_{x:02d}_{y:02d}", (cx, cy, 0.03), (cell_world * 0.72, 0.08, 0.04), orange_mat, decor_collection, bevel=0.02)

    directions = ((1, 0, "east"), (-1, 0, "west"), (0, 1, "south"), (0, -1, "north"))
    for x, y in route:
        cx, cy = cell_center((x, y), cell_world)
        cube(f"Lane_{x:02d}_{y:02d}", (cx, cy, 0.16), (cell_world * 0.78, cell_world * 0.78, 0.18), road_mat, route_collection, bevel=0.12)
        for dx, dy, side in directions:
            if (x + dx, y + dy) not in route:
                if dx:
                    cube(f"LaneEdge_{x:02d}_{y:02d}_{side}", (cx + dx * cell_world * 0.39, cy, 0.28), (0.07, cell_world * 0.70, 0.09), cyan_mat, route_collection, bevel=0.025)
                else:
                    cube(f"LaneEdge_{x:02d}_{y:02d}_{side}", (cx, cy + dy * cell_world * 0.39, 0.28), (cell_world * 0.70, 0.07, 0.09), cyan_mat, route_collection, bevel=0.025)
        if (x, y) in turn_cells:
            cylinder(f"RoundedTurn_{x:02d}_{y:02d}", (cx, cy, 0.30), cell_world * 0.31, 0.08, cyan_mat, route_collection)

    # Low separators make adjacent spiral loops readable without blocking the lane.
    for x, y in sorted(buildable):
        neighbours = sum((x + dx, y + dy) in route for dx, dy, _ in directions)
        if neighbours >= 2 and (x + y) % 3 == 0:
            cx, cy = cell_center((x, y), cell_world)
            cube(f"Divider_{x:02d}_{y:02d}", (cx, cy, 0.22), (cell_world * 0.42, cell_world * 0.12, 0.28), metal_mat, decor_collection, bevel=0.04)

    # Machines are placed from buildable cells, so decorations never cover the actual lane.
    machine_candidates = sorted(buildable, key=lambda cell: (cell[1], cell[0]))
    for index, (x, y) in enumerate(machine_candidates):
        if index % 37 != 0 or x < 2 or x > 27 or y < 3 or y > 15:
            continue
        cx, cy = cell_center((x, y), cell_world)
        cube(f"CoolingUnit_{x:02d}_{y:02d}", (cx, cy, 0.44), (cell_world * 0.34, cell_world * 0.34, 0.62), metal_mat, decor_collection, bevel=0.07)
        cube(f"CoolingGlow_{x:02d}_{y:02d}", (cx, cy - cell_world * 0.18, 0.76), (cell_world * 0.18, 0.05, 0.08), violet_mat, decor_collection, bevel=0.02)

    # Core platform and corporate base remain visibly above the floor but below creeps/towers in the game.
    bx, by = cell_center(base, cell_world)
    cylinder("Central_Corporate_Platform", (bx, by, 0.11), cell_world * 2.5, 0.22, core_mat, decor_collection)
    cylinder("Central_Core_Ring", (bx, by, 0.31), cell_world * 1.75, 0.08, orange_mat, decor_collection)
    cube("Central_Core_Tower", (bx, by, 0.76), (cell_world * 0.9, cell_world * 0.9, 0.85), metal_mat, decor_collection, bevel=0.12)
    cube("Central_Core_Glow", (bx, by, 1.22), (cell_world * 0.5, cell_world * 0.5, 0.08), cyan_mat, decor_collection, bevel=0.02)

    sx, sy = cell_center(tuple(plan["spawn"]["cell"]), cell_world)
    cylinder("Spawn_Ring", (sx, sy, 0.33), cell_world * 0.42, 0.08, violet_mat, decor_collection)

    add_light("Cyan_Core_Light", (bx, by, 8.0), (0.04, 0.55, 0.8), 900, 14.0, light_collection)
    add_light("Violet_Outer_Light", (cell_world * 6, cell_world * 4, 6.0), (0.35, 0.05, 0.8), 650, 18.0, light_collection)
    add_light("Orange_Base_Light", (bx, by, 4.0), (0.9, 0.25, 0.04), 500, 8.0, light_collection)

    center = (cols * cell_world / 2.0, rows * cell_world / 2.0, 0.0)
    gameplay_camera = add_camera("Camera_Gameplay_Orthographic", (center[0], center[1], 42.0), center, 38.0, camera_collection)
    showcase_camera = add_camera("Camera_Showcase_Orthographic", (center[0] + 12.0, center[1] - 24.0, 32.0), center, 43.0, camera_collection)
    layout_camera = add_camera("Camera_Layout_Orthographic", (center[0], center[1], 42.0), center, 38.0, camera_collection)
    scene.camera = gameplay_camera
    scene["transit_nexus_id"] = plan["id"]
    scene["transit_nexus_json"] = str(JSON_PATH)
    scene["transit_nexus_route_length"] = plan["route"]["route_length"]
    scene["transit_nexus_grid"] = f"{cols}x{rows}"
    scene["transit_nexus_note"] = "Gameplay route is sourced from JSON; render is visual only."

    scene.render.filepath = str(GAMEPLAY_PATH)
    scene.camera = gameplay_camera
    bpy.ops.render.render(write_still=True)
    scene.render.filepath = str(SHOWCASE_PATH)
    scene.camera = showcase_camera
    bpy.ops.render.render(write_still=True)
    scene.render.filepath = str(LAYOUT_PATH)
    scene.camera = layout_camera
    bpy.ops.render.render(write_still=True)
    scene.camera = gameplay_camera
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))


def main() -> None:
    build_scene(read_plan())
    print(f"Created {BLEND_PATH}")
    print(f"Created {GAMEPLAY_PATH}")
    print(f"Created {SHOWCASE_PATH}")
    print(f"Created {LAYOUT_PATH}")


if __name__ == "__main__":
    main()
