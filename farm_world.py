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
    "w": 6.4,       # X width
    "d": 5.4,       # Z depth
    "wall_h": 4.0,
    "peak_h": 6.4,
}

# (cx, cz, w, d, base_y, h, yaw_rad)
HAY_BALES: list[dict[str, float]] = [
    # Cozy stacked trio right beside the chicken coop
    {"cx": -8.6, "cz": 12.2, "w": 2.2, "d": 1.6, "base_y": 0.0, "h": 1.15},
    {"cx": -8.7, "cz": 14.2, "w": 2.2, "d": 1.6, "base_y": 0.0, "h": 1.15},
    {"cx": -8.6, "cz": 13.2, "w": 2.0, "d": 1.5, "base_y": 1.15, "h": 1.08},
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

    # 1. Chicken Coop AABB + walkable roof support
    cx = CHICKEN_COOP["cx"]
    cz = CHICKEN_COOP["cz"]
    hx = CHICKEN_COOP["w"] * 0.5 + chick_radius
    hz = CHICKEN_COOP["d"] * 0.5 + chick_radius
    wall_h = CHICKEN_COOP["wall_h"]
    if abs(wx - cx) < hx and abs(wz - cz) < hz:
        if jump_y >= wall_h - 0.35:
            # Perch on roof slope!
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

    # 1. Chicken Coop
    coop_cam = to_cam(CHICKEN_COOP["cx"], current_ground_y + 1.5, CHICKEN_COOP["cz"])
    if coop_cam[2] > -5.5:
        items.append((coop_cam[2], "coop", CHICKEN_COOP))

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
    if kind == "coop":
        coop = payload  # type: ignore[assignment]
        cx, cz = coop["cx"], coop["cz"]
        w, d = coop["w"], coop["d"]
        wall_h, peak_h = coop["wall_h"], coop["peak_h"]
        hx, hz = w * 0.5, d * 0.5
        y0 = current_ground_y
        y_wall = y0 + wall_h
        y_peak = y0 + peak_h

        # Wall corners & roof ridge
        w00 = to_cam(cx - hx, y0, cz - hz)
        w10 = to_cam(cx + hx, y0, cz - hz)
        w11 = to_cam(cx + hx, y0, cz + hz)
        w01 = to_cam(cx - hx, y0, cz + hz)
        t00 = to_cam(cx - hx, y_wall, cz - hz)
        t10 = to_cam(cx + hx, y_wall, cz - hz)
        t11 = to_cam(cx + hx, y_wall, cz + hz)
        t01 = to_cam(cx - hx, y_wall, cz + hz)
        r_front = to_cam(cx, y_peak, cz - hz)
        r_back = to_cam(cx, y_peak, cz + hz)

        # Overhanging roof corners
        oh = 0.45
        rhx, rhz = hx + oh, hz + oh
        ry_eave = y_wall - 0.18
        rf_l = to_cam(cx - rhx, ry_eave, cz - rhz)
        rf_r = to_cam(cx + rhx, ry_eave, cz - rhz)
        rb_l = to_cam(cx - rhx, ry_eave, cz + rhz)
        rb_r = to_cam(cx + rhx, ry_eave, cz + rhz)
        rr_f = to_cam(cx, y_peak + 0.08, cz - rhz)
        rr_b = to_cam(cx, y_peak + 0.08, cz + rhz)

        # Arched/framed coop door on the +X side facing the meadow!
        door_x = cx + hx + 0.02
        d_z0, d_z1 = cz - 0.85, cz + 0.85
        d_y1 = y0 + 2.35
        dr0 = to_cam(door_x, y0, d_z0)
        dr1 = to_cam(door_x, y0, d_z1)
        dr2 = to_cam(door_x, d_y1, d_z1)
        dr3 = to_cam(door_x, d_y1, d_z0)

        # Also a front coop window on -Z wall facing spawn!
        win_z = cz - hz - 0.02
        wn0 = to_cam(cx - 0.85, y0 + 1.65, win_z)
        wn1 = to_cam(cx + 0.85, y0 + 1.65, win_z)
        wn2 = to_cam(cx + 0.85, y0 + 2.85, win_z)
        wn3 = to_cam(cx - 0.85, y0 + 2.85, win_z)

        # Wooden ramp leading up to coop door
        ramp0 = to_cam(cx + hx, y0 + 0.18, cz - 0.72)
        ramp1 = to_cam(cx + hx, y0 + 0.18, cz + 0.72)
        ramp2 = to_cam(cx + hx + 1.65, y0 + 0.02, cz + 0.72)
        ramp3 = to_cam(cx + hx + 1.65, y0 + 0.02, cz - 0.72)

        raw_faces = [
            ([w00, w10, t10, r_front, t00], (244, 224, 172), (176, 138, 86)),  # Front gable wall (-Z)
            ([w11, w01, t01, r_back, t11], (222, 198, 146), (160, 124, 76)),   # Back gable wall (+Z)
            ([w01, w00, t00, t01], (228, 206, 154), (166, 128, 78)),           # Left wall (-X)
            ([w10, w11, t11, t10], (250, 232, 182), (182, 144, 90)),           # Right wall (+X, yard side)
            ([rf_l, rr_f, rr_b, rb_l], (198, 58, 52), (138, 34, 30)),          # Left red roof slope
            ([rr_f, rf_r, rb_r, rr_b], (220, 68, 58), (150, 40, 34)),          # Right red roof slope
            ([dr0, dr1, dr2, dr3], (116, 72, 40), (74, 42, 20)),               # Coop door (+X)
            ([wn0, wn1, wn2, wn3], (152, 206, 236), (112, 74, 42)),            # Cozy blue window (-Z)
            ([ramp0, ramp1, ramp2, ramp3], (182, 132, 76), (124, 86, 46)),     # Wooden ramp (+X)
        ]
        faces = []
        for pts, col, ecol in raw_faces:
            if max(p[2] for p in pts) <= near_z:
                continue
            avg_d = sum(p[2] for p in pts) / len(pts)
            # Small tie-breaker so door/window/ramp draw in front of wall
            if col in ((116, 72, 40), (152, 206, 236), (182, 132, 76)):
                avg_d -= 0.12
            faces.append((avg_d, pts, col, ecol))
        _draw_quad_list(screen, faces, near_z, hw, hh, focal, win_w, win_h)

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
