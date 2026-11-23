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
from typing import Any, Callable

import pygame


# --- STATIC FARM & MEADOW LAYOUT ---

# Authentic "Les P'tites Poules / 不一样的卡梅拉" Storybook Poulailler Grégoire:
# Huge, towering rustic wooden & timber-framed Alsatian farm coop (nearly 8x taller than chicks!),
# steep two-sloped terracotta-tiled gable roof (人字顶瓦屋顶), wooden attic loft (阁楼),
# shuttered windows (fenêtre & volets), front veranda porch, exterior rung ladder (échelle),
# straw nests, and Pédro the Cormorant's wooden barrel (tonneau) at its foot!
CHICKEN_COOP = {
    "cx": -38.0,
    "cz": 42.0,
    "egg_rx": 22.0,  # Giant wooden egg radius X (~44.0m wide!)
    "egg_rz": 21.0,  # Giant wooden egg radius Z (~42.0m deep!)
    "belly_y0": 12.0,# Egg bottom starts 12m above grass on 4 towering wooden stilt legs!
    "belly_y1": 54.0,# Egg top meets terracotta pitched roof cap (39.5m ceiling height inside!)
    "roof_h": 68.0,  # Monumental 68m terracotta-tiled gable roof peak (~28.5x chick height!)
    "door_y": 14.5,  # Front arched chicken doorway & giant walkable interior floor height
    "barrel_cx": -10.5,
    "barrel_cz": 21.0,
    "barrel_r": 1.75,
    "barrel_h": 1.32,# Easy to hop right onto with any tap of J (MIN_JUMP_HEIGHT=1.40)!
}

# (cx, cz, w, d, base_y, h)
HAY_BALES: list[dict[str, float]] = [
    # Cozy stacked hay bales right beside Pédro's barrel & the giant Carmela coop (with walkable 0.55m step!)
    {"cx": -5.6, "cz": 22.8, "w": 2.3, "d": 1.9, "base_y": 0.0, "h": 0.55},
    {"cx": -3.4, "cz": 24.0, "w": 2.8, "d": 2.1, "base_y": 0.0, "h": 1.05},
    {"cx": -3.5, "cz": 26.8, "w": 2.8, "d": 2.1, "base_y": 0.0, "h": 1.05},
    {"cx": -3.4, "cz": 25.4, "w": 2.6, "d": 2.0, "base_y": 1.05, "h": 0.95},
    # Sunny meadow hay stack on the right side (with walkable 0.55m step!)
    {"cx": 26.4, "cz": 16.2, "w": 2.3, "d": 1.9, "base_y": 0.0, "h": 0.55},
    {"cx": 28.0, "cz": 17.6, "w": 2.8, "d": 2.1, "base_y": 0.0, "h": 1.05},
    {"cx": 30.6, "cz": 18.6, "w": 2.6, "d": 2.0, "base_y": 0.0, "h": 1.05},
    {"cx": 29.2, "cz": 18.1, "w": 2.5, "d": 1.9, "base_y": 1.05, "h": 0.95},
    # Single sunny bale near front-left meadow
    {"cx": -11.5, "cz": -6.0, "w": 2.6, "d": 1.9, "base_y": 0.0, "h": 1.02},
]


def _build_fence_segments() -> list[tuple[float, float, float, float]]:
    """Build ultra-far wooden paddock fence perimeter (330m x 320m) with wide south gate."""
    segs: list[tuple[float, float, float, float]] = []

    def add_chain(pts: list[tuple[float, float]]) -> None:
        for i in range(len(pts) - 1):
            segs.append((pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]))

    add_chain([
        (-12.0, -130.0),
        (-165.0, -130.0),
        (-165.0, 190.0),
        (165.0, 190.0),
        (165.0, -130.0),
        (12.0, -130.0),
    ])
    return segs


FENCE_SEGMENTS = _build_fence_segments()


def _build_fence_posts() -> list[tuple[float, float]]:
    """Sample fence posts every ~7.5m along every fence segment without duplicates."""
    posts: list[tuple[float, float]] = []
    for x1, z1, x2, z2 in FENCE_SEGMENTS:
        length = math.hypot(x2 - x1, z2 - z1)
        steps = max(1, round(length / 7.5))
        for si in range(steps + 1):
            t = si / steps
            px = x1 + (x2 - x1) * t
            pz = z1 + (z2 - z1) * t
            if not any(math.hypot(px - ox, pz - oz) < 0.25 for ox, oz in posts):
                posts.append((px, pz))
    return posts


FENCE_POSTS = _build_fence_posts()

# 18 lush tall trees framing the ultra-far 330m x 320m pasture and gigantic egg coop
FARM_TREES: list[dict[str, Any]] = [
    {"wx": -172.0, "wz": -50.0, "scale": 2.60, "seed": 1.0, "pine": True},
    {"wx": -172.0, "wz": 65.0, "scale": 2.85, "seed": 2.3, "pine": False},
    {"wx": -172.0, "wz": 150.0, "scale": 2.75, "seed": 3.1, "pine": False},
    {"wx": -95.0, "wz": 197.0, "scale": 2.80, "seed": 3.7, "pine": True},
    {"wx": 0.0, "wz": 198.0, "scale": 2.90, "seed": 4.2, "pine": False},
    {"wx": 95.0, "wz": 197.0, "scale": 2.75, "seed": 4.9, "pine": False},
    {"wx": 172.0, "wz": 115.0, "scale": 2.70, "seed": 5.4, "pine": True},
    {"wx": 172.0, "wz": -15.0, "scale": 2.55, "seed": 6.8, "pine": False},
    {"wx": -169.0, "wz": -136.0, "scale": 2.60, "seed": 7.5, "pine": False},
    {"wx": 168.0, "wz": -136.0, "scale": 2.55, "seed": 8.2, "pine": True},
    {"wx": -85.0, "wz": -65.0, "scale": 2.40, "seed": 9.1, "pine": False},
    {"wx": -110.0, "wz": 18.0, "scale": 2.50, "seed": 10.4, "pine": True},
    {"wx": 72.0, "wz": 78.0, "scale": 2.55, "seed": 11.7, "pine": False},
    {"wx": 68.0, "wz": -45.0, "scale": 2.35, "seed": 12.9, "pine": False},
    {"wx": 115.0, "wz": 140.0, "scale": 2.65, "seed": 13.5, "pine": False},
    {"wx": -118.0, "wz": 132.0, "scale": 2.75, "seed": 14.8, "pine": True},
    {"wx": 22.0, "wz": 122.0, "scale": 2.45, "seed": 15.6, "pine": False},
    {"wx": 95.0, "wz": -95.0, "scale": 2.40, "seed": 16.3, "pine": False},
]


def _build_meadow_flowers() -> list[dict[str, object]]:
    """Generate deterministic colorful flowers scattered across the ultra-far meadow."""
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
    coop_x0 = CHICKEN_COOP["cx"] - CHICKEN_COOP["egg_rx"] - 4.0
    coop_x1 = CHICKEN_COOP["cx"] + CHICKEN_COOP["egg_rx"] + 5.0
    coop_z0 = CHICKEN_COOP["cz"] - CHICKEN_COOP["egg_rz"] - 20.0
    coop_z1 = CHICKEN_COOP["cz"] + CHICKEN_COOP["egg_rz"] + 4.0

    for idx in range(300):
        wx = rng.uniform(-150.0, 150.0)
        wz = rng.uniform(-115.0, 175.0)
        if coop_x0 <= wx <= coop_x1 and coop_z0 <= wz <= coop_z1:
            continue
        if math.hypot(wx, wz + 6.0) < 3.0:
            continue
        if any(math.hypot(wx - b["cx"], wz - b["cz"]) < 2.6 for b in HAY_BALES):
            continue
        flowers.append({
            "wx": wx,
            "wz": wz,
            "color": palette[idx % len(palette)],
            "h": rng.uniform(0.38, 0.64),
            "size": 0.18 + (idx % 3) * 0.045,
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
    stair_z_bot = cz - erz - 18.0
    stair_z_top = cz - erz - 0.85  # Reaches full doorway height (14.5m) right BEFORE the egg doorway!
    if cx - 3.30 <= wx <= cx + 3.30 and stair_z_bot <= wz <= cz - erz * 0.65:
        t_st = max(0.0, min(1.0, (wz - stair_z_bot) / max(0.1, stair_z_top - stair_z_bot)))
        stair_y = t_st * door_y
        if jump_y >= stair_y - 0.95:
            support_y = max(support_y, stair_y)

    # 1c. Giant Egg Shell + Open Front Doorway + Huge Walkable Interior Egg Hall (y = door_y)!
    in_door_corridor = (abs(wx - cx) <= 3.30) and (wz < cz) and (door_y - 1.55 <= jump_y <= door_y + 9.5)
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
            wall_r = 0.88
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


def _build_coop_faces(
    coop: dict[str, float],
    to_cam: Callable[[float, float, float], tuple[float, float, float]],
    current_ground_y: float,
    near_z: float,
) -> list[tuple[float, list[tuple[float, float, float]], tuple[int, int, int], tuple[int, int, int] | None]]:
    """Build per-polygon camera-space faces for the giant Carmela Egg-on-Legs coop.

    Each polygon carries its true 3D camera depth (and floor polygons sort behind
    every chick inside the coop when viewed from floor level or above!) so multiple
    players standing inside, on the doorway, on the roof, or around the stilts
    interleave cleanly without ever getting covered by the coop floor or walls.
    """
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
        override_depth: float | None = None,
    ) -> None:
        if max(p[2] for p in pts) <= near_z:
            return
        if cull_backface and min(p[2] for p in pts) > near_z and len(pts) >= 3:
            s_pts = [((p[0] / p[2]), -(p[1] / p[2])) for p in pts]
            area2 = 0.0
            for si in range(len(s_pts)):
                ax, ay = s_pts[si]
                bx, by = s_pts[(si + 1) % len(s_pts)]
                area2 += ax * by - bx * ay
            if area2 <= 0.0:
                return
        depth = override_depth if override_depth is not None else (sum(p[2] for p in pts) / len(pts) + bias)
        faces.append((depth, pts, col, edge))

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

    # --- B. Giant Interior Egg Hall: Planked Wooden Floor, Straw Nests, Central Straw Rug, Galleries & Lantern! ---
    y_fl = yg + door_y - 0.04
    n_seg = 12
    fl_pts = []
    for i in range(n_seg):
        ang = (i / n_seg) * math.tau
        fl_pts.append(to_cam(cx + math.cos(ang) * erx * 0.92, y_fl, cz + math.sin(ang) * erz * 0.92))

    # Determine in 3D camera space whether the camera is above the coop floor (eye_y > y_fl):
    # Check upward normal (p_up - p_fl) dot (-p_fl) — actually simpler: test if camera origin (0,0,0)
    # is on the +Y side of the plane y=y_fl using world-up vector transformed into camera space!
    p_fl_c = to_cam(cx, y_fl, cz)
    p_fl_up = to_cam(cx, y_fl + 1.0, cz)
    up_cam = (p_fl_up[0] - p_fl_c[0], p_fl_up[1] - p_fl_c[1], p_fl_up[2] - p_fl_c[2])
    # Vector from floor point to camera is -p_fl_c; dot > 0 means camera is above floor level!
    cam_above_floor = (-(p_fl_c[0] * up_cam[0] + p_fl_c[1] * up_cam[1] + p_fl_c[2] * up_cam[2])) >= -0.35
    max_floor_z = max(p[2] for p in fl_pts)
    floor_base_depth = (max_floor_z + 0.35) if cam_above_floor else p_fl_c[2]

    add_poly(fl_pts, (172, 122, 68), (94, 58, 28), override_depth=floor_base_depth)

    if cam_above_floor:
        # Alternating warm oak plank strips across the 40m-wide giant floor (drawn just above floor, behind chicks!)
        for pi in range(-5, 6, 2):
            px_s = cx + pi * (erx * 0.145)
            pw_s = erx * 0.135
            pz_span = erz * 0.78 * math.sqrt(max(0.15, 1.0 - (pi * 0.145) ** 2))
            add_poly([
                to_cam(px_s - pw_s * 0.48, y_fl + 0.02, cz - pz_span),
                to_cam(px_s + pw_s * 0.48, y_fl + 0.02, cz - pz_span),
                to_cam(px_s + pw_s * 0.48, y_fl + 0.02, cz + pz_span),
                to_cam(px_s - pw_s * 0.48, y_fl + 0.02, cz + pz_span),
            ], (158, 108, 56), (112, 70, 34), override_depth=floor_base_depth - 0.02)

        # Cozy central golden straw carpet circle in the middle of the giant egg hall
        rug_pts = []
        for i in range(10):
            ang = (i / 10) * math.tau
            rug_pts.append(to_cam(cx + math.cos(ang) * 5.2, y_fl + 0.04, cz + math.sin(ang) * 5.0))
        add_poly(rug_pts, (232, 190, 68), (168, 126, 36), override_depth=floor_base_depth - 0.04)

    # Big cozy straw-lined hen nesting boxes along left & right walls + cream eggs (sorted at true depth!)
    for side_x in (-1.0, 1.0):
        nx_box = cx + side_x * (erx * 0.62)
        for nz_off in (-7.2, -2.4, 2.4, 7.2):
            nz_box = cz + nz_off
            add_poly([
                to_cam(nx_box - 2.1, y_fl + 0.05, nz_box - 1.6),
                to_cam(nx_box + 2.1, y_fl + 0.05, nz_box - 1.6),
                to_cam(nx_box + 2.1, y_fl + 1.05, nz_box + 1.6),
                to_cam(nx_box - 2.1, y_fl + 1.05, nz_box + 1.6),
            ], (238, 198, 72), (168, 124, 34), bias=+0.02)
            add_poly([
                to_cam(nx_box - 0.50, y_fl + 0.72, nz_box - 0.38),
                to_cam(nx_box + 0.50, y_fl + 0.72, nz_box - 0.38),
                to_cam(nx_box + 0.36, y_fl + 1.48, nz_box + 0.34),
                to_cam(nx_box - 0.36, y_fl + 1.48, nz_box + 0.34),
            ], (252, 248, 236), (190, 178, 152), bias=-0.02)

    # Tall multi-tier wooden roosting galleries along the back curved wall
    for py_off in (2.4, 5.2, 8.0, 11.0):
        add_poly([
            to_cam(cx - 8.5, y_fl + py_off, cz + erz * 0.64),
            to_cam(cx + 8.5, y_fl + py_off, cz + erz * 0.64),
            to_cam(cx + 8.5, y_fl + py_off + 0.45, cz + erz * 0.64),
            to_cam(cx - 8.5, y_fl + py_off + 0.45, cz + erz * 0.64),
        ], (144, 92, 44), (82, 48, 20), bias=-0.02)

    # Warm glowing golden coop lantern hanging high inside the vaulted egg ceiling!
    lan_y = y_fl + 20.0
    add_poly([
        to_cam(cx - 0.14, lan_y + 1.4, cz),
        to_cam(cx + 0.14, lan_y + 1.4, cz),
        to_cam(cx + 0.14, yg + by1 - 0.5, cz),
        to_cam(cx - 0.14, yg + by1 - 0.5, cz),
    ], (72, 64, 56), None, bias=-0.01)
    add_poly([
        to_cam(cx - 1.15, lan_y - 1.2, cz - 1.15),
        to_cam(cx + 1.15, lan_y - 1.2, cz - 1.15),
        to_cam(cx + 0.95, lan_y + 1.4, cz + 0.95),
        to_cam(cx - 0.95, lan_y + 1.4, cz + 0.95),
    ], (255, 224, 110), (188, 128, 36), bias=-0.03)

    # --- C. Giant 12-Sided Egg Shell (EXTERIOR outward panels + INTERIOR inward panels!) ---
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
            a0 = (i / n_seg) * math.tau
            a1 = ((i + 1) / n_seg) * math.tau
            if ri in (0, 1) and i in (8, 9):
                for frac_a, frac_b in ([(0.0, 0.36)] if i == 8 else [(0.64, 1.0)]):
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
            # Exterior face (automatically culls when camera walks inside!)
            add_poly([p_b0, p_b1, p_t1, p_t0], c_ext, (104, 64, 30), cull_backface=True)
            # Interior face (reversed winding -> ONLY visible through open doorway or when inside!)
            if ri >= 1:
                add_poly([p_b1, p_b0, p_t0, p_t1], c_int, (72, 44, 22), bias=+0.08, cull_backface=True)

    # --- D. Gabled Terracotta-Tiled Roof Cap perched atop the Egg (人字顶瓦片!) ---
    rc_w = erx * 0.72
    rc_d = erz * 0.72
    y_eave = yg + by1 - 0.45
    y_peak = yg + roof_h
    add_poly([
        to_cam(cx - rc_w * 0.85, y_eave + 0.35, cz - rc_d * 0.82),
        to_cam(cx + rc_w * 0.85, y_eave + 0.35, cz - rc_d * 0.82),
        to_cam(cx, y_peak - 0.1, cz - rc_d * 0.82),
    ], (186, 134, 74))
    add_poly([
        to_cam(cx + rc_w * 0.85, y_eave + 0.35, cz + rc_d * 0.82),
        to_cam(cx - rc_w * 0.85, y_eave + 0.35, cz + rc_d * 0.82),
        to_cam(cx, y_peak - 0.1, cz + rc_d * 0.82),
    ], (152, 106, 56))
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
        add_poly([to_cam(lx0, ry0, cz - rc_d), to_cam(lx0, ry0, cz + rc_d), to_cam(lx1, ry1, cz + rc_d), to_cam(lx1, ry1, cz - rc_d)], t_col_l, (112, 40, 22), bias=-0.05)
        add_poly([to_cam(rx0, ry0, cz + rc_d), to_cam(rx0, ry0, cz - rc_d), to_cam(rx1, ry1, cz - rc_d), to_cam(rx1, ry1, cz + rc_d)], t_col_r, (104, 36, 20), bias=-0.05)

    # Cozy threshold straw tuft right outside the open arched doorway (only visible from floor level or above!)
    z_front = cz - erz * 0.96
    if cam_above_floor:
        add_poly([
            to_cam(cx - 1.35, yg + door_y - 0.05, z_front - 0.25),
            to_cam(cx + 1.35, yg + door_y - 0.05, z_front - 0.25),
            to_cam(cx + 1.15, yg + door_y + 0.18, z_front + 0.25),
            to_cam(cx - 1.15, yg + door_y + 0.18, z_front + 0.25),
        ], (238, 198, 72), (176, 134, 36), override_depth=floor_base_depth - 0.06)

    # Solid wooden doorstep landing faces bridging stair top cleanly into the open doorway
    dl_x0, dl_x1 = cx - 3.30, cx + 3.30
    dl_z0, dl_z1 = (z_front - 0.75) - 1.60, (z_front - 0.75) + 1.60
    dl_y0, dl_y1 = yg + door_y - 0.26, yg + door_y + 0.16
    p000 = to_cam(dl_x0, dl_y0, dl_z0)
    p100 = to_cam(dl_x1, dl_y0, dl_z0)
    p101 = to_cam(dl_x1, dl_y0, dl_z1)
    p001 = to_cam(dl_x0, dl_y0, dl_z1)
    p010 = to_cam(dl_x0, dl_y1, dl_z0)
    p110 = to_cam(dl_x1, dl_y1, dl_z0)
    p111 = to_cam(dl_x1, dl_y1, dl_z1)
    p011 = to_cam(dl_x0, dl_y1, dl_z1)
    if cam_above_floor:
        dl_top_depth = max(p[2] for p in (p010, p110, p111, p011)) + 0.15
        add_poly([p010, p110, p111, p011], (184, 134, 74), (88, 54, 24), override_depth=dl_top_depth)
    else:
        add_poly([p000, p001, p101, p100], (118, 74, 36), (88, 54, 24))
    add_poly([p000, p100, p110, p010], (148, 100, 50), (88, 54, 24))
    add_poly([p101, p001, p011, p111], (122, 80, 38), (88, 54, 24))
    add_poly([p001, p000, p010, p011], (132, 86, 42), (88, 54, 24))
    add_poly([p100, p101, p111, p110], (140, 92, 46), (88, 54, 24))

    return faces


def collect_world_prop_draw_items(
    to_cam: Callable[[float, float, float], tuple[float, float, float]],
    current_ground_y: float,
    near_z: float,
) -> list[tuple[float, str, object]]:
    """Return distance-tagged prop items to interleave cleanly in PASS 2 with chicks."""
    items: list[tuple[float, str, object]] = []

    # 1. Giant Carmela Egg-on-Legs Coop (per-polygon true 3D depth interleaving for multiplayer!)
    _cx, _cz = CHICKEN_COOP["cx"], CHICKEN_COOP["cz"]
    _erz = CHICKEN_COOP["egg_rz"]
    c_coop = to_cam(_cx, current_ground_y + 20.0, _cz)
    if c_coop[2] > -58.0:
        for f_depth, pts_cam, fill_col, edge_col in _build_coop_faces(CHICKEN_COOP, to_cam, current_ground_y, near_z):
            items.append((f_depth, "coop_face", (pts_cam, fill_col, edge_col)))

    # 1b. Monumental 36-step Wooden Coop Stairs (per-step + segmented handrail sorting for multiplayer!)
    z_top = _cz - _erz * 0.94
    z_bot = _cz - _erz - 18.0
    y_top = current_ground_y + CHICKEN_COOP["door_y"] - 0.05
    y_bot = current_ground_y + 0.02
    n_steps = 36
    step_d = (z_top - z_bot) / n_steps
    step_h = (y_top - y_bot) / n_steps
    for si in range(n_steps):
        sz_c = z_bot + (si + 0.5) * step_d
        sy_c = y_bot + si * step_h
        sc_cam = to_cam(_cx, sy_c + step_h * 0.5, sz_c)
        if sc_cam[2] > -3.0:
            items.append((sc_cam[2], "coop_stair_step", (_cx, sy_c, sz_c, step_h + 0.14, step_d * 1.18)))
    n_rail_segs = 6
    for ri in range(n_rail_segs):
        t0, t1 = ri / n_rail_segs, (ri + 1) / n_rail_segs
        rz0, rz1 = z_bot + (z_top - z_bot) * t0, z_bot + (z_top - z_bot) * t1
        ry0, ry1 = y_bot + 0.65 + (y_top - y_bot) * t0, y_bot + 0.65 + (y_top - y_bot) * t1
        for rx_off in (-3.02, 3.02):
            p_b = to_cam(_cx + rx_off, ry0, rz0)
            p_t = to_cam(_cx + rx_off, ry1, rz1)
            if p_b[2] > near_z or p_t[2] > near_z:
                items.append(((p_b[2] + p_t[2]) * 0.5, "coop_stair_rail", (p_b, p_t)))

    c_barrel = to_cam(CHICKEN_COOP["barrel_cx"], current_ground_y + 1.25, CHICKEN_COOP["barrel_cz"])
    if c_barrel[2] > -3.5:
        items.append((c_barrel[2], "pedro_barrel", CHICKEN_COOP))

    # 2. Hay Bales
    for bale in HAY_BALES:
        bc = to_cam(bale["cx"], current_ground_y + bale["base_y"] + bale["h"] * 0.5, bale["cz"])
        if bc[2] > -2.0:
            items.append((bc[2], "hay", bale))

    # 3. Fence spans (each segment split into ~7.5m bays for accurate per-bay depth sorting!)
    for x1, z1, x2, z2 in FENCE_SEGMENTS:
        length = math.hypot(x2 - x1, z2 - z1)
        bays = max(1, round(length / 7.5))
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
    weather: str = "spring",
) -> None:
    """Render one 3D farm building or nature prop."""
    if kind == "coop_face":
        pts_cam, fill_col, edge_col = payload  # type: ignore[misc]
        scr = _clip_poly_cam(pts_cam, near_z, hw, hh, focal, win_w, win_h)
        if len(scr) >= 3:
            pygame.draw.polygon(screen, fill_col, scr)
            if edge_col is not None:
                pygame.draw.polygon(screen, edge_col, scr, 1)

    elif kind == "coop_stair_step":
        scx, sy_c, sz_c, sh, sd = payload  # type: ignore[misc]
        _draw_box(
            screen, to_cam, scx, sy_c, sz_c, 6.00, sh, sd,
            colors={"top": (188, 138, 78), "front": (152, 104, 52), "right": (138, 92, 46), "left": (132, 86, 42), "back": (120, 78, 38)},
            near_z=near_z, hw=hw, hh=hh, focal=focal, win_w=win_w, win_h=win_h,
            edge_col=(92, 56, 26),
        )

    elif kind == "coop_stair_rail":
        p_b, p_t = payload  # type: ignore[misc]
        if p_b[2] > near_z and p_t[2] > near_z:
            sb = (round(hw + (p_b[0] / p_b[2]) * focal), round(hh - (p_b[1] / p_b[2]) * focal))
            st = (round(hw + (p_t[0] / p_t[2]) * focal), round(hh - (p_t[1] / p_t[2]) * focal))
            w_px = max(4, int(round(0.16 * focal / max(0.8, (p_b[2] + p_t[2]) * 0.5))))
            pygame.draw.line(screen, (132, 84, 40), sb, st, w_px)

    elif kind == "carmela_coop":
        coop = payload  # type: ignore[assignment]
        faces = _build_coop_faces(coop, to_cam, current_ground_y, near_z)
        _draw_quad_list(screen, faces, near_z, hw, hh, focal, win_w, win_h)

    elif kind == "coop_ladder":
        coop = payload  # type: ignore[assignment]
        cx, cz = coop["cx"], coop["cz"]
        erz = coop["egg_rz"]
        door_y = coop["door_y"]
        yg = current_ground_y
        z_top = cz - erz * 0.94
        z_bot = cz - erz - 18.0
        y_top = yg + door_y - 0.05
        y_bot = yg + 0.02
        n_steps = 36
        step_d = (z_top - z_bot) / n_steps
        step_h = (y_top - y_bot) / n_steps
        for si in range(n_steps):
            sz_c = z_bot + (si + 0.5) * step_d
            sy_c = y_bot + si * step_h
            _draw_box(
                screen, to_cam, cx, sy_c, sz_c, 6.00, step_h + 0.14, step_d * 1.18,
                colors={"top": (188, 138, 78), "front": (152, 104, 52), "right": (138, 92, 46), "left": (132, 86, 42), "back": (120, 78, 38)},
                near_z=near_z, hw=hw, hh=hh, focal=focal, win_w=win_w, win_h=win_h,
                edge_col=(92, 56, 26),
            )
        for rx_off in (-3.02, 3.02):
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
        tx, tz, sc, seed = float(tree["wx"]), float(tree["wz"]), float(tree["scale"]), float(tree["seed"])
        is_pine = bool(tree.get("pine", False))
        trunk_h = (2.7 if is_pine else 3.2) * sc
        trunk_w = (0.64 if is_pine else 0.72) * sc
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
        sway = math.sin(anim_time * 1.4 + seed) * 0.08 * sc

        if is_pine:
            # Evergreen pine tree: keeps all needles year-round (with snowy caps in winter!)
            tier_specs = [
                (1.65 * sc, 3.65 * sc, 2.30 * sc, (34, 98, 48)),
                (2.75 * sc, 4.75 * sc, 1.85 * sc, (42, 114, 56)),
                (3.80 * sc, 5.75 * sc, 1.38 * sc, (50, 128, 62)),
                (4.75 * sc, 6.75 * sc, 0.90 * sc, (62, 144, 72)),
            ]
            pine_faces = []
            n_cone = 6
            for ti_idx, (y_bot, y_top, rad, base_col) in enumerate(tier_specs):
                tip_cam = to_cam(tx + sway * (0.4 + 0.2 * ti_idx), current_ground_y + y_top, tz)
                for si in range(n_cone):
                    a0 = (si / n_cone) * math.tau + seed * 0.3
                    a1 = ((si + 1) / n_cone) * math.tau + seed * 0.3
                    p0 = to_cam(tx + math.cos(a0) * rad + sway * 0.3, current_ground_y + y_bot, tz + math.sin(a0) * rad)
                    p1 = to_cam(tx + math.cos(a1) * rad + sway * 0.3, current_ground_y + y_bot, tz + math.sin(a1) * rad)
                    if max(p0[2], p1[2], tip_cam[2]) > near_z:
                        shade = 0.85 + 0.18 * math.sin((a0 + a1) * 0.5)
                        f_col = (
                            min(255, int(base_col[0] * shade)),
                            min(255, int(base_col[1] * shade)),
                            min(255, int(base_col[2] * shade)),
                        )
                        zc_avg = (p0[2] + p1[2] + tip_cam[2]) / 3.0
                        pine_faces.append((zc_avg, [p0, p1, tip_cam], f_col, (24, 68, 34)))
                        if weather == "winter":
                            # Snow-frosted upper ridge cap on evergreen pine boughs
                            sm0 = (
                                p0[0] * 0.35 + tip_cam[0] * 0.65,
                                p0[1] * 0.35 + tip_cam[1] * 0.65,
                                p0[2] * 0.35 + tip_cam[2] * 0.65,
                            )
                            sm1 = (
                                p1[0] * 0.35 + tip_cam[0] * 0.65,
                                p1[1] * 0.35 + tip_cam[1] * 0.65,
                                p1[2] * 0.35 + tip_cam[2] * 0.65,
                            )
                            pine_faces.append((zc_avg - 0.03, [sm0, sm1, tip_cam], (238, 246, 255), None))
            _draw_quad_list(screen, pine_faces, near_z, hw, hh, focal, win_w, win_h)
            return

        # Non-pine deciduous trees: draw bare wooden branches in fall & winter (winter loses ALL leaves!)
        if weather in ("fall", "winter"):
            branch_specs = [
                (0.0, trunk_h * 0.78, 0.0, -1.65 * sc + sway * 0.5, trunk_h + 1.55 * sc, -0.60 * sc),
                (0.0, trunk_h * 0.84, 0.0, 1.72 * sc + sway * 0.5, trunk_h + 1.68 * sc, 0.55 * sc),
                (0.0, trunk_h * 0.88, 0.0, -0.55 * sc + sway * 0.6, trunk_h + 1.95 * sc, 1.35 * sc),
                (0.0, trunk_h * 0.90, 0.0, 0.45 * sc + sway * 0.6, trunk_h + 2.05 * sc, -1.25 * sc),
                (0.0, trunk_h * 0.94, 0.0, 0.12 * sc + sway * 0.8, trunk_h + 2.45 * sc, 0.08 * sc),
                (-0.95 * sc + sway * 0.3, trunk_h + 0.95 * sc, -0.35 * sc, -2.05 * sc + sway * 0.6, trunk_h + 1.90 * sc, -1.05 * sc),
                (1.00 * sc + sway * 0.3, trunk_h + 1.05 * sc, 0.32 * sc, 2.10 * sc + sway * 0.6, trunk_h + 2.05 * sc, 0.95 * sc),
            ]
            br_col = (104, 72, 44) if weather == "winter" else (112, 74, 40)
            for x0, y0, z0, x1, y1, z1 in branch_specs:
                p0 = to_cam(tx + x0, current_ground_y + y0, tz + z0)
                p1 = to_cam(tx + x1, current_ground_y + y1, tz + z1)
                if p0[2] > near_z and p1[2] > near_z:
                    s0 = (round(hw + (p0[0] / p0[2]) * focal), round(hh - (p0[1] / p0[2]) * focal))
                    s1 = (round(hw + (p1[0] / p1[2]) * focal), round(hh - (p1[1] / p1[2]) * focal))
                    bw = max(2, round((0.20 * sc / max(1.0, (p0[2] + p1[2]) * 0.5)) * focal))
                    pygame.draw.line(screen, br_col, s0, s1, bw)
                    if weather == "winter":
                        pygame.draw.line(screen, (230, 240, 250), (s0[0], s0[1] - 1), (s1[0], s1[1] - 1), max(1, bw // 3))

        if weather == "winter":
            # Non-pine trees lose ALL of their leaves in winter!
            return

        if weather == "fall":
            _fvar = int(abs(seed)) % 3
            if _fvar == 0:
                canopy_pal = [(192, 72, 42), (212, 90, 48), (228, 114, 54)]
            elif _fvar == 1:
                canopy_pal = [(206, 118, 38), (226, 140, 46), (242, 168, 60)]
            else:
                canopy_pal = [(196, 148, 42), (218, 172, 52), (238, 198, 66)]
            # Fewer, smaller sparse autumn leaves remaining on the tree!
            lobes = [
                (-1.25 * sc + sway, trunk_h + 1.35 * sc, -0.50 * sc, 1.05 * sc, canopy_pal[0]),
                (1.15 * sc + sway, trunk_h + 1.48 * sc, 0.52 * sc, 0.98 * sc, canopy_pal[1]),
                (0.10 * sc + sway * 1.1, trunk_h + 2.25 * sc, -0.15 * sc, 1.08 * sc, canopy_pal[2]),
            ]
        elif weather == "summer":
            canopy_pal = [
                (44, 134, 46), (54, 150, 52), (62, 160, 58),
                (48, 142, 48), (68, 168, 62), (86, 184, 72),
            ]
            lobes = [
                (0.0 + sway, trunk_h + 1.25 * sc, 0.0, 2.35 * sc, canopy_pal[0]),
                (-1.15 * sc + sway, trunk_h + 0.75 * sc, -0.55 * sc, 1.65 * sc, canopy_pal[1]),
                (1.18 * sc + sway, trunk_h + 0.80 * sc, 0.45 * sc, 1.68 * sc, canopy_pal[2]),
                (-0.45 * sc + sway, trunk_h + 0.90 * sc, 1.05 * sc, 1.60 * sc, canopy_pal[3]),
                (0.35 * sc + sway, trunk_h + 1.05 * sc, -1.05 * sc, 1.58 * sc, canopy_pal[4]),
                (0.05 * sc + sway * 1.2, trunk_h + 2.25 * sc, 0.05 * sc, 1.55 * sc, canopy_pal[5]),
            ]
        else:
            # Spring: fresh bright green + pink cherry-blossom trees!
            if int(abs(seed)) % 4 == 0:
                canopy_pal = [
                    (236, 162, 190), (244, 178, 204), (248, 192, 214),
                    (238, 168, 196), (252, 204, 222), (255, 224, 236),
                ]
            else:
                canopy_pal = [
                    (64, 146, 56), (74, 162, 62), (80, 170, 66),
                    (68, 154, 58), (84, 176, 68), (104, 194, 78),
                ]
            lobes = [
                (0.0 + sway, trunk_h + 1.25 * sc, 0.0, 2.35 * sc, canopy_pal[0]),
                (-1.15 * sc + sway, trunk_h + 0.75 * sc, -0.55 * sc, 1.65 * sc, canopy_pal[1]),
                (1.18 * sc + sway, trunk_h + 0.80 * sc, 0.45 * sc, 1.68 * sc, canopy_pal[2]),
                (-0.45 * sc + sway, trunk_h + 0.90 * sc, 1.05 * sc, 1.60 * sc, canopy_pal[3]),
                (0.35 * sc + sway, trunk_h + 1.05 * sc, -1.05 * sc, 1.58 * sc, canopy_pal[4]),
                (0.05 * sc + sway * 1.2, trunk_h + 2.25 * sc, 0.05 * sc, 1.55 * sc, canopy_pal[5]),
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
                hi_col = (min(255, col[0] + 20), min(255, col[1] + 22), min(255, col[2] + 14))
                pygame.draw.circle(screen, hi_col, (sx - max(1, sr // 5), sy - max(1, sr // 5)), max(2, round(sr * 0.58)))

    elif kind == "flower":
        if weather == "winter":
            return
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
            stem_col = (146, 134, 64) if weather == "fall" else (62, 146, 52)
            pygame.draw.line(screen, stem_col, (bx, by), (tx, ty), 2)
            pr = max(3, round((fsize / c_top[2]) * focal))
            col = fl["color"]  # type: ignore[assignment]
            for pi in range(5):
                pang = (2.0 * math.pi * pi) / 5.0 + float(fl["phase"])
                px = tx + round(math.cos(pang) * pr * 0.72)
                py = ty + round(math.sin(pang) * pr * 0.72)
                pygame.draw.circle(screen, col, (px, py), max(2, round(pr * 0.62)))
            pygame.draw.circle(screen, (255, 212, 54), (tx, ty), max(2, round(pr * 0.48)))
