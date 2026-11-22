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
    "cx": -17.5,
    "cz": 18.0,
    "egg_rx": 8.4,   # Colossal wooden egg radius X (~16.8m wide!)
    "egg_rz": 8.0,   # Colossal wooden egg radius Z (~16.0m deep!)
    "belly_y0": 5.6, # Egg bottom starts 5.6m above grass on 4 tall wooden stilt legs!
    "belly_y1": 23.8,# Egg top meets terracotta pitched roof cap
    "roof_h": 30.5,  # Colossal terracotta-tiled gable roof peak (~13x chick height!)
    "door_y": 7.2,   # Front arched chicken doorway & walkable interior coop floor height
    "barrel_cx": -6.8,
    "barrel_cz": 9.8,
    "barrel_r": 1.55,
    "barrel_h": 1.32,# Easy to hop right onto with any tap of J (MIN_JUMP_HEIGHT=1.40)!
}

# (cx, cz, w, d, base_y, h)
HAY_BALES: list[dict[str, float]] = [
    # Cozy stacked hay bales right beside Pédro's barrel & the colossal Carmela coop (with walkable 0.55m step!)
    {"cx": -3.4, "cz": 12.4, "w": 2.1, "d": 1.7, "base_y": 0.0, "h": 0.55},
    {"cx": -1.5, "cz": 13.5, "w": 2.6, "d": 1.9, "base_y": 0.0, "h": 1.05},
    {"cx": -1.6, "cz": 16.2, "w": 2.6, "d": 1.9, "base_y": 0.0, "h": 1.05},
    {"cx": -1.5, "cz": 14.8, "w": 2.4, "d": 1.8, "base_y": 1.05, "h": 0.95},
    # Sunny meadow hay stack on the right side (with walkable 0.55m step!)
    {"cx": 11.4, "cz": 9.2, "w": 2.1, "d": 1.7, "base_y": 0.0, "h": 0.55},
    {"cx": 12.6, "cz": 10.5, "w": 2.6, "d": 1.9, "base_y": 0.0, "h": 1.05},
    {"cx": 15.0, "cz": 11.4, "w": 2.4, "d": 1.8, "base_y": 0.0, "h": 1.05},
    {"cx": 13.7, "cz": 10.9, "w": 2.3, "d": 1.7, "base_y": 1.05, "h": 0.95},
    # Single sunny bale near front-left fence
    {"cx": -8.8, "cz": -5.2, "w": 2.5, "d": 1.8, "base_y": 0.0, "h": 1.02},
]


def _build_fence_segments() -> list[tuple[float, float, float, float]]:
    """Build wooden paddock fence lines leaving wide open front entrance."""
    segs: list[tuple[float, float, float, float]] = []

    def add_chain(pts: list[tuple[float, float]]) -> None:
        for i in range(len(pts) - 1):
            segs.append((pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]))

    add_chain([
        (-5.5, -12.0),
        (-31.5, -12.0),
        (-31.5, 31.5),
        (23.5, 31.5),
        (23.5, -12.0),
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
    {"wx": -34.5, "wz": 4.0, "scale": 1.90, "seed": 1.0},
    {"wx": -34.5, "wz": 29.5, "scale": 2.10, "seed": 2.3},
    {"wx": -6.5, "wz": 34.5, "scale": 1.95, "seed": 3.7},
    {"wx": 12.5, "wz": 34.5, "scale": 2.00, "seed": 4.9},
    {"wx": 26.5, "wz": 16.0, "scale": 1.85, "seed": 5.4},
    {"wx": 26.0, "wz": -3.5, "scale": 1.70, "seed": 6.8},
    {"wx": -33.0, "wz": -14.5, "scale": 1.80, "seed": 7.5},
    {"wx": 18.5, "wz": -15.5, "scale": 1.70, "seed": 8.2},
    {"wx": 3.0, "wz": 35.5, "scale": 2.05, "seed": 9.1},
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
    coop_x0 = CHICKEN_COOP["cx"] - CHICKEN_COOP["egg_rx"] - 2.0
    coop_x1 = CHICKEN_COOP["cx"] + CHICKEN_COOP["egg_rx"] + 3.5
    coop_z0 = CHICKEN_COOP["cz"] - CHICKEN_COOP["egg_rz"] - 9.0
    coop_z1 = CHICKEN_COOP["cz"] + CHICKEN_COOP["egg_rz"] + 2.0

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

    # 1. Giant Carmela Egg-on-Legs Poulailler + Walkable Stairs + Walk-Inside Floor + Pédro's Barrel
    cx = CHICKEN_COOP["cx"]
    cz = CHICKEN_COOP["cz"]
    erx = CHICKEN_COOP["egg_rx"]
    erz = CHICKEN_COOP["egg_rz"]
    by0 = CHICKEN_COOP["belly_y0"]
    by1 = CHICKEN_COOP["belly_y1"]
    roof_h = CHICKEN_COOP["roof_h"]
    door_y = CHICKEN_COOP["door_y"]

    # 1a. 4 Splayed Wooden Stilt Legs (chicks can walk freely underneath the giant wooden egg!)
    leg_dx = erx * 0.62
    leg_dz = erz * 0.62
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            t_leg = max(0.0, min(1.0, jump_y / max(0.1, by0)))
            lx = cx + sx * leg_dx * (1.28 - 0.36 * t_leg)
            lz = cz + sz * leg_dz * (1.28 - 0.36 * t_leg)
            if jump_y < by0 + 0.3:
                dl = math.hypot(wx - lx, wz - lz)
                lr = 0.65 + chick_radius
                if dl < lr:
                    if dl < 1e-4:
                        wx = lx + lr
                    else:
                        wx = lx + ((wx - lx) / dl) * lr
                        wz = lz + ((wz - lz) / dl) * lr

    # 1b. Grand Wide Walkable Wooden Coop Stairs (grass -> doorway landing -> straight inside!)
    stair_z_bot = cz - erz - 8.4
    stair_z_top = cz - erz - 0.65  # Reaches full doorway height (7.2m) right BEFORE the egg doorway!
    if cx - 1.95 <= wx <= cx + 1.95 and stair_z_bot <= wz <= cz - erz * 0.65:
        t_st = max(0.0, min(1.0, (wz - stair_z_bot) / max(0.1, stair_z_top - stair_z_bot)))
        stair_y = t_st * door_y
        if jump_y >= stair_y - 0.95:
            support_y = max(support_y, stair_y)

    # 1c. Colossal Egg Shell + Open Front Doorway + Walkable Cozy Interior Room Floor (y = door_y)!
    in_door_corridor = (abs(wx - cx) <= 1.75) and (wz < cz) and (door_y - 1.35 <= jump_y <= door_y + 4.8)
    dx_e = (wx - cx) / max(0.1, erx + chick_radius)
    dz_e = (wz - cz) / max(0.1, erz + chick_radius)
    ell_d = math.hypot(dx_e, dz_e)

    # Interior floor radius (smoothly covers entire inside of the egg room at y = door_y)
    dx_in = (wx - cx) / max(0.1, erx - 0.55)
    dz_in = (wz - cz) / max(0.1, erz - 0.55)
    ell_in = math.hypot(dx_in, dz_in)

    if jump_y >= by1 - 0.55:
        # Walk/land on top of the terracotta gable roof cap!
        if ell_d < 1.0:
            slope_t = max(0.0, min(1.0, abs(wx - cx) / max(0.1, erx * 0.65)))
            support_y = max(support_y, roof_h - slope_t * (roof_h - by1))
    elif jump_y >= door_y - 0.85:
        # Doorway / Interior height band!
        if ell_in <= 1.0:
            # Inside the giant egg coop -> stand on the cozy wooden interior floor!
            support_y = max(support_y, door_y)
            # Keep chick gently inside curved inner egg walls unless leaving through open doorway!
            wall_r = 0.84
            if ell_in > wall_r and not in_door_corridor:
                wx = cx + (dx_in / ell_in) * wall_r * (erx - 0.55)
                wz = cz + (dz_in / ell_in) * wall_r * (erz - 0.55)
        elif ell_d < 1.0 and not in_door_corridor:
            # Outside wall ring (block entry everywhere EXCEPT straight through the open front doorway!)
            if ell_d < 1e-4:
                wx = cx + erx + chick_radius
            else:
                wx = cx + (dx_e / ell_d) * (erx + chick_radius)
                wz = cz + (dz_e / ell_d) * (erz + chick_radius)
    elif jump_y >= by0 - 0.65:
        # Lower egg belly below doorway floor (push outside unless below the egg on the grass!)
        if ell_d < 1.0:
            if ell_d < 1e-4:
                wx = cx + erx + chick_radius
            else:
                wx = cx + (dx_e / ell_d) * (erx + chick_radius)
                wz = cz + (dz_e / ell_d) * (erz + chick_radius)

    # 1d. Pédro the Cormorant's Wooden Barrel (tonneau) — easily jumpable onto!
    bcx, bcz = CHICKEN_COOP["barrel_cx"], CHICKEN_COOP["barrel_cz"]
    br, bh = CHICKEN_COOP["barrel_r"], CHICKEN_COOP["barrel_h"]
    db = math.hypot(wx - bcx, wz - bcz)
    if db < br + chick_radius:
        if jump_y >= bh - 0.55:
            support_y = max(support_y, bh)
        else:
            if db < 1e-4:
                wx = bcx + br + chick_radius
            else:
                scale_b = (br + chick_radius) / db
                wx = bcx + (wx - bcx) * scale_b
                wz = bcz + (wz - bcz) * scale_b

    # 2. Hay Bales (walk onto low 0.55m step OR hop easily onto 1.05m/2.00m bales!)
    for bale in HAY_BALES:
        bx, bz = bale["cx"], bale["cz"]
        bhx = bale["w"] * 0.5 + chick_radius
        bhz = bale["d"] * 0.5 + chick_radius
        top_y = bale["base_y"] + bale["h"]
        if abs(wx - bx) < bhx and abs(wz - bz) < bhz:
            if jump_y >= top_y - 0.58:
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

    # 1. Giant Carmela Egg-on-Legs Coop Sub-Parts (egg tower, front ladder + perch, Pédro's barrel)
    _cx, _cz = CHICKEN_COOP["cx"], CHICKEN_COOP["cz"]
    _erz = CHICKEN_COOP["egg_rz"]
    c_coop = to_cam(_cx, current_ground_y + 10.0, _cz)
    c_coop_back = to_cam(_cx, current_ground_y + 10.0, _cz + _erz * 0.85)
    # When inside or right at the coop, push sort depth toward the back so chicks inside render clearly in front!
    coop_depth = max(c_coop[2], c_coop_back[2]) if c_coop[2] < 9.5 else c_coop[2]
    if c_coop[2] > -22.0:
        items.append((coop_depth, "carmela_coop", CHICKEN_COOP))
    c_ladder = to_cam(_cx, current_ground_y + CHICKEN_COOP["door_y"] * 0.5, _cz - _erz - 4.0)
    if c_ladder[2] > -12.0:
        items.append((c_ladder[2], "coop_ladder", CHICKEN_COOP))
    c_barrel = to_cam(CHICKEN_COOP["barrel_cx"], current_ground_y + 1.25, CHICKEN_COOP["barrel_cz"])
    if c_barrel[2] > -3.5:
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
        # Hollow Walk-Inside Giant Egg-on-Legs Poulailler:
        # - 4 splayed wooden stilt legs
        # - Back-face culled exterior wooden egg shell WITH ACTUAL OPEN FRONT ARCHED DOORWAY
        # - Cozy interior wooden plank floor + inward egg walls + straw nests with white eggs + perches!
        # - Terracotta-tiled gable roof cap (人字顶瓦片)
        coop = payload  # type: ignore[assignment]
        cx, cz = coop["cx"], coop["cz"]
        erx = coop["egg_rx"]
        erz = coop["egg_rz"]
        by0 = coop["belly_y0"]
        by1 = coop["belly_y1"]
        roof_h = coop["roof_h"]
        door_y = coop["door_y"]
        yg = current_ground_y

        faces: list[tuple[float, list[tuple[float, float, float]], tuple[int, int, int], tuple[int, int, int] | None]] = []

        def add_poly(
            pts: list[tuple[float, float, float]],
            col: tuple[int, int, int],
            edge: tuple[int, int, int] | None = (88, 52, 24),
            bias: float = 0.0,
            cull_backface: bool = False,
        ) -> None:
            if max(p[2] for p in pts) <= near_z:
                return
            if cull_backface and min(p[2] for p in pts) > near_z and len(pts) >= 3:
                # 2D screen-space signed winding check (positive = front-facing CCW in screen coords)
                s_pts = [((p[0] / p[2]), -(p[1] / p[2])) for p in pts]
                area2 = 0.0
                for si in range(len(s_pts)):
                    ax, ay = s_pts[si]
                    bx, by = s_pts[(si + 1) % len(s_pts)]
                    area2 += ax * by - bx * ay
                if area2 <= 0.0:
                    return
            faces.append((sum(p[2] for p in pts) / len(pts) + bias, pts, col, edge))

        # --- A. 4 Splayed Wooden Timber Legs (pattes) ---
        leg_dx = erx * 0.62
        leg_dz = erz * 0.62
        for sx in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                bx, bz = cx + sx * leg_dx * 1.28, cz + sz * leg_dz * 1.28
                tx, tz = cx + sx * leg_dx * 0.88, cz + sz * leg_dz * 0.88
                yb, yt = yg, yg + by0 + 1.35
                w_l = 0.44
                p00 = to_cam(bx - w_l, yb, bz - w_l)
                p10 = to_cam(bx + w_l, yb, bz - w_l)
                p11 = to_cam(bx + w_l, yb, bz + w_l)
                p01 = to_cam(bx - w_l, yb, bz + w_l)
                q00 = to_cam(tx - w_l * 0.88, yt, tz - w_l * 0.88)
                q10 = to_cam(tx + w_l * 0.88, yt, tz - w_l * 0.88)
                q11 = to_cam(tx + w_l * 0.88, yt, tz + w_l * 0.88)
                q01 = to_cam(tx - w_l * 0.88, yt, tz + w_l * 0.88)
                add_poly([p00, p10, q10, q00], (138, 86, 42))
                add_poly([p10, p11, q11, q10], (122, 74, 34))
                add_poly([p11, p01, q01, q11], (104, 62, 28))
                add_poly([p01, p00, q00, q01], (116, 70, 32))

        # --- B. Cozy Interior Egg Coop Floor + Straw Nests + Eggs + Roosting Perches (y = door_y!) ---
        # Draw walkable wooden interior floor (visible both through open door and when standing inside!)
        y_fl = yg + door_y - 0.04
        n_seg = 12
        fl_pts = []
        for i in range(n_seg):
            ang = (i / n_seg) * math.tau
            fl_pts.append(to_cam(cx + math.cos(ang) * erx * 0.90, y_fl, cz + math.sin(ang) * erz * 0.90))
        add_poly(fl_pts, (172, 122, 68), (94, 58, 28), bias=+0.05)

        # Straw-lined hen nesting boxes along left & right interior walls + white eggs!
        for side_x in (-1.0, 1.0):
            nx_box = cx + side_x * (erx * 0.56)
            for nz_off in (-1.3, 1.1):
                nz_box = cz + nz_off
                # Wooden nest box rim + golden straw bed
                add_poly([
                    to_cam(nx_box - 0.85, y_fl + 0.04, nz_box - 0.75),
                    to_cam(nx_box + 0.85, y_fl + 0.04, nz_box - 0.75),
                    to_cam(nx_box + 0.85, y_fl + 0.55, nz_box + 0.75),
                    to_cam(nx_box - 0.85, y_fl + 0.55, nz_box + 0.75),
                ], (238, 198, 72), (168, 124, 34), bias=-0.04)
                # Little white/cream egg nestled in the straw!
                add_poly([
                    to_cam(nx_box - 0.22, y_fl + 0.36, nz_box - 0.18),
                    to_cam(nx_box + 0.22, y_fl + 0.36, nz_box - 0.18),
                    to_cam(nx_box + 0.16, y_fl + 0.72, nz_box + 0.16),
                    to_cam(nx_box - 0.16, y_fl + 0.72, nz_box + 0.16),
                ], (252, 248, 236), (190, 178, 152), bias=-0.08)

        # Back-wall wooden roosting perch bars inside the coop
        for py_off in (1.2, 2.5):
            add_poly([
                to_cam(cx - 2.6, y_fl + py_off, cz + erz * 0.56),
                to_cam(cx + 2.6, y_fl + py_off, cz + erz * 0.56),
                to_cam(cx + 2.6, y_fl + py_off + 0.22, cz + erz * 0.56),
                to_cam(cx - 2.6, y_fl + py_off + 0.22, cz + erz * 0.56),
            ], (144, 92, 44), (82, 48, 20), bias=-0.05)

        # --- C. Giant 12-Sided Egg Shell (EXTERIOR outward panels + INTERIOR inward panels!) ---
        # Front doorway is centered at angle 3*pi/2 (-Z, between segment 8 and segment 9 in 12 segments -> i==8,9)!
        egg_rings = [
            (0.00, 0.36),
            (0.14, 0.84),
            (0.36, 1.00),
            (0.64, 0.91),
            (0.86, 0.72),
            (1.00, 0.50),
        ]
        ring_cols = [
            (168, 114, 60),
            (188, 134, 74),
            (204, 150, 86),
            (194, 140, 78),
            (178, 124, 68),
        ]
        egg_h = by1 - by0
        for ri in range(len(egg_rings) - 1):
            t0, s0 = egg_rings[ri]
            t1, s1 = egg_rings[ri + 1]
            y0_r = yg + by0 + t0 * egg_h
            y1_r = yg + by0 + t1 * egg_h
            base_c = ring_cols[ri]
            for i in range(n_seg):
                # Leave ACTUAL OPEN DOORWAY GAP in front (-Z, segment 8 & 9 on ring ri==1 which spans y = 5.9..8.6m!)
                # Wait: ri==0 is 4.2..5.9m, ri==1 is 5.9..8.6m. Skip i==8 on ri==1 (front-left/center door hole)!
                # Wait: in standard trig, angle 3*pi/2 = 270 deg = 0.75 * tau -> segment i=8 (240..270) & i=9 (270..300) straddle -Z!
                # Leave BOTH narrow inner doorway half-panels open (or draw half-panels flanking +/-1.4m)!
                a0 = (i / n_seg) * math.tau
                a1 = ((i + 1) / n_seg) * math.tau
                if ri in (0, 1) and i in (8, 9):
                    # Keep tall open doorway across upper belly ring 0 (from y_door up) and ring 1!
                    for frac_a, frac_b in ([(0.0, 0.42)] if i == 8 else [(0.58, 1.0)]):
                        sa0 = a0 + frac_a * (a1 - a0)
                        sa1 = a0 + frac_b * (a1 - a0)
                        p_b0 = to_cam(cx + math.cos(sa0) * erx * s0, y0_r, cz + math.sin(sa0) * erz * s0)
                        p_b1 = to_cam(cx + math.cos(sa1) * erx * s0, y0_r, cz + math.sin(sa1) * erz * s0)
                        p_t1 = to_cam(cx + math.cos(sa1) * erx * s1, y1_r, cz + math.sin(sa1) * erz * s1)
                        p_t0 = to_cam(cx + math.cos(sa0) * erx * s1, y1_r, cz + math.sin(sa0) * erz * s1)
                        add_poly([p_b0, p_b1, p_t1, p_t0], (178, 124, 68), (92, 54, 24), cull_backface=False)
                    continue

                light = 0.82 + 0.18 * math.sin((a0 + a1) * 0.5 - 0.5)
                c_ext = (
                    min(245, int(base_c[0] * light)),
                    min(220, int(base_c[1] * light)),
                    min(165, int(base_c[2] * light)),
                )
                c_int = (
                    max(75, int(base_c[0] * 0.58)),
                    max(48, int(base_c[1] * 0.54)),
                    max(24, int(base_c[2] * 0.48)),
                )
                p_b0 = to_cam(cx + math.cos(a0) * erx * s0, y0_r, cz + math.sin(a0) * erz * s0)
                p_b1 = to_cam(cx + math.cos(a1) * erx * s0, y0_r, cz + math.sin(a1) * erz * s0)
                p_t1 = to_cam(cx + math.cos(a1) * erx * s1, y1_r, cz + math.sin(a1) * erz * s1)
                p_t0 = to_cam(cx + math.cos(a0) * erx * s1, y1_r, cz + math.sin(a0) * erz * s1)
                # Exterior face (visible from outside, automatically culls when camera walks inside!)
                add_poly([p_b0, p_b1, p_t1, p_t0], c_ext, (104, 64, 30), cull_backface=True)
                # Interior face (reversed winding -> ONLY visible through open doorway or when inside!)
                if ri >= 1:
                    add_poly([p_b1, p_b0, p_t0, p_t1], c_int, (72, 44, 22), bias=+0.08, cull_backface=True)

        # --- D. Little Gabled Terracotta-Tiled Roof Cap perched atop the Egg (人字顶瓦片!) ---
        rc_w = erx * 0.72
        rc_d = erz * 0.72
        y_eave = yg + by1 - 0.45
        y_peak = yg + roof_h
        add_poly([to_cam(cx - rc_w * 0.85, y_eave + 0.35, cz - rc_d * 0.82),
                  to_cam(cx + rc_w * 0.85, y_eave + 0.35, cz - rc_d * 0.82),
                  to_cam(cx, y_peak - 0.1, cz - rc_d * 0.82)], (186, 134, 74))
        add_poly([to_cam(cx + rc_w * 0.85, y_eave + 0.35, cz + rc_d * 0.82),
                  to_cam(cx - rc_w * 0.85, y_eave + 0.35, cz + rc_d * 0.82),
                  to_cam(cx, y_peak - 0.1, cz + rc_d * 0.82)], (152, 106, 56))
        for ci in range(3):
            ct0 = ci / 3.0
            ct1 = (ci + 1) / 3.0
            lx0 = (cx - rc_w) + ct0 * rc_w
            lx1 = (cx - rc_w) + ct1 * rc_w
            rx0 = (cx + rc_w) - ct0 * rc_w
            rx1 = (cx + rc_w) - ct1 * rc_w
            ry0 = y_eave + ct0 * (y_peak - y_eave)
            ry1 = y_eave + ct1 * (y_peak - y_eave)
            t_col_l = (204 - ci * 10, 84 - ci * 4, 50)
            t_col_r = (182 - ci * 10, 74 - ci * 4, 44)
            add_poly([to_cam(lx0, ry0, cz - rc_d), to_cam(lx0, ry0, cz + rc_d), to_cam(lx1, ry1, cz + rc_d), to_cam(lx1, ry1, cz - rc_d)], t_col_l, (112, 40, 22), bias=-0.10)
            add_poly([to_cam(rx0, ry0, cz + rc_d), to_cam(rx0, ry0, cz - rc_d), to_cam(rx1, ry1, cz - rc_d), to_cam(rx1, ry1, cz + rc_d)], t_col_r, (104, 36, 20), bias=-0.10)

        # Cozy threshold straw tuft right outside the open arched doorway
        z_front = cz - erz * 0.96
        add_poly([
            to_cam(cx - 1.35, yg + door_y - 0.05, z_front - 0.25),
            to_cam(cx + 1.35, yg + door_y - 0.05, z_front - 0.25),
            to_cam(cx + 1.15, yg + door_y + 0.18, z_front + 0.25),
            to_cam(cx - 1.15, yg + door_y + 0.18, z_front + 0.25),
        ], (238, 198, 72), (176, 134, 36), bias=-0.20)

        _draw_quad_list(screen, faces, near_z, hw, hh, focal, win_w, win_h)

        # Solid wooden doorstep landing bridging stair top cleanly into the open doorway
        _draw_box(
            screen, to_cam, cx, yg + door_y - 0.18, z_front - 0.45, 3.60, 0.28, 1.65,
            colors={"top": (184, 134, 74), "front": (148, 100, 50), "right": (140, 92, 46), "left": (132, 86, 42), "back": (122, 80, 38)},
            near_z=near_z, hw=hw, hh=hh, focal=focal, win_w=win_w, win_h=win_h,
            edge_col=(88, 54, 24),
        )

    elif kind == "coop_ladder":
        # Wide solid wooden chicken coop STAIRS (14 flat wooden steps + handrails!) climbing from grass into coop!
        coop = payload  # type: ignore[assignment]
        cx, cz = coop["cx"], coop["cz"]
        erz = coop["egg_rz"]
        door_y = coop["door_y"]
        yg = current_ground_y
        z_top = cz - erz * 0.94
        z_bot = cz - erz - 8.4
        y_top = yg + door_y - 0.05
        y_bot = yg + 0.02
        n_steps = 20
        step_d = (z_top - z_bot) / n_steps
        step_h = (y_top - y_bot) / n_steps
        for si in range(n_steps):
            sz_c = z_bot + (si + 0.5) * step_d
            sy_c = y_bot + si * step_h
            _draw_box(
                screen, to_cam, cx, sy_c, sz_c, 3.30, step_h + 0.10, step_d * 1.16,
                colors={"top": (188, 138, 78), "front": (152, 104, 52), "right": (138, 92, 46), "left": (132, 86, 42), "back": (120, 78, 38)},
                near_z=near_z, hw=hw, hh=hh, focal=focal, win_w=win_w, win_h=win_h,
                edge_col=(92, 56, 26),
            )
        # Side wooden stair stringer rails
        for rx_off in (-1.68, 1.68):
            p_b = to_cam(cx + rx_off, y_bot + 0.65, z_bot)
            p_t = to_cam(cx + rx_off, y_top + 0.65, z_top)
            if p_b[2] > near_z and p_t[2] > near_z:
                sb = (round(hw + (p_b[0] / p_b[2]) * focal), round(hh - (p_b[1] / p_b[2]) * focal))
                st = (round(hw + (p_t[0] / p_t[2]) * focal), round(hh - (p_t[1] / p_t[2]) * focal))
                w_px = max(4, int(round(0.16 * focal / max(0.8, (p_b[2] + p_t[2]) * 0.5))))
                pygame.draw.line(screen, (132, 84, 40), sb, st, w_px)

    elif kind == "pedro_barrel":
        # Pédro the Cormorant's wooden oak barrel (tonneau) at the foot of the egg stilts!
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
