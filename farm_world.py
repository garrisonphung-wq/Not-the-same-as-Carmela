"""3D Farm Buildings & Nature Props for Not the Same as Carmela.

Includes:
- Cozy red-roofed Chicken Coop (walls, gable, pitched roof, arched door, loft window, ramp)
- Stacked Golden Hay Bales (walkable/jumpable tops!)
- Storybook Wooden Fence (post-and-rail paddock with open gates, jumpable)
- Lush 3D Trees (tapered trunks + layered shaded canopies)
- Meadow Flowers (daisies, tulips, buttercups, bluebells)
- Shared collision + prop-top support height solver for players and AI chicks
"""

from __future__ import annotations

import math
from typing import Callable

import pygame


# --- STATIC FARM & MEADOW LAYOUT ---

CHICKEN_COOP = {
    "cx": -14.0,
    "cz": 14.0,
    "w": 3.4,       # Raised wooden coop cabin X width
    "d": 2.8,       # Raised wooden coop cabin Z depth
    "stilt_h": 1.05,
    "wall_h": 3.05,
    "peak_h": 4.15,
    "run_w": 3.6,   # Attached chicken-wire mesh run extending on +X
    "run_h": 1.85,
}

# (cx, cz, w, d, base_y, h, yaw_rad)
HAY_BALES: list[dict[str, float]] = [
    # Cozy stacked trio right beside the chicken coop wire run
    {"cx": -6.3, "cz": 13.0, "w": 2.1, "d": 1.5, "base_y": 0.0, "h": 1.12},
    {"cx": -6.4, "cz": 14.9, "w": 2.1, "d": 1.5, "base_y": 0.0, "h": 1.12},
    {"cx": -6.3, "cz": 13.9, "w": 1.9, "d": 1.4, "base_y": 1.12, "h": 1.05},
    # Sunny meadow hay stack on the right side
    {"cx": 11.5, "cz": 10.5, "w": 2.4, "d": 1.7, "base_y": 0.0, "h": 1.20},
    {"cx": 13.7, "cz": 11.2, "w": 2.1, "d": 1.6, "base_y": 0.0, "h": 1.12},
    {"cx": 12.4, "cz": 10.9, "w": 2.0, "d": 1.5, "base_y": 1.20, "h": 1.08},
    # Small lone hay bale near front-left fence
    {"cx": -11.5, "cz": 1.5, "w": 1.9, "d": 1.4, "base_y": 0.0, "h": 1.05},
]


def _build_fence_segments() -> list[tuple[float, float, float, float]]:
    """Build wooden paddock fence lines leaving wide open front/side gates."""
    segs: list[tuple[float, float, float, float]] = []

    def add_chain(pts: list[tuple[float, float]]) -> None:
        for i in range(len(pts) - 1):
            segs.append((pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]))

    # Left-front -> Left-back -> Back behind coop -> Right-back -> Right-front (open center gate!)
    add_chain([
        (-5.5, -11.5),
        (-18.5, -11.5),
        (-18.5, 22.0),
        (19.5, 22.0),
        (19.5, -11.5),
        (6.0, -11.5),
    ])
    return segs


FENCE_SEGMENTS = _build_fence_segments()


def _build_fence_posts() -> list[tuple[float, float]]:
    """Sample fence posts every ~3.2m along every fence segment without duplicates."""
    posts: list[tuple[float, float]] = []
    for x1, z1, x2, z2 in FENCE_SEGMENTS:
        length = math.hypot(x2 - x1, z2 - z1)
        steps = max(1, round(length / 3.2))
        for si in range(steps + 1):
            t = si / steps
            px = x1 + (x2 - x1) * t
            pz = z1 + (z2 - z1) * t
            if not any(math.hypot(px - ox, pz - oz) < 0.25 for ox, oz in posts):
                posts.append((px, pz))
    return posts


FENCE_POSTS = _build_fence_posts()

# 9 lush storybook trees around the farm perimeter & sunny meadow
FARM_TREES: list[dict[str, float]] = [
    {"wx": -21.5, "wz": 6.5, "scale": 1.15, "seed": 1.0},
    {"wx": -21.0, "wz": 20.5, "scale": 1.25, "seed": 2.3},
    {"wx": -6.0, "wz": 25.0, "scale": 1.10, "seed": 3.7},
    {"wx": 10.5, "wz": 24.5, "scale": 1.22, "seed": 4.9},
    {"wx": 22.0, "wz": 15.0, "scale": 1.18, "seed": 5.4},
    {"wx": 21.8, "wz": -3.5, "scale": 1.08, "seed": 6.8},
    {"wx": -20.5, "wz": -12.5, "scale": 1.12, "seed": 7.5},
    {"wx": 16.5, "wz": -14.0, "scale": 1.05, "seed": 8.2},
    {"wx": 3.0, "wz": 26.8, "scale": 1.30, "seed": 9.1},
]


def _build_meadow_flowers() -> list[dict[str, object]]:
    """Generate deterministic colorful flowers scattered evenly across the meadow."""
    import random as _rand
    rng = _rand.Random(42069)
    palette = [
        (255, 250, 240),  # White daisy
        (255, 130, 165),  # Pink tulip
        (255, 220, 72),   # Golden buttercup
        (135, 185, 255),  # Sky bluebell
        (255, 155, 92),   # Coral marigold
        (215, 155, 255),  # Lavender blossom
    ]
    flowers: list[dict[str, object]] = []
    coop_x0 = CHICKEN_COOP["cx"] - CHICKEN_COOP["w"] * 0.5 - 1.0
    coop_x1 = CHICKEN_COOP["cx"] + CHICKEN_COOP["w"] * 0.5 + 1.0
    coop_z0 = CHICKEN_COOP["cz"] - CHICKEN_COOP["d"] * 0.5 - 1.0
    coop_z1 = CHICKEN_COOP["cz"] + CHICKEN_COOP["d"] * 0.5 + 1.0

    for idx in range(95):
        wx = rng.uniform(-23.5, 23.5)
        wz = rng.uniform(-14.5, 25.5)
        if coop_x0 <= wx <= coop_x1 and coop_z0 <= wz <= coop_z1:
            continue
        if math.hypot(wx, wz + 6.0) < 2.2:
            continue
        if any(math.hypot(wx - b["cx"], wz - b["cz"]) < 2.0 for b in HAY_BALES):
            continue
        flowers.append({
            "wx": wx,
            "wz": wz,
            "color": palette[idx % len(palette)],
            "h": rng.uniform(0.34, 0.56),
            "size": 0.15 + (idx % 3) * 0.035,
            "phase": idx * 0.7,
        })
    return flowers


MEADOW_FLOWERS = _build_meadow_flowers()


def resolve_world_props_collision(
    wx: float,
    wz: float,
    jump_y: float,
    chick_radius: float = 0.48,
) -> tuple[float, float, float]:
    """Push chick cleanly outside solid walls/bales/fences/trunks and return max support height."""
    support_y = 0.0

    # 1. Raised Wooden Chicken Coop + Walkable Ramp + Outboard Nest Box + Attached Wire Run
    cx = CHICKEN_COOP["cx"]
    cz = CHICKEN_COOP["cz"]
    hx = CHICKEN_COOP["w"] * 0.5 + chick_radius
    hz = CHICKEN_COOP["d"] * 0.5 + chick_radius
    wall_h = CHICKEN_COOP["wall_h"]
    stilt_h = CHICKEN_COOP["stilt_h"]

    # 1a. Walkable cleated ramp leading up to the coop pop-door on the -Z front face
    ramp_x0, ramp_x1 = cx - 0.58, cx + 0.58
    ramp_z_bot = cz - CHICKEN_COOP["d"] * 0.5 - 2.35
    ramp_z_top = cz - CHICKEN_COOP["d"] * 0.5
    if ramp_x0 <= wx <= ramp_x1 and ramp_z_bot <= wz <= ramp_z_top:
        t_ramp = (wz - ramp_z_bot) / max(0.1, ramp_z_top - ramp_z_bot)
        ramp_y = t_ramp * (stilt_h + 0.08)
        if jump_y >= ramp_y - 0.45:
            support_y = max(support_y, ramp_y)

    # 1b. Coop cabin & stilts + walkable roof
    if abs(wx - cx) < hx and abs(wz - cz) < hz:
        if jump_y >= wall_h - 0.35:
            frac_x = min(1.0, abs(wx - cx) / max(0.1, CHICKEN_COOP["w"] * 0.5))
            roof_y = CHICKEN_COOP["peak_h"] - frac_x * (CHICKEN_COOP["peak_h"] - wall_h)
            support_y = max(support_y, roof_y)
        else:
            dx_edge = hx - abs(wx - cx)
            dz_edge = hz - abs(wz - cz)
            if dx_edge < dz_edge:
                wx = cx + (hx if wx >= cx else -hx)
            else:
                wz = cz + (hz if wz >= cz else -hz)

    # 1c. Outboard Nesting Box on -X side (walkable slanted top!)
    nb_x0 = cx - CHICKEN_COOP["w"] * 0.5 - 0.95 - chick_radius
    nb_x1 = cx - CHICKEN_COOP["w"] * 0.5
    nb_z0 = cz - 1.05 - chick_radius
    nb_z1 = cz + 1.05 + chick_radius
    if nb_x0 <= wx <= nb_x1 and nb_z0 <= wz <= nb_z1:
        if jump_y >= 1.75:
            support_y = max(support_y, 2.05)
        elif jump_y >= 0.75:
            dx_nb = abs(wx - nb_x0)
            dz_nb = min(abs(wz - nb_z0), abs(wz - nb_z1))
            if dx_nb <= dz_nb:
                wx = nb_x0
            else:
                wz = nb_z0 if abs(wz - nb_z0) < abs(wz - nb_z1) else nb_z1

    # 1d. Attached Wire-Mesh Run Pen on +X side (jumpable over roof at y >= 1.85)
    run_x0 = cx + CHICKEN_COOP["w"] * 0.5
    run_x1 = run_x0 + CHICKEN_COOP["run_w"] + chick_radius
    run_z0 = cz - CHICKEN_COOP["d"] * 0.5 - chick_radius
    run_z1 = cz + CHICKEN_COOP["d"] * 0.5 + chick_radius
    if run_x0 < wx < run_x1 and run_z0 < wz < run_z1:
        if jump_y >= CHICKEN_COOP["run_h"] - 0.25:
            support_y = max(support_y, CHICKEN_COOP["run_h"])
        else:
            d_rx1 = run_x1 - wx
            d_rz0 = wz - run_z0
            d_rz1 = run_z1 - wz
            m = min(d_rx1, d_rz0, d_rz1)
            if m == d_rx1:
                wx = run_x1
            elif m == d_rz0:
                wz = run_z0
            else:
                wz = run_z1

    # 2. Hay Bales (walk/stand on top or push outside sides)
    for bale in HAY_BALES:
        bx, bz = bale["cx"], bale["cz"]
        bhx = bale["w"] * 0.5 + chick_radius
        bhz = bale["d"] * 0.5 + chick_radius
        top_y = bale["base_y"] + bale["h"]
        if abs(wx - bx) < bhx and abs(wz - bz) < bhz:
            if jump_y >= top_y - 0.32:
                support_y = max(support_y, top_y)
            elif jump_y + 0.9 >= bale["base_y"]:
                dx_e = bhx - abs(wx - bx)
                dz_e = bhz - abs(wz - bz)
                if dx_e < dz_e:
                    wx = bx + (bhx if wx >= bx else -bhx)
                else:
                    wz = bz + (bhz if wz >= bz else -bhz)

    # 3. Wooden Fence Segments (jumpable above y = 1.12)
    if jump_y < 1.12:
        fence_r = 0.24 + chick_radius
        for x1, z1, x2, z2 in FENCE_SEGMENTS:
            vx, vz = x2 - x1, z2 - z1
            seg_len2 = vx * vx + vz * vz
            if seg_len2 < 1e-6:
                continue
            t = max(0.0, min(1.0, ((wx - x1) * vx + (wz - z1) * vz) / seg_len2))
            px = x1 + t * vx
            pz = z1 + t * vz
            dx, dz = wx - px, wz - pz
            d = math.hypot(dx, dz)
            if d < fence_r:
                if d < 1e-4:
                    nx, nz = -vz / math.sqrt(seg_len2), vx / math.sqrt(seg_len2)
                else:
                    nx, nz = dx / d, dz / d
                wx = px + nx * fence_r
                wz = pz + nz * fence_r

    # 4. Tree Trunks
    for tree in FARM_TREES:
        t_scale = tree["scale"]
        trunk_r = 0.48 * t_scale + chick_radius
        if jump_y < 2.9 * t_scale:
            dx = wx - tree["wx"]
            dz = wz - tree["wz"]
            d = math.hypot(dx, dz)
            if d < trunk_r:
                nx, nz = (dx / d, dz / d) if d > 1e-4 else (1.0, 0.0)
                wx = tree["wx"] + nx * trunk_r
                wz = tree["wz"] + nz * trunk_r

    return wx, wz, support_y


# --- 3D RENDERING HELPERS ---

def _clip_poly_cam(
    cam_pts: list[tuple[float, float, float]],
    near_z: float,
    hw: float,
    hh: float,
    focal: float,
    win_w: int,
    win_h: int,
) -> list[tuple[int, int]]:
    """Sutherland-Hodgman near-plane clip and 2D screen projection."""
    clipped: list[tuple[float, float, float]] = []
    n = len(cam_pts)
    for i in range(n):
        a = cam_pts[i]
        b = cam_pts[(i + 1) % n]
        a_in = a[2] >= near_z
        b_in = b[2] >= near_z
        if a_in and b_in:
            clipped.append(b)
        elif a_in and not b_in:
            t = (near_z - a[2]) / (b[2] - a[2])
            clipped.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), near_z))
        elif (not a_in) and b_in:
            t = (near_z - a[2]) / (b[2] - a[2])
            clipped.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), near_z))
            clipped.append(b)
    if len(clipped) < 3:
        return []
    return [
        (
            max(-4000, min(win_w + 4000, round(hw + (p[0] / p[2]) * focal))),
            max(-4000, min(win_h + 4000, round(hh - (p[1] / p[2]) * focal))),
        )
        for p in clipped
    ]


def _draw_quad_list(
    screen: pygame.Surface,
    faces: list[tuple[float, list[tuple[float, float, float]], tuple[int, int, int], tuple[int, int, int] | None]],
    near_z: float,
    hw: float,
    hh: float,
    focal: float,
    win_w: int,
    win_h: int,
) -> None:
    """Sort 3D faces back-to-front by camera depth and draw filled polygons."""
    faces.sort(key=lambda f: f[0], reverse=True)
    for _depth, pts_cam, fill_col, edge_col in faces:
        scr = _clip_poly_cam(pts_cam, near_z, hw, hh, focal, win_w, win_h)
        if len(scr) >= 3:
            pygame.draw.polygon(screen, fill_col, scr)
            if edge_col is not None:
                pygame.draw.polygon(screen, edge_col, scr, 1)


def _draw_box(
    screen: pygame.Surface,
    to_cam: Callable[[float, float, float], tuple[float, float, float]],
    cx: float,
    y0: float,
    cz: float,
    w: float,
    h: float,
    d: float,
    colors: dict[str, tuple[int, int, int]],
    near_z: float,
    hw: float,
    hh: float,
    focal: float,
    win_w: int,
    win_h: int,
    edge_col: tuple[int, int, int] | None = None,
) -> None:
    hx, hz = w * 0.5, d * 0.5
    x0, x1 = cx - hx, cx + hx
    z0, z1 = cz - hz, cz + hz
    y1 = y0 + h

    p000 = to_cam(x0, y0, z0)
    p100 = to_cam(x1, y0, z0)
    p101 = to_cam(x1, y0, z1)
    p001 = to_cam(x0, y0, z1)
    p010 = to_cam(x0, y1, z0)
    p110 = to_cam(x1, y1, z0)
    p111 = to_cam(x1, y1, z1)
    p011 = to_cam(x0, y1, z1)

    raw_faces = [
        ([p010, p110, p111, p011], colors["top"]),
        ([p000, p100, p110, p010], colors["front"]),
        ([p101, p001, p011, p111], colors["back"]),
        ([p001, p000, p010, p011], colors["left"]),
        ([p100, p101, p111, p110], colors["right"]),
    ]
    faces = []
    for pts, col in raw_faces:
        if max(p[2] for p in pts) <= near_z:
            continue
        depth = sum(p[2] for p in pts) * 0.25
        faces.append((depth, pts, col, edge_col))
    _draw_quad_list(screen, faces, near_z, hw, hh, focal, win_w, win_h)


def collect_world_prop_draw_items(
    to_cam: Callable[[float, float, float], tuple[float, float, float]],
    current_ground_y: float,
    near_z: float,
) -> list[tuple[float, str, object]]:
    """Return distance-tagged prop items to interleave cleanly in PASS 2 with chicks."""
    items: list[tuple[float, str, object]] = []

    # 1. Chicken Coop Sub-Parts (depth-sorted independently so ramp/nest/wire-run/cabin never z-fight from any angle!)
    _cx, _cz = CHICKEN_COOP["cx"], CHICKEN_COOP["cz"]
    _hx, _hz = CHICKEN_COOP["w"] * 0.5, CHICKEN_COOP["d"] * 0.5
    c_cabin = to_cam(_cx, current_ground_y + 1.8, _cz)
    if c_cabin[2] > -4.0:
        items.append((c_cabin[2], "coop_cabin", CHICKEN_COOP))
    c_run = to_cam(_cx + _hx + CHICKEN_COOP["run_w"] * 0.5, current_ground_y + 0.9, _cz)
    if c_run[2] > -4.0:
        items.append((c_run[2], "coop_run", CHICKEN_COOP))
    c_nest = to_cam(_cx - _hx - 0.48, current_ground_y + 1.45, _cz)
    if c_nest[2] > -3.0:
        items.append((c_nest[2], "coop_nest", CHICKEN_COOP))
    c_ramp = to_cam(_cx, current_ground_y + 0.5, _cz - _hz - 1.15)
    if c_ramp[2] > -3.0:
        items.append((c_ramp[2], "coop_ramp", CHICKEN_COOP))

    # 2. Hay Bales
    for bale in HAY_BALES:
        bc = to_cam(bale["cx"], current_ground_y + bale["base_y"] + bale["h"] * 0.5, bale["cz"])
        if bc[2] > -2.0:
            items.append((bc[2], "hay", bale))

    # 3. Fence spans (each segment split into ~3.2m bays for accurate per-bay depth sorting!)
    for x1, z1, x2, z2 in FENCE_SEGMENTS:
        length = math.hypot(x2 - x1, z2 - z1)
        bays = max(1, round(length / 3.2))
        for bi in range(bays):
            t0 = bi / bays
            t1 = (bi + 1) / bays
            ax, az = x1 + (x2 - x1) * t0, z1 + (z2 - z1) * t0
            bx, bz = x1 + (x2 - x1) * t1, z1 + (z2 - z1) * t1
            mc = to_cam((ax + bx) * 0.5, current_ground_y + 0.65, (az + bz) * 0.5)
            if mc[2] > -2.5:
                items.append((mc[2], "fence_bay", (ax, az, bx, bz)))

    # 4. Fence Posts
    for px, pz in FENCE_POSTS:
        pc = to_cam(px, current_ground_y + 0.7, pz)
        if pc[2] > -1.2:
            items.append((pc[2], "fence_post", (px, pz)))

    # 5. Lush 3D Trees
    for tree in FARM_TREES:
        tc = to_cam(tree["wx"], current_ground_y + 2.2 * tree["scale"], tree["wz"])
        if tc[2] > -3.5:
            items.append((tc[2], "tree", tree))

    # 6. Meadow Flowers (only within ~48m camera depth for ultra-crisp 60 FPS)
    for fl in MEADOW_FLOWERS:
        fc = to_cam(fl["wx"], current_ground_y + 0.15, fl["wz"])
        if near_z < fc[2] < 48.0:
            items.append((fc[2], "flower", fl))

    return items


def draw_world_prop_item(
    kind: str,
    payload: object,
    screen: pygame.Surface,
    to_cam: Callable[[float, float, float], tuple[float, float, float]],
    current_ground_y: float,
    near_z: float,
    hw: float,
    hh: float,
    focal: float,
    win_w: int,
    win_h: int,
    anim_time: float,
) -> None:
    """Render one 3D farm building or nature prop."""
    if kind == "coop_run":
        coop = payload  # type: ignore[assignment]
        cx, cz = coop["cx"], coop["cz"]
        w, d = coop["w"], coop["d"]
        run_w, run_h = coop["run_w"], coop["run_h"]
        hx, hz = w * 0.5, d * 0.5
        y_ground = current_ground_y
        leg_col = {
            "top": (152, 102, 58),
            "front": (132, 86, 46),
            "right": (122, 78, 42),
            "left": (110, 70, 38),
            "back": (102, 64, 34),
        }
        rx0, rx1 = cx + hx, cx + hx + run_w
        rz0, rz1 = cz - hz, cz + hz
        ry_top = y_ground + run_h
        for px, pz in ((rx1, rz0), (rx1, rz1)):
            _draw_box(
                screen, to_cam, px - 0.10, y_ground, pz, 0.20, run_h, 0.20,
                leg_col, near_z, hw, hh, focal, win_w, win_h, edge_col=(78, 48, 24),
            )
        _draw_box(screen, to_cam, (rx0 + rx1) * 0.5, ry_top - 0.12, rz0 + 0.08, run_w, 0.14, 0.14, leg_col, near_z, hw, hh, focal, win_w, win_h)
        _draw_box(screen, to_cam, (rx0 + rx1) * 0.5, ry_top - 0.12, rz1 - 0.08, run_w, 0.14, 0.14, leg_col, near_z, hw, hh, focal, win_w, win_h)
        _draw_box(screen, to_cam, rx1 - 0.08, ry_top - 0.12, cz, 0.14, 0.14, d, leg_col, near_z, hw, hh, focal, win_w, win_h)

        wire_col = (182, 192, 200)
        def _wire_line(p1: tuple[float, float, float], p2: tuple[float, float, float]) -> None:
            c1, c2 = to_cam(*p1), to_cam(*p2)
            if c1[2] > near_z and c2[2] > near_z:
                s1 = (round(hw + (c1[0] / c1[2]) * focal), round(hh - (c1[1] / c1[2]) * focal))
                s2 = (round(hw + (c2[0] / c2[2]) * focal), round(hh - (c2[1] / c2[2]) * focal))
                pygame.draw.line(screen, wire_col, s1, s2, 1)

        for wi in range(1, 5):
            wy = y_ground + (wi / 5.0) * run_h
            _wire_line((rx0, wy, rz0), (rx1, wy, rz0))
            _wire_line((rx0, wy, rz1), (rx1, wy, rz1))
            _wire_line((rx1, wy, rz0), (rx1, wy, rz1))
        for wx_i in range(1, 7):
            wxp = rx0 + (wx_i / 7.0) * run_w
            _wire_line((wxp, y_ground, rz0), (wxp, ry_top, rz0))
            _wire_line((wxp, y_ground, rz1), (wxp, ry_top, rz1))
            _wire_line((wxp, ry_top, rz0), (wxp, ry_top, rz1))
        for wz_i in range(1, 6):
            wzp = rz0 + (wz_i / 6.0) * d
            _wire_line((rx1, y_ground, wzp), (rx1, ry_top, wzp))
            _wire_line((rx0, ry_top, wzp), (rx1, ry_top, wzp))

    elif kind == "coop_cabin":
        coop = payload  # type: ignore[assignment]
        cx, cz = coop["cx"], coop["cz"]
        w, d = coop["w"], coop["d"]
        stilt_h = coop["stilt_h"]
        wall_h, peak_h = coop["wall_h"], coop["peak_h"]
        hx, hz = w * 0.5, d * 0.5
        y_ground = current_ground_y
        y_floor = y_ground + stilt_h
        y_wall = y_ground + wall_h
        y_peak = y_ground + peak_h

        leg_col = {
            "top": (152, 102, 58),
            "front": (132, 86, 46),
            "right": (122, 78, 42),
            "left": (110, 70, 38),
            "back": (102, 64, 34),
        }
        for lx in (cx - hx + 0.18, cx + hx - 0.18):
            for lz in (cz - hz + 0.18, cz + hz - 0.18):
                _draw_box(
                    screen, to_cam, lx, y_ground, lz, 0.24, stilt_h + 0.05, 0.24,
                    leg_col, near_z, hw, hh, focal, win_w, win_h, edge_col=(78, 48, 24),
                )

        w00 = to_cam(cx - hx, y_floor, cz - hz)
        w10 = to_cam(cx + hx, y_floor, cz - hz)
        w11 = to_cam(cx + hx, y_floor, cz + hz)
        w01 = to_cam(cx - hx, y_floor, cz + hz)
        t00 = to_cam(cx - hx, y_wall, cz - hz)
        t10 = to_cam(cx + hx, y_wall, cz - hz)
        t11 = to_cam(cx + hx, y_wall, cz + hz)
        t01 = to_cam(cx - hx, y_wall, cz + hz)
        r_front = to_cam(cx, y_peak, cz - hz)
        r_back = to_cam(cx, y_peak, cz + hz)

        oh = 0.34
        rhx, rhz = hx + oh, hz + oh
        ry_eave = y_wall - 0.14
        rf_l = to_cam(cx - rhx, ry_eave, cz - rhz)
        rf_r = to_cam(cx + rhx, ry_eave, cz - rhz)
        rb_l = to_cam(cx - rhx, ry_eave, cz + rhz)
        rb_r = to_cam(cx + rhx, ry_eave, cz + rhz)
        rr_f = to_cam(cx, y_peak + 0.06, cz - rhz)
        rr_b = to_cam(cx, y_peak + 0.06, cz + rhz)

        pop_w = 0.48
        dz_f = cz - hz - 0.02
        pop0 = to_cam(cx - pop_w, y_floor + 0.06, dz_f)
        pop1 = to_cam(cx + pop_w, y_floor + 0.06, dz_f)
        pop2 = to_cam(cx + pop_w, y_floor + 1.15, dz_f)
        pop3 = to_cam(cx - pop_w, y_floor + 1.15, dz_f)

        vt0 = to_cam(cx - 0.38, y_wall + 0.12, dz_f)
        vt1 = to_cam(cx + 0.38, y_wall + 0.12, dz_f)
        vt2 = to_cam(cx + 0.38, y_wall + 0.62, dz_f)
        vt3 = to_cam(cx - 0.38, y_wall + 0.62, dz_f)

        cabin_faces = [
            ([w00, w10, w11, w01], (116, 74, 38), (78, 48, 24)),
            ([w00, w10, t10, r_front, t00], (196, 138, 78), (124, 80, 42)),
            ([w11, w01, t01, r_back, t11], (166, 114, 62), (108, 68, 36)),
            ([w01, w00, t00, t01], (176, 122, 68), (112, 72, 38)),
            ([w10, w11, t11, t10], (188, 132, 74), (118, 76, 40)),
            ([rf_l, rr_f, rr_b, rb_l], (138, 68, 48), (88, 40, 26)),
            ([rr_f, rf_r, rb_r, rr_b], (162, 82, 56), (98, 46, 30)),
            ([pop0, pop1, pop2, pop3], (58, 36, 22), (112, 72, 36)),
            ([vt0, vt1, vt2, vt3], (86, 56, 34), (124, 82, 44)),
        ]
        faces = []
        for pts, col, ecol in cabin_faces:
            if max(p[2] for p in pts) <= near_z:
                continue
            avg_d = sum(p[2] for p in pts) / len(pts)
            if col in ((58, 36, 22), (86, 56, 34)):
                avg_d -= 0.10
            faces.append((avg_d, pts, col, ecol))
        _draw_quad_list(screen, faces, near_z, hw, hh, focal, win_w, win_h)

        for pi in range(1, 5):
            py = y_floor + (pi / 5.0) * (wall_h - stilt_h)
            _wire_p1, _wire_p2 = to_cam(cx - hx, py, dz_f), to_cam(cx + hx, py, dz_f)
            if _wire_p1[2] > near_z and _wire_p2[2] > near_z:
                sa = (round(hw + (_wire_p1[0] / _wire_p1[2]) * focal), round(hh - (_wire_p1[1] / _wire_p1[2]) * focal))
                sb = (round(hw + (_wire_p2[0] / _wire_p2[2]) * focal), round(hh - (_wire_p2[1] / _wire_p2[2]) * focal))
                pygame.draw.line(screen, (132, 86, 44), sa, sb, 1)

    elif kind == "coop_ramp":
        coop = payload  # type: ignore[assignment]
        cx, cz = coop["cx"], coop["cz"]
        hz = coop["d"] * 0.5
        stilt_h = coop["stilt_h"]
        y_ground = current_ground_y
        y_floor = y_ground + stilt_h
        rz_top = cz - hz
        rz_bot = rz_top - 2.35
        rm_l_t = to_cam(cx - 0.50, y_floor + 0.05, rz_top)
        rm_r_t = to_cam(cx + 0.50, y_floor + 0.05, rz_top)
        rm_r_b = to_cam(cx + 0.50, y_ground + 0.03, rz_bot)
        rm_l_b = to_cam(cx - 0.50, y_ground + 0.03, rz_bot)
        if max(p[2] for p in (rm_l_t, rm_r_t, rm_r_b, rm_l_b)) > near_z:
            scr_ramp = _clip_poly_cam([rm_l_t, rm_r_t, rm_r_b, rm_l_b], near_z, hw, hh, focal, win_w, win_h)
            if len(scr_ramp) >= 3:
                pygame.draw.polygon(screen, (186, 134, 78), scr_ramp)
                pygame.draw.polygon(screen, (112, 74, 38), scr_ramp, 1)
        for ci in range(1, 7):
            ct = ci / 7.0
            cz_c = rz_bot + ct * (rz_top - rz_bot)
            cy_c = (y_ground + 0.05) + ct * (stilt_h + 0.02)
            ca, cb = to_cam(cx - 0.48, cy_c, cz_c), to_cam(cx + 0.48, cy_c, cz_c)
            if ca[2] > near_z and cb[2] > near_z:
                sa = (round(hw + (ca[0] / ca[2]) * focal), round(hh - (ca[1] / ca[2]) * focal))
                sb = (round(hw + (cb[0] / cb[2]) * focal), round(hh - (cb[1] / cb[2]) * focal))
                pygame.draw.line(screen, (108, 68, 34), sa, sb, 3)

    elif kind == "coop_nest":
        coop = payload  # type: ignore[assignment]
        cx, cz = coop["cx"], coop["cz"]
        hx = coop["w"] * 0.5
        nb_cx = cx - hx - 0.48
        _draw_box(
            screen, to_cam, nb_cx, current_ground_y + 1.05, cz, 0.92, 0.85, 2.05,
            colors={
                "top": (166, 86, 58),
                "front": (188, 132, 74),
                "right": (176, 122, 68),
                "left": (172, 118, 66),
                "back": (158, 108, 58),
            },
            near_z=near_z, hw=hw, hh=hh, focal=focal, win_w=win_w, win_h=win_h,
            edge_col=(104, 66, 34),
        )

    elif kind == "hay":
        bale = payload  # type: ignore[assignment]
        _draw_box(
            screen, to_cam,
            bale["cx"], current_ground_y + bale["base_y"], bale["cz"],
            bale["w"], bale["h"], bale["d"],
            colors={
                "top": (244, 206, 92),
                "front": (232, 188, 72),
                "right": (222, 178, 66),
                "left": (204, 160, 56),
                "back": (194, 150, 50),
            },
            near_z=near_z, hw=hw, hh=hh, focal=focal, win_w=win_w, win_h=win_h,
            edge_col=(168, 124, 38),
        )
        # Draw dark twine straps around the hay bale
        bx, bz = bale["cx"], bale["cz"]
        by0 = current_ground_y + bale["base_y"]
        by1 = by0 + bale["h"] + 0.01
        bhx, bhz = bale["w"] * 0.5 + 0.01, bale["d"] * 0.5 + 0.01
        for strap_off in (-bale["w"] * 0.24, bale["w"] * 0.24):
            sx = bx + strap_off
            p_top_f = to_cam(sx, by1, bz - bhz)
            p_top_b = to_cam(sx, by1, bz + bhz)
            p_bot_f = to_cam(sx, by0, bz - bhz)
            p_bot_b = to_cam(sx, by0, bz + bhz)
            for a, b in ((p_bot_f, p_top_f), (p_top_f, p_top_b), (p_top_b, p_bot_b)):
                if a[2] > near_z and b[2] > near_z:
                    sa = (round(hw + (a[0] / a[2]) * focal), round(hh - (a[1] / a[2]) * focal))
                    sb = (round(hw + (b[0] / b[2]) * focal), round(hh - (b[1] / b[2]) * focal))
                    pygame.draw.line(screen, (146, 102, 34), sa, sb, 2)

    elif kind == "fence_bay":
        ax, az, bx, bz = payload  # type: ignore[misc]
        vx, vz = bx - ax, bz - az
        vlen = math.hypot(vx, vz)
        if vlen < 1e-4:
            return
        nx, nz = (-vz / vlen) * 0.08, (vx / vlen) * 0.08
        rail_faces = []
        for y_bot, y_top, col in (
            (current_ground_y + 0.42, current_ground_y + 0.58, (176, 124, 72)),
            (current_ground_y + 0.92, current_ground_y + 1.08, (192, 138, 82)),
        ):
            # Front/back rail face + top rail face
            pts_side = [
                to_cam(ax + nx, y_bot, az + nz),
                to_cam(bx + nx, y_bot, bz + nz),
                to_cam(bx + nx, y_top, bz + nz),
                to_cam(ax + nx, y_top, az + nz),
            ]
            pts_other = [
                to_cam(ax - nx, y_bot, az - nz),
                to_cam(bx - nx, y_bot, bz - nz),
                to_cam(bx - nx, y_top, bz - nz),
                to_cam(ax - nx, y_top, az - nz),
            ]
            pts_top = [
                to_cam(ax - nx, y_top, az - nz),
                to_cam(bx - nx, y_top, bz - nz),
                to_cam(bx + nx, y_top, bz + nz),
                to_cam(ax + nx, y_top, az + nz),
            ]
            for pts, c in ((pts_side, col), (pts_other, col), (pts_top, (208, 156, 98))):
                if max(p[2] for p in pts) > near_z:
                    rail_faces.append((sum(p[2] for p in pts) * 0.25, pts, c, (128, 86, 46)))
        _draw_quad_list(screen, rail_faces, near_z, hw, hh, focal, win_w, win_h)

    elif kind == "fence_post":
        px, pz = payload  # type: ignore[misc]
        _draw_box(
            screen, to_cam,
            px, current_ground_y, pz,
            0.30, 1.38, 0.30,
            colors={
                "top": (212, 162, 102),
                "front": (184, 130, 76),
                "right": (172, 120, 68),
                "left": (158, 108, 60),
                "back": (150, 102, 56),
            },
            near_z=near_z, hw=hw, hh=hh, focal=focal, win_w=win_w, win_h=win_h,
            edge_col=(118, 78, 42),
        )

    elif kind == "tree":
        tree = payload  # type: ignore[assignment]
        tx, tz, sc, seed = tree["wx"], tree["wz"], tree["scale"], tree["seed"]
        trunk_h = 3.2 * sc
        trunk_w = 0.72 * sc
        # Tree trunk
        _draw_box(
            screen, to_cam,
            tx, current_ground_y, tz,
            trunk_w, trunk_h, trunk_w,
            colors={
                "top": (118, 78, 44),
                "front": (132, 86, 48),
                "right": (122, 78, 44),
                "left": (106, 68, 38),
                "back": (98, 62, 34),
            },
            near_z=near_z, hw=hw, hh=hh, focal=focal, win_w=win_w, win_h=win_h,
            edge_col=(78, 48, 26),
        )
        # Multi-lobe swaying leafy storybook canopy!
        sway = math.sin(anim_time * 1.4 + seed) * 0.08 * sc
        lobes = [
            (0.0 + sway, trunk_h + 1.25 * sc, 0.0, 2.35 * sc, (64, 146, 56)),
            (-1.15 * sc + sway, trunk_h + 0.75 * sc, -0.55 * sc, 1.65 * sc, (74, 162, 62)),
            (1.18 * sc + sway, trunk_h + 0.80 * sc, 0.45 * sc, 1.68 * sc, (80, 170, 66)),
            (-0.45 * sc + sway, trunk_h + 0.90 * sc, 1.05 * sc, 1.60 * sc, (68, 154, 58)),
            (0.35 * sc + sway, trunk_h + 1.05 * sc, -1.05 * sc, 1.58 * sc, (84, 176, 68)),
            (0.05 * sc + sway * 1.2, trunk_h + 2.25 * sc, 0.05 * sc, 1.55 * sc, (104, 194, 78)),
        ]
        lobe_cam = []
        for ox, oy, oz, rad, col in lobes:
            lc = to_cam(tx + ox, current_ground_y + oy, tz + oz)
            if lc[2] > near_z:
                lobe_cam.append((lc[2], lc, rad, col))
        lobe_cam.sort(key=lambda it: it[0], reverse=True)
        for zc, lc, rad, col in lobe_cam:
            sx = round(hw + (lc[0] / zc) * focal)
            sy = round(hh - (lc[1] / zc) * focal)
            sr = max(4, round((rad / zc) * focal))
            if -sr <= sx <= win_w + sr and -sr <= sy <= win_h + sr:
                pygame.draw.circle(screen, col, (sx, sy), sr)
                # Subtle sunny highlight puff on upper-left of each canopy lobe
                pygame.draw.circle(screen, (min(255, col[0] + 20), min(255, col[1] + 22), min(255, col[2] + 14)), (sx - max(1, sr // 5), sy - max(1, sr // 5)), max(2, round(sr * 0.58)))

    elif kind == "flower":
        fl = payload  # type: ignore[assignment]
        fx, fz = float(fl["wx"]), float(fl["wz"])
        fh = float(fl["h"])
        fsize = float(fl["size"])
        sway = math.sin(anim_time * 2.5 + float(fl["phase"])) * 0.04
        c_base = to_cam(fx, current_ground_y, fz)
        c_top = to_cam(fx + sway, current_ground_y + fh, fz)
        if c_base[2] > near_z and c_top[2] > near_z:
            bx = round(hw + (c_base[0] / c_base[2]) * focal)
            by = round(hh - (c_base[1] / c_base[2]) * focal)
            tx = round(hw + (c_top[0] / c_top[2]) * focal)
            ty = round(hh - (c_top[1] / c_top[2]) * focal)
            pygame.draw.line(screen, (62, 146, 52), (bx, by), (tx, ty), 2)
            pr = max(3, round((fsize / c_top[2]) * focal))
            col = fl["color"]  # type: ignore[assignment]
            for pi in range(5):
                pang = (2.0 * math.pi * pi) / 5.0 + float(fl["phase"])
                px = tx + round(math.cos(pang) * pr * 0.72)
                py = ty + round(math.sin(pang) * pr * 0.72)
                pygame.draw.circle(screen, col, (px, py), max(2, round(pr * 0.62)))
            pygame.draw.circle(screen, (255, 212, 54), (tx, ty), max(2, round(pr * 0.48)))
