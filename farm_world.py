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

# Authentic "Les P'tites Poules / 不一样的卡梅拉" Storybook Poulailler Grégoire:
# Huge, towering rustic wooden & timber-framed Alsatian farm coop (nearly 8x taller than chicks!),
# steep two-sloped terracotta-tiled gable roof (人字顶瓦屋顶), wooden attic loft (阁楼),
# shuttered windows (fenêtre & volets), front veranda porch, exterior rung ladder (échelle),
# straw nests, and Pédro the Cormorant's wooden barrel (tonneau) at its foot!
CHICKEN_COOP = {
    "cx": -15.5,
    "cz": 16.5,
    "w": 14.5,       # ~6x chick height wide!
    "d": 11.0,       # Deep rustic wooden barn-coop body
    "porch_d": 2.4,  # Front wooden veranda deck depth (-Z)
    "deck_y": 2.6,   # Raised wooden veranda deck height
    "wall_h": 10.6,  # Timber-framed wood wall height (~4.5x chick height!)
    "roof_h": 18.5,  # Steep pitched terracotta-tiled gable ridge (~7.8x chick height!)
    "barrel_cx": -6.3,
    "barrel_cz": 10.2,
    "barrel_r": 1.45,
    "barrel_h": 2.55,
}

# (cx, cz, w, d, base_y, h)
HAY_BALES: list[dict[str, float]] = [
    # Cozy stacked trio right beside Pédro's barrel & the giant Carmela coop
    {"cx": -2.8, "cz": 13.5, "w": 2.6, "d": 1.9, "base_y": 0.0, "h": 1.50},
    {"cx": -2.9, "cz": 16.2, "w": 2.6, "d": 1.9, "base_y": 0.0, "h": 1.50},
    {"cx": -2.8, "cz": 14.8, "w": 2.4, "d": 1.8, "base_y": 1.50, "h": 1.40},
    # Sunny meadow hay stack on the right side
    {"cx": 12.6, "cz": 10.5, "w": 2.6, "d": 1.9, "base_y": 0.0, "h": 1.50},
    {"cx": 15.0, "cz": 11.4, "w": 2.4, "d": 1.8, "base_y": 0.0, "h": 1.50},
    {"cx": 13.7, "cz": 10.9, "w": 2.3, "d": 1.7, "base_y": 1.50, "h": 1.40},
    # Single sunny bale near front-left fence
    {"cx": -8.8, "cz": -5.2, "w": 2.5, "d": 1.8, "base_y": 0.0, "h": 1.45},
]


def _build_fence_segments() -> list[tuple[float, float, float, float]]:
    """Build wooden paddock fence lines leaving wide open front entrance."""
    segs: list[tuple[float, float, float, float]] = []

    def add_chain(pts: list[tuple[float, float]]) -> None:
        for i in range(len(pts) - 1):
            segs.append((pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]))

    add_chain([
        (-5.5, -12.0),
        (-26.5, -12.0),
        (-26.5, 26.5),
        (22.5, 26.5),
        (22.5, -12.0),
        (6.0, -12.0),
    ])
    return segs


FENCE_SEGMENTS = _build_fence_segments()


def _build_fence_posts() -> list[tuple[float, float]]:
    """Sample fence posts every ~3.4m along every fence segment without duplicates."""
    posts: list[tuple[float, float]] = []
    for x1, z1, x2, z2 in FENCE_SEGMENTS:
        length = math.hypot(x2 - x1, z2 - z1)
        steps = max(1, round(length / 3.4))
        for si in range(steps + 1):
            t = si / steps
            px = x1 + (x2 - x1) * t
            pz = z1 + (z2 - z1) * t
            if not any(math.hypot(px - ox, pz - oz) < 0.25 for ox, oz in posts):
                posts.append((px, pz))
    return posts


FENCE_POSTS = _build_fence_posts()

# 9 lush storybook trees framing the giant coop and sunny meadow
FARM_TREES: list[dict[str, float]] = [
    {"wx": -29.5, "wz": 4.0, "scale": 1.80, "seed": 1.0},
    {"wx": -29.5, "wz": 25.5, "scale": 1.95, "seed": 2.3},
    {"wx": -6.0, "wz": 29.0, "scale": 1.80, "seed": 3.7},
    {"wx": 12.0, "wz": 29.0, "scale": 1.90, "seed": 4.9},
    {"wx": 25.5, "wz": 15.5, "scale": 1.80, "seed": 5.4},
    {"wx": 25.0, "wz": -3.5, "scale": 1.65, "seed": 6.8},
    {"wx": -28.0, "wz": -14.0, "scale": 1.75, "seed": 7.5},
    {"wx": 18.0, "wz": -15.5, "scale": 1.65, "seed": 8.2},
    {"wx": 3.0, "wz": 30.0, "scale": 1.95, "seed": 9.1},
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
    coop_x0 = CHICKEN_COOP["cx"] - CHICKEN_COOP["w"] * 0.5 - 1.5
    coop_x1 = CHICKEN_COOP["cx"] + CHICKEN_COOP["w"] * 0.5 + 3.5
    coop_z0 = CHICKEN_COOP["cz"] - CHICKEN_COOP["d"] * 0.5 - CHICKEN_COOP["porch_d"] - 6.0
    coop_z1 = CHICKEN_COOP["cz"] + CHICKEN_COOP["d"] * 0.5 + 1.5

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

    # 1. Giant Carmela Poulailler Grégoire: Barn Cabin + Front Porch + Exterior Ladder + Roof + Pédro's Barrel
    cx = CHICKEN_COOP["cx"]
    cz = CHICKEN_COOP["cz"]
    hw_c = CHICKEN_COOP["w"] * 0.5
    hd_c = CHICKEN_COOP["d"] * 0.5
    porch_d = CHICKEN_COOP["porch_d"]
    deck_y = CHICKEN_COOP["deck_y"]
    wall_h = CHICKEN_COOP["wall_h"]
    roof_h = CHICKEN_COOP["roof_h"]
    z_front_wall = cz - hd_c
    z_porch_edge = z_front_wall - porch_d

    # 1a. Exterior Wooden Ladder (l'échelle du poulailler) leaning up to front wooden porch
    lad_z_bot = z_porch_edge - 5.2
    lad_z_top = z_porch_edge + 0.35
    if cx - 1.35 <= wx <= cx + 1.35 and lad_z_bot <= wz <= lad_z_top:
        t_lad = max(0.0, min(1.0, (wz - lad_z_bot) / max(0.1, lad_z_top - lad_z_bot)))
        lad_y = t_lad * deck_y
        if jump_y >= lad_y - 0.65:
            support_y = max(support_y, lad_y)

    # 1b. Walkable Front Wooden Veranda Porch (chicks can stand on top of porch at y=deck_y OR walk beneath!)
    if cx - hw_c - 0.2 <= wx <= cx + hw_c + 0.2 and z_porch_edge - 0.2 <= wz <= z_front_wall + 0.2:
        if jump_y >= deck_y - 0.55:
            support_y = max(support_y, deck_y)

    # 1c. Main Rustic Wooden Barn-Coop Walls + Steep Gabled Terracotta Tiled Roof (walkable roof!)
    if abs(wx - cx) < hw_c + chick_radius and abs(wz - cz) < hd_c + chick_radius:
        if jump_y >= wall_h - 0.45:
            # Stand anywhere on the two-sloped pitched roof (ridge along Z at wx = cx)!
            slope_t = max(0.0, min(1.0, abs(wx - cx) / max(0.1, hw_c)))
            roof_y = roof_h - slope_t * (roof_h - wall_h)
            support_y = max(support_y, roof_y)
        else:
            dx_e = (hw_c + chick_radius) - abs(wx - cx)
            dz_e = (hd_c + chick_radius) - abs(wz - cz)
            if dx_e < dz_e:
                wx = cx + ((hw_c + chick_radius) if wx >= cx else -(hw_c + chick_radius))
            else:
                wz = cz + ((hd_c + chick_radius) if wz >= cz else -(hd_c + chick_radius))

    # 1d. Pédro the Cormorant's Wooden Barrel (tonneau) at the foot of the coop
    bcx, bcz = CHICKEN_COOP["barrel_cx"], CHICKEN_COOP["barrel_cz"]
    br, bh = CHICKEN_COOP["barrel_r"], CHICKEN_COOP["barrel_h"]
    db = math.hypot(wx - bcx, wz - bcz)
    if db < br + chick_radius:
        if jump_y >= bh - 0.35:
            support_y = max(support_y, bh)
        else:
            if db < 1e-4:
                wx = bcx + br + chick_radius
            else:
                scale_b = (br + chick_radius) / db
                wx = bcx + (wx - bcx) * scale_b
                wz = bcz + (wz - bcz) * scale_b

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

    # 1. Giant Carmela Poulailler Grégoire Sub-Parts (depth-sorted independently for clean porch/ladder occlusion!)
    _cx, _cz = CHICKEN_COOP["cx"], CHICKEN_COOP["cz"]
    _hd = CHICKEN_COOP["d"] * 0.5
    _pd = CHICKEN_COOP["porch_d"]
    c_coop = to_cam(_cx, current_ground_y + 6.5, _cz)
    if c_coop[2] > -12.0:
        items.append((c_coop[2], "carmela_coop", CHICKEN_COOP))
    c_porch = to_cam(_cx, current_ground_y + CHICKEN_COOP["deck_y"], _cz - _hd - _pd * 0.5)
    if c_porch[2] > -9.0:
        items.append((c_porch[2], "coop_porch", CHICKEN_COOP))
    c_ladder = to_cam(_cx, current_ground_y + CHICKEN_COOP["deck_y"] * 0.5, _cz - _hd - _pd - 2.6)
    if c_ladder[2] > -7.0:
        items.append((c_ladder[2], "coop_ladder", CHICKEN_COOP))
    c_barrel = to_cam(CHICKEN_COOP["barrel_cx"], current_ground_y + 1.25, CHICKEN_COOP["barrel_cz"])
    if c_barrel[2] > -3.5:
        items.append((c_barrel[2], "pedro_barrel", CHICKEN_COOP))

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

    # 1. Carmela Storybook Coop (Poulailler) + Exterior Ladder + Pédro's Barrel
    _cx, _cz = CHICKEN_COOP["cx"], CHICKEN_COOP["cz"]
    _rz = CHICKEN_COOP["rz"]
    c_coop = to_cam(_cx, current_ground_y + 5.0, _cz)
    if c_coop[2] > -7.5:
        items.append((c_coop[2], "carmela_coop", CHICKEN_COOP))
    c_ladder = to_cam(_cx, current_ground_y + 1.6, _cz - _rz - 2.6)
    if c_ladder[2] > -5.5:
        items.append((c_ladder[2], "coop_ladder", CHICKEN_COOP))
    c_barrel = to_cam(CHICKEN_COOP["barrel_cx"], current_ground_y + 1.2, CHICKEN_COOP["barrel_cz"])
    if c_barrel[2] > -2.5:
        items.append((c_barrel[2], "pedro_barrel", CHICKEN_COOP))

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

    # 1. Carmela Storybook Coop (Poulailler) + Exterior Ladder + Pédro's Barrel
    _cx, _cz = CHICKEN_COOP["cx"], CHICKEN_COOP["cz"]
    _rz = CHICKEN_COOP["rz"]
    c_coop = to_cam(_cx, current_ground_y + 2.2, _cz)
    if c_coop[2] > -4.5:
        items.append((c_coop[2], "carmela_coop", CHICKEN_COOP))
    c_ladder = to_cam(_cx, current_ground_y + 0.7, _cz - _rz - 1.15)
    if c_ladder[2] > -3.0:
        items.append((c_ladder[2], "coop_ladder", CHICKEN_COOP))
    c_barrel = to_cam(CHICKEN_COOP["barrel_cx"], current_ground_y + 0.6, CHICKEN_COOP["barrel_cz"])
    if c_barrel[2] > -2.5:
        items.append((c_barrel[2], "pedro_barrel", CHICKEN_COOP))

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
    if kind == "carmela_coop":
        # Authentic "Les P'tites Poules / 不一样的卡梅拉" Poulailler Grégoire:
        # Huge timber-framed Alsatian wooden barn-coop, steep overhanging terracotta-tiled gable roof,
        # triangular attic loft (阁楼), big plank doorway, and shuttered windows (fenêtre & volets)!
        coop = payload  # type: ignore[assignment]
        cx, cz = coop["cx"], coop["cz"]
        hw_c = coop["w"] * 0.5
        hd_c = coop["d"] * 0.5
        deck_y = coop["deck_y"]
        wall_h = coop["wall_h"]
        roof_h = coop["roof_h"]
        yg = current_ground_y

        x0, x1 = cx - hw_c, cx + hw_c
        z0, z1 = cz - hd_c, cz + hd_c
        y_wall = yg + wall_h
        y_peak = yg + roof_h
        y_lower = yg + deck_y + 0.35

        faces: list[tuple[float, list[tuple[float, float, float]], tuple[int, int, int], tuple[int, int, int] | None]] = []

        # 1) Stone plinth foundation & main warm weathered oak plank walls (4 sides)
        # Front wall (-Z) lower cobble/stone plinth + upper golden-brown timber walls + front attic gable triangle
        w_front_col = (196, 144, 86)
        w_side_col = (176, 126, 72)
        w_back_col = (152, 108, 60)
        stone_col = (182, 170, 150)
        stone_side = (162, 150, 132)
        beam_col = (94, 58, 28)

        def add_quad(pts: list[tuple[float, float, float]], col: tuple[int, int, int], edge: tuple[int, int, int] | None = beam_col, bias: float = 0.0) -> None:
            if max(p[2] for p in pts) <= near_z:
                return
            d = sum(p[2] for p in pts) / len(pts) + bias
            faces.append((d, pts, col, edge))

        # Stone base walls (ground -> y_lower)
        add_quad([to_cam(x0, yg, z0), to_cam(x1, yg, z0), to_cam(x1, y_lower, z0), to_cam(x0, y_lower, z0)], stone_col, (124, 112, 94))
        add_quad([to_cam(x1, yg, z1), to_cam(x0, yg, z1), to_cam(x0, y_lower, z1), to_cam(x1, y_lower, z1)], (146, 134, 118), (112, 100, 84))
        add_quad([to_cam(x0, yg, z1), to_cam(x0, yg, z0), to_cam(x0, y_lower, z0), to_cam(x0, y_lower, z1)], stone_side, (112, 100, 84))
        add_quad([to_cam(x1, yg, z0), to_cam(x1, yg, z1), to_cam(x1, y_lower, z1), to_cam(x1, y_lower, z0)], (172, 160, 142), (112, 100, 84))

        # Upper wooden barn walls (y_lower -> y_wall)
        add_quad([to_cam(x0, y_lower, z0), to_cam(x1, y_lower, z0), to_cam(x1, y_wall, z0), to_cam(x0, y_wall, z0)], w_front_col)
        add_quad([to_cam(x1, y_lower, z1), to_cam(x0, y_lower, z1), to_cam(x0, y_wall, z1), to_cam(x1, y_wall, z1)], w_back_col)
        add_quad([to_cam(x0, y_lower, z1), to_cam(x0, y_lower, z0), to_cam(x0, y_wall, z0), to_cam(x0, y_wall, z1)], w_side_col)
        add_quad([to_cam(x1, y_lower, z0), to_cam(x1, y_lower, z1), to_cam(x1, y_wall, z1), to_cam(x1, y_wall, z0)], (184, 134, 78))

        # Front & Back Triangular Attic Gable Walls (阁楼 — y_wall -> y_peak)
        add_quad([to_cam(x0, y_wall, z0), to_cam(x1, y_wall, z0), to_cam(cx, y_peak, z0)], (206, 156, 98))
        add_quad([to_cam(x1, y_wall, z1), to_cam(x0, y_wall, z1), to_cam(cx, y_peak, z1)], w_back_col)

        # 2) Steep Overhanging Terracotta-Tiled Two-Sloped Gable Roof (人字顶瓦屋顶!)
        ox = 1.15
        oz = 1.05
        eave_y = y_wall - 0.55
        # Left & Right main tiled roof slopes (divided into 3 horizontal courses for crisp tile texture!)
        for ci in range(3):
            t0 = ci / 3.0
            t1 = (ci + 1) / 3.0
            lx0 = (x0 - ox) + t0 * (cx - (x0 - ox))
            lx1 = (x0 - ox) + t1 * (cx - (x0 - ox))
            rx0 = (x1 + ox) + t0 * (cx - (x1 + ox))
            rx1 = (x1 + ox) + t1 * (cx - (x1 + ox))
            ry0 = eave_y + t0 * (y_peak - eave_y)
            ry1 = eave_y + t1 * (y_peak - eave_y)
            tile_l = (202 - ci * 8, 86 - ci * 3, 52)
            tile_r = (182 - ci * 8, 76 - ci * 3, 46)
            add_quad([to_cam(lx0, ry0, z0 - oz), to_cam(lx0, ry0, z1 + oz), to_cam(lx1, ry1, z1 + oz), to_cam(lx1, ry1, z0 - oz)], tile_l, (118, 42, 24))
            add_quad([to_cam(rx0, ry0, z1 + oz), to_cam(rx0, ry0, z0 - oz), to_cam(rx1, ry1, z0 - oz), to_cam(rx1, ry1, z1 + oz)], tile_r, (108, 38, 22))

        # 3) Front Coop Plank Doorway (y = deck_y -> deck_y + 4.1) opening onto front porch
        d_x0, d_x1 = cx - 1.35, cx + 1.35
        d_y0, d_y1 = yg + deck_y + 0.08, yg + deck_y + 4.35
        add_quad([to_cam(d_x0, d_y0, z0 - 0.06), to_cam(d_x1, d_y0, z0 - 0.06), to_cam(d_x1, d_y1, z0 - 0.06), to_cam(d_x0, d_y1, z0 - 0.06)], (74, 46, 24), (118, 76, 38), bias=-0.22)

        # 4) Two Front Shuttered Windows (fenêtre + volets!) flanking the doorway & Attic Loft Window (阁楼窗)!
        for wx_c, wy_c, ww, wh in [
            (cx - 4.3, yg + deck_y + 2.7, 1.9, 2.0),
            (cx + 4.3, yg + deck_y + 2.7, 1.9, 2.0),
            (cx, y_wall + 2.8, 2.1, 2.3),  # Cozy triangular gable loft window!
        ]:
            # Window frame + blue/sky glass
            add_quad([to_cam(wx_c - ww * 0.5, wy_c - wh * 0.5, z0 - 0.07), to_cam(wx_c + ww * 0.5, wy_c - wh * 0.5, z0 - 0.07),
                      to_cam(wx_c + ww * 0.5, wy_c + wh * 0.5, z0 - 0.07), to_cam(wx_c - ww * 0.5, wy_c + wh * 0.5, z0 - 0.07)],
                     (112, 174, 218), (88, 54, 26), bias=-0.26)
            # Open wooden shutters (volets!) on left & right of each window
            sh_w = ww * 0.42
            add_quad([to_cam(wx_c - ww * 0.5 - sh_w, wy_c - wh * 0.5, z0 - 0.09), to_cam(wx_c - ww * 0.5, wy_c - wh * 0.5, z0 - 0.09),
                      to_cam(wx_c - ww * 0.5, wy_c + wh * 0.5, z0 - 0.09), to_cam(wx_c - ww * 0.5 - sh_w, wy_c + wh * 0.5, z0 - 0.09)],
                     (154, 82, 48), (88, 44, 22), bias=-0.28)
            add_quad([to_cam(wx_c + ww * 0.5, wy_c - wh * 0.5, z0 - 0.09), to_cam(wx_c + ww * 0.5 + sh_w, wy_c - wh * 0.5, z0 - 0.09),
                      to_cam(wx_c + ww * 0.5 + sh_w, wy_c + wh * 0.5, z0 - 0.09), to_cam(wx_c + ww * 0.5, wy_c + wh * 0.5, z0 - 0.09)],
                     (154, 82, 48), (88, 44, 22), bias=-0.28)

        _draw_quad_list(screen, faces, near_z, hw, hh, focal, win_w, win_h)

        # Half-timbered vertical & horizontal wood beam accents (colombages!) on visible front/side walls
        for bx in (x0 + 0.12, cx - hw_c * 0.5, cx + hw_c * 0.5, x1 - 0.12):
            pb0, pb1 = to_cam(bx, y_lower, z0 - 0.05), to_cam(bx, y_wall, z0 - 0.05)
            if pb0[2] > near_z and pb1[2] > near_z:
                s0 = (round(hw + (pb0[0] / pb0[2]) * focal), round(hh - (pb0[1] / pb0[2]) * focal))
                s1 = (round(hw + (pb1[0] / pb1[2]) * focal), round(hh - (pb1[1] / pb1[2]) * focal))
                pygame.draw.line(screen, beam_col, s0, s1, max(3, int(round(0.24 * focal / max(1.0, (pb0[2] + pb1[2]) * 0.5)))))
        # Horizontal timber beam across gable base
        pg0, pg1 = to_cam(x0, y_wall, z0 - 0.06), to_cam(x1, y_wall, z0 - 0.06)
        if pg0[2] > near_z and pg1[2] > near_z:
            sg0 = (round(hw + (pg0[0] / pg0[2]) * focal), round(hh - (pg0[1] / pg0[2]) * focal))
            sg1 = (round(hw + (pg1[0] / pg1[2]) * focal), round(hh - (pg1[1] / pg1[2]) * focal))
            pygame.draw.line(screen, beam_col, sg0, sg1, max(3, int(round(0.26 * focal / max(1.0, (pg0[2] + pg1[2]) * 0.5)))))

    elif kind == "coop_porch":
        # Wide front wooden veranda gallery on timber posts + cozy straw nest mounds
        coop = payload  # type: ignore[assignment]
        cx, cz = coop["cx"], coop["cz"]
        hw_c = coop["w"] * 0.5
        hd_c = coop["d"] * 0.5
        porch_d = coop["porch_d"]
        deck_y = coop["deck_y"]
        yg = current_ground_y
        zp = cz - hd_c - porch_d * 0.5
        # Support timber posts under the porch
        for px in (cx - hw_c + 0.35, cx - 2.2, cx + 2.2, cx + hw_c - 0.35):
            _draw_box(
                screen, to_cam, px, yg + deck_y * 0.5, cz - hd_c - porch_d + 0.28, 0.34, deck_y, 0.34,
                colors={"top": (136, 88, 44), "front": (128, 82, 40), "right": (118, 74, 36), "left": (108, 66, 32), "back": (102, 62, 30)},
                near_z=near_z, hw=hw, hh=hh, focal=focal, win_w=win_w, win_h=win_h,
                edge_col=(78, 46, 20),
            )
        # Main veranda deck planks
        _draw_box(
            screen, to_cam, cx, yg + deck_y - 0.14, zp, coop["w"] + 0.3, 0.28, porch_d,
            colors={"top": (184, 134, 76), "front": (152, 104, 54), "right": (144, 96, 50), "left": (136, 90, 46), "back": (124, 82, 42)},
            near_z=near_z, hw=hw, hh=hh, focal=focal, win_w=win_w, win_h=win_h,
            edge_col=(88, 54, 24),
        )
        # Low porch railing on left & right wings (leaving center open for the wooden ladder!)
        for side_x in (cx - hw_c * 0.58, cx + hw_c * 0.58):
            _draw_box(
                screen, to_cam, side_x, yg + deck_y + 0.55, cz - hd_c - porch_d + 0.18, coop["w"] * 0.36, 0.18, 0.18,
                colors={"top": (176, 126, 68), "front": (154, 106, 56), "right": (142, 94, 48), "left": (136, 90, 46), "back": (124, 82, 42)},
                near_z=near_z, hw=hw, hh=hh, focal=focal, win_w=win_w, win_h=win_h,
                edge_col=(88, 54, 24),
            )

    elif kind == "coop_ladder":
        # Wide chick-scale "l'échelle du poulailler" leaning up to the front veranda deck!
        coop = payload  # type: ignore[assignment]
        cx, cz = coop["cx"], coop["cz"]
        hd_c = coop["d"] * 0.5
        porch_d = coop["porch_d"]
        deck_y = coop["deck_y"]
        yg = current_ground_y
        z_top = cz - hd_c - porch_d + 0.15
        z_bot = z_top - 5.10
        y_top = yg + deck_y + 0.04
        y_bot = yg + 0.05
        for rx_off in (-1.05, 1.05):
            p_b = to_cam(cx + rx_off, y_bot, z_bot)
            p_t = to_cam(cx + rx_off, y_top, z_top)
            if p_b[2] > near_z and p_t[2] > near_z:
                sb = (round(hw + (p_b[0] / p_b[2]) * focal), round(hh - (p_b[1] / p_b[2]) * focal))
                st = (round(hw + (p_t[0] / p_t[2]) * focal), round(hh - (p_t[1] / p_t[2]) * focal))
                w_px = max(4, int(round(0.18 * focal / max(0.8, (p_b[2] + p_t[2]) * 0.5))))
                pygame.draw.line(screen, (148, 96, 48), sb, st, w_px)
        for ri in range(1, 10):
            rt = ri / 10.0
            rz_r = z_bot + rt * (z_top - z_bot)
            ry_r = y_bot + rt * (y_top - y_bot)
            pa, pb = to_cam(cx - 1.05, ry_r, rz_r), to_cam(cx + 1.05, ry_r, rz_r)
            if pa[2] > near_z and pb[2] > near_z:
                sa = (round(hw + (pa[0] / pa[2]) * focal), round(hh - (pa[1] / pa[2]) * focal))
                sb = (round(hw + (pb[0] / pb[2]) * focal), round(hh - (pb[1] / pb[2]) * focal))
                w_px = max(3, int(round(0.14 * focal / max(0.8, (pa[2] + pb[2]) * 0.5))))
                pygame.draw.line(screen, (184, 132, 74), sa, sb, w_px)

    elif kind == "pedro_barrel":
        # Pédro the Cormorant's wooden oak barrel (tonneau) with iron hoops!
        coop = payload  # type: ignore[assignment]
        bcx, bcz = coop["barrel_cx"], coop["barrel_cz"]
        br, bh = coop["barrel_r"], coop["barrel_h"]
        yg = current_ground_y
        n_b = 8
        faces = []
        top_pts = []
        for i in range(n_b):
            a0 = (i / n_b) * math.tau
            a1 = ((i + 1) / n_b) * math.tau
            r_end = br * 0.88
            r_mid = br * 1.06
            b0 = to_cam(bcx + math.cos(a0) * r_end, yg, bcz + math.sin(a0) * r_end)
            b1 = to_cam(bcx + math.cos(a1) * r_end, yg, bcz + math.sin(a1) * r_end)
            m0 = to_cam(bcx + math.cos(a0) * r_mid, yg + bh * 0.5, bcz + math.sin(a0) * r_mid)
            m1 = to_cam(bcx + math.cos(a1) * r_mid, yg + bh * 0.5, bcz + math.sin(a1) * r_mid)
            t0 = to_cam(bcx + math.cos(a0) * r_end, yg + bh, bcz + math.sin(a0) * r_end)
            t1 = to_cam(bcx + math.cos(a1) * r_end, yg + bh, bcz + math.sin(a1) * r_end)
            top_pts.append(t0)
            shade = 0.80 + 0.20 * math.sin((a0 + a1) * 0.5)
            oak = (int(164 * shade), int(106 * shade), int(56 * shade))
            if max(p[2] for p in (b0, b1, m1, m0)) > near_z:
                faces.append(((b0[2] + b1[2] + m1[2] + m0[2]) * 0.25, [b0, b1, m1, m0], oak, (78, 48, 24)))
            if max(p[2] for p in (m0, m1, t1, t0)) > near_z:
                faces.append(((m0[2] + m1[2] + t1[2] + t0[2]) * 0.25, [m0, m1, t1, t0], oak, (78, 48, 24)))
        if top_pts and max(p[2] for p in top_pts) > near_z:
            faces.append((sum(p[2] for p in top_pts) / len(top_pts), top_pts, (186, 128, 72), (78, 48, 24)))
        _draw_quad_list(screen, faces, near_z, hw, hh, focal, win_w, win_h)
        for hy in (yg + bh * 0.22, yg + bh * 0.78):
            for i in range(n_b):
                a0 = (i / n_b) * math.tau
                a1 = ((i + 1) / n_b) * math.tau
                p0 = to_cam(bcx + math.cos(a0) * br * 0.99, hy, bcz + math.sin(a0) * br * 0.99)
                p1 = to_cam(bcx + math.cos(a1) * br * 0.99, hy, bcz + math.sin(a1) * br * 0.99)
                if p0[2] > near_z and p1[2] > near_z:
                    s0 = (round(hw + (p0[0] / p0[2]) * focal), round(hh - (p0[1] / p0[2]) * focal))
                    s1 = (round(hw + (p1[0] / p1[2]) * focal), round(hh - (p1[1] / p1[2]) * focal))
                    pygame.draw.line(screen, (62, 64, 70), s0, s1, 2)

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
