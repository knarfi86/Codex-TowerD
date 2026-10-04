from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

Grid = Tuple[int, int]

@dataclass(frozen=True)
class MapDefinition:
    key: str
    title: str
    subtitle: str
    paths: Tuple[Tuple[Grid, ...], ...]
    pads: Tuple[Grid, ...]
    terrain: str
    layout_mode: str = "fixed"
    grid_size: Tuple[int, int] = (20, 12)
    junctions: Tuple[Grid, ...] = ()


def buildable_cells(
    paths: Tuple[Tuple[Grid, ...], ...],
    blocked: Iterable[Grid] = (),
    grid_size: Tuple[int, int] = (20, 12),
) -> Tuple[Grid, ...]:
    occupied = {cell for route in paths for cell in route}
    occupied.update(blocked)
    return tuple(
        (x, y)
        for y in range(grid_size[1])
        for x in range(grid_size[0])
        if (x, y) not in occupied
    )


def line(a: Grid, b: Grid) -> List[Grid]:
    """Axis-aligned inclusive grid segment."""
    ax, ay = a
    bx, by = b
    result: List[Grid] = []
    if ax == bx:
        step = 1 if by >= ay else -1
        result = [(ax, y) for y in range(ay, by + step, step)]
    elif ay == by:
        step = 1 if bx >= ax else -1
        result = [(x, ay) for x in range(ax, bx + step, step)]
    else:
        raise ValueError("Only axis-aligned segments are supported")
    return result


def join(*segments: Iterable[Grid]) -> Tuple[Grid, ...]:
    out: List[Grid] = []
    for segment in segments:
        for cell in segment:
            if not out or out[-1] != cell:
                out.append(cell)
    return tuple(out)

# Every route shares a spawn and castle but differs at forks. Paths intentionally
# overlap at junctions, giving the simulation a readable, branching grid topology.
ARENA_ROUTES = (
    join(line((0, 5), (3, 5)), line((3, 5), (3, 2)), line((3, 2), (8, 2)), line((8, 2), (8, 8)), line((8, 8), (14, 8)), line((14, 8), (14, 4)), line((14, 4), (19, 4))),
    join(line((0, 5), (3, 5)), line((3, 5), (3, 8)), line((3, 8), (6, 8)), line((6, 8), (6, 3)), line((6, 3), (12, 3)), line((12, 3), (12, 7)), line((12, 7), (19, 7))),
    join(line((0, 5), (5, 5)), line((5, 5), (5, 10)), line((5, 10), (10, 10)), line((10, 10), (10, 5)), line((10, 5), (15, 5)), line((15, 5), (15, 7)), line((15, 7), (19, 7))),
)

RIVER_DELTA = MapDefinition(
    key="arena",
    title="Creep Arena",
    subtitle="Offenes Grid, viele Bauzellen, drei Laufwege",
    terrain="arena",
    paths=ARENA_ROUTES,
    pads=buildable_cells(ARENA_ROUTES),
)

SUNKEN_PASS = MapDefinition(
    key="pass",
    title="Versunkener Pass",
    subtitle="Eine Schleife um die Ruinen",
    terrain="ruins",
    paths=(
        join(line((0, 2), (4, 2)), line((4, 2), (4, 5)), line((4, 5), (8, 5)), line((8, 5), (8, 2)), line((8, 2), (14, 2)), line((14, 2), (14, 7)), line((14, 7), (19, 7))),
        join(line((0, 2), (4, 2)), line((4, 2), (4, 7)), line((4, 7), (8, 7)), line((8, 7), (8, 9)), line((8, 9), (14, 9)), line((14, 9), (14, 7)), line((14, 7), (19, 7))),
        join(line((0, 2), (6, 2)), line((6, 2), (6, 5)), line((6, 5), (10, 5)), line((10, 5), (10, 7)), line((10, 7), (19, 7))),
    ),
    pads=((1,1),(1,3),(3,1),(3,4),(3,6),(3,8),(5,4),(5,6),(7,1),(7,3),(7,6),(7,8),(9,4),(9,6),(9,8),(11,1),(11,3),(11,6),(11,8),(13,1),(13,3),(13,6),(13,8),(15,6),(15,8),(17,6),(17,8)),
)

EMBER_FORGE = MapDefinition(
    key="forge",
    title="Glut-Schmiede",
    subtitle="Doppelte Kraterroute mit Feuergraben",
    terrain="lava",
    paths=(
        join(line((0, 9), (3, 9)), line((3, 9), (3, 6)), line((3, 6), (7, 6)), line((7, 6), (7, 3)), line((7, 3), (13, 3)), line((13, 3), (13, 6)), line((13, 6), (19, 6))),
        join(line((0, 9), (3, 9)), line((3, 9), (3, 10)), line((3, 10), (9, 10)), line((9, 10), (9, 7)), line((9, 7), (13, 7)), line((13, 7), (13, 6)), line((13, 6), (19, 6))),
        join(line((0, 9), (5, 9)), line((5, 9), (5, 7)), line((5, 7), (9, 7)), line((9, 7), (9, 5)), line((9, 5), (15, 5)), line((15, 5), (15, 6)), line((15, 6), (19, 6))),
    ),
    pads=((1,8),(1,10),(2,7),(2,10),(4,5),(4,7),(4,8),(4,11),(6,5),(6,8),(6,9),(6,11),(8,2),(8,4),(8,6),(8,8),(10,2),(10,4),(10,6),(10,8),(12,2),(12,4),(12,6),(12,8),(14,4),(14,7),(14,8),(16,5),(16,7),(18,5),(18,7)),
)

FROSTKLAMM_ROUTES = (
    join(line((0, 1), (6, 1)), line((6, 1), (6, 6)), line((6, 6), (12, 6)), line((12, 6), (12, 2)), line((12, 2), (17, 2)), line((17, 2), (17, 10)), line((17, 10), (19, 10))),
    join(line((0, 1), (4, 1)), line((4, 1), (4, 9)), line((4, 9), (10, 9)), line((10, 9), (10, 4)), line((10, 4), (14, 4)), line((14, 4), (14, 10)), line((14, 10), (19, 10))),
    join(line((0, 1), (2, 1)), line((2, 1), (2, 7)), line((2, 7), (8, 7)), line((8, 7), (8, 10)), line((8, 10), (12, 10)), line((12, 10), (12, 8)), line((12, 8), (16, 8)), line((16, 8), (16, 10)), line((16, 10), (19, 10))),
)

FROSTKLAMM = MapDefinition(
    key="frost",
    title="Frostklamm",
    subtitle="Eisige Serpentinen, offenes Baufeld",
    terrain="ice",
    paths=FROSTKLAMM_ROUTES,
    pads=buildable_cells(FROSTKLAMM_ROUTES),
)

SANDSTURM_ROUTES = (
    join(line((0, 10), (4, 10)), line((4, 10), (4, 6)), line((4, 6), (9, 6)), line((9, 6), (9, 10)), line((9, 10), (14, 10)), line((14, 10), (14, 3)), line((14, 3), (19, 3)), line((19, 3), (19, 1))),
    join(line((0, 10), (6, 10)), line((6, 10), (6, 8)), line((6, 8), (11, 8)), line((11, 8), (11, 5)), line((11, 5), (16, 5)), line((16, 5), (16, 1)), line((16, 1), (19, 1))),
    join(line((0, 10), (2, 10)), line((2, 10), (2, 5)), line((2, 5), (7, 5)), line((7, 5), (7, 2)), line((7, 2), (12, 2)), line((12, 2), (12, 6)), line((12, 6), (19, 6)), line((19, 6), (19, 1))),
)

SANDSTURM = MapDefinition(
    key="dune",
    title="Sandsturm-Basar",
    subtitle="Treppenpfade durch die Dünen",
    terrain="desert",
    paths=SANDSTURM_ROUTES,
    pads=((13,1),(15,1),(14,2),(17,2),(6,3),(9,3),(11,3),(5,4),(8,4),(10,4),(13,4),(15,4),(17,4),(9,5),(18,5),(3,6),(1,7),(5,7),(7,7),(10,7),(12,7),(15,7),(17,7),(3,8),(13,8),(16,8),(1,9),(5,9),(7,9),(11,9),(8,10),(3,11)),
)

FINSTERWALD_ROUTES = (
    join(line((0, 0), (8, 0)), line((8, 0), (8, 4)), line((8, 4), (3, 4)), line((3, 4), (3, 8)), line((3, 8), (11, 8)), line((11, 8), (11, 11)), line((11, 11), (19, 11))),
    join(line((0, 0), (5, 0)), line((5, 0), (5, 6)), line((5, 6), (13, 6)), line((13, 6), (13, 2)), line((13, 2), (17, 2)), line((17, 2), (17, 11)), line((17, 11), (19, 11))),
    join(line((0, 0), (2, 0)), line((2, 0), (2, 10)), line((2, 10), (6, 10)), line((6, 10), (6, 3)), line((6, 3), (15, 3)), line((15, 3), (15, 8)), line((15, 8), (19, 8)), line((19, 8), (19, 11))),
)

FINSTERWALD = MapDefinition(
    key="timber",
    title="Finsterwald",
    subtitle="Spiralschleifen im Dickicht, offenes Baufeld",
    terrain="forest",
    paths=FINSTERWALD_ROUTES,
    pads=buildable_cells(FINSTERWALD_ROUTES),
)

SCHATTENGRUFT_ROUTES = (
    join(line((0, 6), (3, 6)), line((3, 6), (3, 1)), line((3, 1), (9, 1)), line((9, 1), (9, 5)), line((9, 5), (13, 5)), line((13, 5), (13, 10)), line((13, 10), (17, 10)), line((17, 10), (17, 6)), line((17, 6), (19, 6))),
    join(line((0, 6), (5, 6)), line((5, 6), (5, 10)), line((5, 10), (11, 10)), line((11, 10), (11, 7)), line((11, 7), (15, 7)), line((15, 7), (15, 2)), line((15, 2), (19, 2)), line((19, 2), (19, 6))),
    join(line((0, 6), (7, 6)), line((7, 6), (7, 3)), line((7, 3), (11, 3)), line((11, 3), (11, 1)), line((11, 1), (16, 1)), line((16, 1), (16, 8)), line((16, 8), (19, 8)), line((19, 8), (19, 6))),
)

SCHATTENGRUFT = MapDefinition(
    key="crypt",
    title="Schattengruft",
    subtitle="Doppelschleife um die Sarkophage",
    terrain="crypt",
    paths=SCHATTENGRUFT_ROUTES,
    pads=((17,1),(5,2),(8,2),(10,2),(13,2),(4,3),(6,3),(12,3),(14,3),(17,3),(5,4),(8,4),(10,4),(13,4),(18,4),(4,5),(6,5),(17,5),(10,6),(12,6),(14,6),(4,7),(6,7),(8,7),(18,7),(7,8),(10,8),(12,8),(14,8),(16,9),(18,9),(12,10)),
)

MAZE_CITADEL = MapDefinition(
    key="tower_maze",
    title="Turm-Labyrinth",
    subtitle="Freies Raster · Türme definieren den kompletten Weg",
    terrain="arena",
    paths=(((0, 5), (19, 5)),),
    pads=buildable_cells((((0, 5), (19, 5)),)),
    layout_mode="maze",
)

TRANSIT_NEXUS_V3_JSON = Path(__file__).resolve().parents[1] / "designs" / "transit_nexus_v3" / "transit_nexus_v3.json"


def _load_transit_nexus_v3() -> MapDefinition:
    data = json.loads(TRANSIT_NEXUS_V3_JSON.read_text(encoding="utf-8"))
    grid_size = (int(data["grid"]["columns"]), int(data["grid"]["rows"]))
    route = tuple((int(cell[0]), int(cell[1])) for cell in data["route"]["cells"])
    pads = tuple((int(cell[0]), int(cell[1])) for cell in data["areas"]["buildable_cells"])
    turns = tuple((int(cell[0]), int(cell[1])) for cell in data["route"]["turn_cells"])
    return MapDefinition(
        key=str(data["id"]),
        title=str(data["name"]),
        subtitle=f"{grid_size[0]}×{grid_size[1]} · {len(route)} Zellen · eine feste Insolvenzspirale",
        terrain="nexus_v3",
        paths=(route,),
        pads=pads,
        grid_size=grid_size,
        junctions=turns,
    )


TRANSIT_NEXUS = _load_transit_nexus_v3()

MAPS: Tuple[MapDefinition, ...] = (
    RIVER_DELTA, SUNKEN_PASS, EMBER_FORGE, FROSTKLAMM, SANDSTURM, FINSTERWALD, SCHATTENGRUFT,
    MAZE_CITADEL, TRANSIT_NEXUS,
)


def path_cells(map_def: MapDefinition) -> Set[Grid]:
    return {cell for route in map_def.paths for cell in route}


def get_map(index: int) -> MapDefinition:
    return MAPS[index % len(MAPS)]


def map_indices_for_layout(layout_mode: str) -> Tuple[int, ...]:
    return tuple(index for index, map_def in enumerate(MAPS) if map_def.layout_mode == layout_mode)
