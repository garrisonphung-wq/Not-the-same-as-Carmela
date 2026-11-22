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

# Authentic "Les P'tites Poules / 不一样的卡梅拉" Storybook Poulailler:
# Rounded egg-like stone & timber coop tower, upper battlements (créneaux),
# terracotta tiled gable/loft roof, exterior wooden ladder (échelle), and Pédro's wooden barrel!
CHICKEN_COOP = {
    "cx": -14.0,
    "cz": 14.0,
    "rx": 2.35,      # Rounded octagonal radius X
    "rz": 2.15,      # Rounded octagonal radius Z
    "base_h": 2.75,  # Main stone & half-timber body height
    "crenel_h": 3.45,# Battlement parapet height ("Les coqs aux créneaux !")
    "roof_h": 5.35,  # Terracotta tiled loft roof peak
    "barrel_cx": -10.85,
    "barrel_cz": 12.15,
    "barrel_r": 0.62,
    "barrel_h": 1.18,
}

# (cx, cz, w, d, base_y, h, yaw_rad)
HAY_BALES: list[dict[str, float]] = [
    # Cozy stacked trio right beside the Carmela coop & Pédro's barrel
    {"cx": -8.2, "cz": 12.6, "w": 2.1, "d": 1.5, "base_y": 0.0, "h": 1.12},
    {"cx": -8.3, "cz": 14.5, "w": 2.1, "d": 1.5, "base_y": 0.0, "h": 1.12},
    {"cx": -8.2, "cz": 13.5, "w": 1.9, "d": 1.4, "base_y": 1.12, "h": 1.05},
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
    coop_x0 = CHICKEN_COOP["cx"] - CHICKEN_COOP["rx"] - 1.2
    coop_x1 = CHICKEN_COOP["cx"] + CHICKEN_COOP["rx"] + 1.2
    coop_z0 = CHICKEN_COOP["cz"] - CHICKEN_COOP["rz"] - 2.6
    coop_z1 = CHICKEN_COOP["cz"] + CHICKEN_COOP["rz"] + 1.2

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

    # 1. Carmela Storybook Poulailler: Rounded Egg-Tower Coop + Battlements + Roof + Exterior Ladder + Pédro's Barrel
    cx = CHICKEN_COOP["cx"]
    cz = CHICKEN_COOP["cz"]
    rx = CHICKEN_COOP["rx"]
    rz = CHICKEN_COOP["rz"]
    base_h = CHICKEN_COOP["base_h"]
    crenel_h = CHICKEN_COOP["crenel_h"]
    roof_h = CHICKEN_COOP["roof_h"]

    # 1a. Exterior Wooden Ladder (l'échelle du poulailler) leaning up to the front coop door/porch (-Z face)
    lad_z_bot = cz - rz - 2.35
    lad_z_top = cz - rz + 0.15
    if cx - 0.62 <= wx <= cx + 0.62 and lad_z_bot <= wz <= lad_z_top:
        t_lad = max(0.0, min(1.0, (wz - lad_z_bot) / max(0.1, lad_z_top - lad_z_bot)))
        lad_y = t_lad * 1.45
        if jump_y >= lad_y - 0.45:
            support_y = max(support_y, lad_y)

    # 1b. Rounded coop tower body + walkable battlements (créneaux) & tiled roof
    dx_c = (wx - cx) / max(0.1, rx + chick_radius)
    dz_c = (wz - cz) / max(0.1, rz + chick_radius)
    ell_d = math.hypot(dx_c, dz_c)
    if ell_d < 1.0:
        if jump_y >= crenel_h - 0.35:
            # Stand on tiled roof or battlements rim!
            if ell_d < 0.72:
                frac_r = min(1.0, ell_d / 0.72)
                support_y = max(support_y, roof_h - frac_r * (roof_h - crenel_h))
            else:
                support_y = max(support_y, base_h + 0.35)
        elif jump_y >= base_h - 0.35 and ell_d > 0.72:
            support_y = max(support_y, base_h)
        else:
            if ell_d < 1e-4:
                wx = cx + rx + chick_radius
            else:
                wx = cx + (dx_c / ell_d) * (rx + chick_radius)
                wz = cz + (dz_c / ell_d) * (rz + chick_radius)

    # 1c. Pédro the Cormorant's Wooden Barrel (tonneau) at the foot of the coop
    bcx, bcz = CHICKEN_COOP["barrel_cx"], CHICKEN_COOP["barrel_cz"]
    br, bh = CHICKEN_COOP["barrel_r"], CHICKEN_COOP["barrel_h"]
    db = math.hypot(wx - bcx, wz - bcz)
    if db < br + chick_radius:
        if jump_y >= bh - 0.28:
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
    if kind == "carmela_coop":
        coop = payload  # type: ignore[assignment]
        cx, cz = coop["cx"], coop["cz"]
        rx, rz = coop["rx"], coop["rz"]
        base_h = coop["base_h"]
        crenel_h = coop["crenel_h"]
        roof_h = coop["roof_h"]
        yg = current_ground_y
        y_mid = yg + base_h * 0.52
        y_base = yg + base_h
        y_cren = yg + crenel_h
        y_peak = yg + roof_h

        # Rounded 10-sided egg-tower geometry tapering slightly inward near the top (egg silhouette!)
        n_seg = 10
        faces: list[tuple[float, list[tuple[float, float, float]], tuple[int, int, int], tuple[int, int, int] | None]] = []

        # Half-timbered rustic wood vertical beams & stone/plaster lower wall + warm wood upper wall
        for i in range(n_seg):
            a0 = (i / n_seg) * math.tau
            a1 = ((i + 1) / n_seg) * math.tau
            # Slight egg-like swell at middle, narrower at bottom & top
            rb0 = 0.94
            rm0 = 1.03
            rt0 = 0.92
            p_b0 = to_cam(cx + math.cos(a0) * rx * rb0, yg, cz + math.sin(a0) * rz * rb0)
            p_b1 = to_cam(cx + math.cos(a1) * rx * rb0, yg, cz + math.sin(a1) * rz * rb0)
            p_m0 = to_cam(cx + math.cos(a0) * rx * rm0, y_mid, cz + math.sin(a0) * rz * rm0)
            p_m1 = to_cam(cx + math.cos(a1) * rx * rm0, y_mid, cz + math.sin(a1) * rz * rm0)
            p_t0 = to_cam(cx + math.cos(a0) * rx * rt0, y_base, cz + math.sin(a0) * rz * rt0)
            p_t1 = to_cam(cx + math.cos(a1) * rx * rt0, y_base, cz + math.sin(a1) * rz * rt0)

            light = 0.80 + 0.20 * math.sin((a0 + a1) * 0.5 - 0.6)
            # Lower stone base (warm limestone/cobble)
            stone_c = (int(208 * light), int(196 * light), int(174 * light))
            # Upper timber plank body (warm honey oak)
            wood_c = (int(198 * light), int(146 * light), int(88 * light))
            if max(p[2] for p in (p_b0, p_b1, p_m1, p_m0)) > near_z:
                d_low = (p_b0[2] + p_b1[2] + p_m1[2] + p_m0[2]) * 0.25
                faces.append((d_low, [p_b0, p_b1, p_m1, p_m0], stone_c, (128, 114, 96)))
            if max(p[2] for p in (p_m0, p_m1, p_t1, p_t0)) > near_z:
                d_up = (p_m0[2] + p_m1[2] + p_t1[2] + p_t0[2]) * 0.25
                faces.append((d_up, [p_m0, p_m1, p_t1, p_t0], wood_c, (112, 74, 38)))

            # Medieval Battlements / Crenels ("Les coqs aux créneaux !") on every even face around top rim
            if i % 2 == 0:
                cr_in = 0.90
                cr_out = 1.00
                c0 = to_cam(cx + math.cos(a0) * rx * cr_out, y_base - 0.05, cz + math.sin(a0) * rz * cr_out)
                c1 = to_cam(cx + math.cos(a1) * rx * cr_out, y_base - 0.05, cz + math.sin(a1) * rz * cr_out)
                c2 = to_cam(cx + math.cos(a1) * rx * cr_in, y_cren, cz + math.sin(a1) * rz * cr_in)
                c3 = to_cam(cx + math.cos(a0) * rx * cr_in, y_cren, cz + math.sin(a0) * rz * cr_in)
                if max(p[2] for p in (c0, c1, c2, c3)) > near_z:
                    faces.append(((c0[2] + c1[2] + c2[2] + c3[2]) * 0.25 - 0.04, [c0, c1, c2, c3], (182, 130, 74), (104, 66, 34)))

            # Steep Conical/Tiled Storybook Roof rising from inner attic wall above the battlements!
            r_rad = 0.80
            rp0 = to_cam(cx + math.cos(a0) * rx * r_rad, y_cren - 0.12, cz + math.sin(a0) * rz * r_rad)
            rp1 = to_cam(cx + math.cos(a1) * rx * r_rad, y_cren - 0.12, cz + math.sin(a1) * rz * r_rad)
            rp_mid0 = to_cam(cx + math.cos(a0) * rx * 0.42, (y_cren + y_peak) * 0.52, cz + math.sin(a0) * rz * 0.42)
            rp_mid1 = to_cam(cx + math.cos(a1) * rx * 0.42, (y_cren + y_peak) * 0.52, cz + math.sin(a1) * rz * 0.42)
            rp_tip = to_cam(cx, y_peak, cz)
            tile_l = 0.82 + 0.18 * math.cos((a0 + a1) * 0.5 + 0.5)
            tile_low_c = (int(196 * tile_l), int(84 * tile_l), int(56 * tile_l))
            tile_hi_c = (int(212 * tile_l), int(98 * tile_l), int(64 * tile_l))
            if max(p[2] for p in (rp0, rp1, rp_mid1, rp_mid0)) > near_z:
                faces.append(((rp0[2] + rp1[2] + rp_mid1[2] + rp_mid0[2]) * 0.25, [rp0, rp1, rp_mid1, rp_mid0], tile_low_c, (118, 44, 28)))
            if max(p[2] for p in (rp_mid0, rp_mid1, rp_tip)) > near_z:
                faces.append(((rp_mid0[2] + rp_mid1[2] + rp_tip[2]) * 0.25, [rp_mid0, rp_mid1, rp_tip], tile_hi_c, (118, 44, 28)))

        # Front Chicken Doorway & Small Balcony Porch facing the farmyard (-Z)
        z_front = cz - rz * 1.02
        door0 = to_cam(cx - 0.46, yg + 1.35, z_front - 0.04)
        door1 = to_cam(cx + 0.46, yg + 1.35, z_front - 0.04)
        door2 = to_cam(cx + 0.42, yg + 2.38, z_front - 0.04)
        door3 = to_cam(cx - 0.42, yg + 2.38, z_front - 0.04)
        if max(p[2] for p in (door0, door1, door2, door3)) > near_z:
            faces.append((door0[2] - 0.14, [door0, door1, door2, door3], (68, 42, 24), (124, 82, 42)))

        # Cozy Attic Loft Window (grenier) up under the terracotta tiled roof!
        win0 = to_cam(cx - 0.34, y_cren + 0.16, cz - rz * 0.72)
        win1 = to_cam(cx + 0.34, y_cren + 0.16, cz - rz * 0.72)
        win2 = to_cam(cx + 0.30, y_cren + 0.74, cz - rz * 0.56)
        win3 = to_cam(cx - 0.30, y_cren + 0.74, cz - rz * 0.56)
        if max(p[2] for p in (win0, win1, win2, win3)) > near_z:
            faces.append((win0[2] - 0.18, [win0, win1, win2, win3], (110, 170, 215), (96, 62, 32)))

        _draw_quad_list(screen, faces, near_z, hw, hh, focal, win_w, win_h)

        # Tiny front balcony ledge just under the coop door for the ladder top
        _draw_box(
            screen, to_cam, cx, yg + 1.32, z_front - 0.18, 1.35, 0.14, 0.55,
            colors={"top": (182, 130, 74), "front": (154, 106, 56), "right": (146, 98, 52), "left": (138, 92, 48), "back": (128, 84, 44)},
            near_z=near_z, hw=hw, hh=hh, focal=focal, win_w=win_w, win_h=win_h,
            edge_col=(96, 60, 28),
        )

    elif kind == "coop_ladder":
        # Classic "l'échelle du poulailler" — 2 wooden side rails + horizontal wooden rungs!
        coop = payload  # type: ignore[assignment]
        cx, cz = coop["cx"], coop["cz"]
        rz = coop["rz"]
        yg = current_ground_y
        z_top = cz - rz - 0.25
        z_bot = z_top - 2.20
        y_top = yg + 1.38
        y_bot = yg + 0.04
        # Two wooden side rails
        for rx_off in (-0.40, 0.40):
            p_b = to_cam(cx + rx_off, y_bot, z_bot)
            p_t = to_cam(cx + rx_off, y_top, z_top)
            if p_b[2] > near_z and p_t[2] > near_z:
                sb = (round(hw + (p_b[0] / p_b[2]) * focal), round(hh - (p_b[1] / p_b[2]) * focal))
                st = (round(hw + (p_t[0] / p_t[2]) * focal), round(hh - (p_t[1] / p_t[2]) * focal))
                w_px = max(3, int(round(0.08 * focal / max(0.8, (p_b[2] + p_t[2]) * 0.5))))
                pygame.draw.line(screen, (148, 96, 48), sb, st, w_px)
        # 7 wooden ladder rungs
        for ri in range(1, 8):
            rt = ri / 8.0
            rz_r = z_bot + rt * (z_top - z_bot)
            ry_r = y_bot + rt * (y_top - y_bot)
            pa, pb = to_cam(cx - 0.40, ry_r, rz_r), to_cam(cx + 0.40, ry_r, rz_r)
            if pa[2] > near_z and pb[2] > near_z:
                sa = (round(hw + (pa[0] / pa[2]) * focal), round(hh - (pa[1] / pa[2]) * focal))
                sb = (round(hw + (pb[0] / pb[2]) * focal), round(hh - (pb[1] / pb[2]) * focal))
                w_px = max(2, int(round(0.06 * focal / max(0.8, (pa[2] + pb[2]) * 0.5))))
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
        # Iron barrel hoops
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
