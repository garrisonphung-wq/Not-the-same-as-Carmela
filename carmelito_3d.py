"""
carmelito_3d.py
Faithful real-time 3D Polygonal Mesh Renderer for Carmelito (卡梅利多).
Modeled meticulously to match the official illustrations from Christian Jolibois & Christian Heinrich:
1. Expressive round head with prominent red 4-scalloped crown crest.
2. Large white cartoon eyes with cute, small/medium dark pupils (not oversized) + smooth blinking.
3. Wide, short, blunt, rounded, bulbous duck/banana beak curving downward with a warm smile crease.
4. SMOOTH LOCOMOTION BLENDING:
   - Standing: Relaxed arms hanging downward along torso, legs straight.
   - Walking: Gentle stroll stride with relaxed gentle arm pendulum swing.
   - Running: Athletic sprint with 90-degree bent elbow pump, high knee bend and push-off.
   - Smooth interpolation between standing, walking, and running without snapping!
5. Slender yellow chicken legs permanently rooted inside lower body drumstick cuffs (never detach).
6. Storybook ink contour linework to match the hand-drawn picture-book aesthetic.
"""

from __future__ import annotations
import math
import pygame


# Authentic Storybook Palette sampled directly from the illustrations:
COLOR_BODY_PINK = (218, 96, 108)        # Carmelito's strawberry-magenta pink
COLOR_COMB_RED = (200, 48, 42)          # Deep rooster red comb
COLOR_BEAK_YELLOW = (238, 185, 65)      # Warm storybook beak yellow
COLOR_MOUTH_DARK = (88, 20, 25)         # Deep mouth interior cavity
COLOR_TONGUE_PINK = (235, 112, 128)     # Cute inner mouth tongue
COLOR_EYE_WHITE = (255, 255, 255)       # Bright cartoon eye white
COLOR_PUPIL_DARK = (20, 12, 14)         # Rich dark cartoon pupil
COLOR_LEG_YELLOW = (225, 172, 52)       # Chicken leg yellow
COLOR_INK_LINE = (68, 24, 28)           # Hand-drawn ink outline

# Carmen (卡门) Palette - Carmelito's little yellow sister:
COLOR_CARMEN_YELLOW = (252, 214, 66)    # Carmen's fluffy sunny-golden yellow down feathers
COLOR_CARMEN_COMB = (215, 48, 45)       # Carmen's cute little red chick comb
COLOR_CARMEN_BEAK = (248, 156, 38)      # Carmen's warm orange-yellow beak
COLOR_CARMEN_LEG = (238, 148, 35)       # Carmen's slender orange-yellow legs
COLOR_CARMEN_INK = (72, 44, 18)         # Warm storybook brown-ink outline

# Belino / Coquenpâte (小胖墩) Palette - Fat white rooster rival:
COLOR_PANGDUN_WHITE = (246, 247, 252)   # Plump white down feathers
COLOR_PANGDUN_COMB = (222, 38, 34)      # Bright prominent rooster comb
COLOR_PANGDUN_BEAK = (242, 168, 40)     # Sturdy orange-yellow beak
COLOR_PANGDUN_LEG = (235, 152, 36)      # Chunky yellow-orange legs
COLOR_PANGDUN_INK = (42, 40, 52)        # Sharp comic ink outline

# Xiaoliuzi / Coqsix (小六子) Palette - Tall, lean adolescent off-white/cream cockerel:
COLOR_XIAOLIUZI_TAN = (246, 240, 224)    # Off-white / warm cream cockerel plumage
COLOR_XIAOLIUZI_BELLY = (224, 216, 200)  # Subtle pale gray-beige watercolor shading under belly & wings
COLOR_XIAOLIUZI_ACCENT = (228, 220, 206) # Soft pale gray-beige shading on tail tuft
COLOR_XIAOLIUZI_COMB = (218, 36, 42)     # Bright crimson-red jagged flopping comb & dangling wattles
COLOR_XIAOLIUZI_BEAK = (246, 166, 36)    # Bright yellow-orange pointed beak
COLOR_XIAOLIUZI_LEG = (244, 162, 34)     # Skinny stick-like yellow-orange bird legs
COLOR_XIAOLIUZI_CLAW = (132, 92, 48)     # Dark clawed tips on three-toed feet
COLOR_XIAOLIUZI_INK = (34, 30, 32)       # Loose expressive storybook black ink outline


def create_cube_grid(
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    subdivisions: tuple[int, int, int],
    base_color: tuple[int, int, int],
    taper_y: float = 0.0,
    taper_z: float = 0.0,
    roundness: float = 0.0,
    draw_contour: bool = True,
) -> list[tuple[list[tuple[float, float, float]], tuple[int, int, int], bool]]:
    """
    Creates a polygonal 3D mesh block with subdivision, tapering, and spherical blending.
    Returns a list of faces: (vertex_list, fill_color, draw_contour).
    """
    cx, cy, cz = center
    sx, sy, sz = size
    div_x, div_y, div_z = subdivisions

    faces = []

    def get_vertex(gx: float, gy: float, gz: float) -> tuple[float, float, float]:
        t_y = (gy + 1.0) * 0.5  # 0 at bottom, 1 at top
        taper_x = 1.0 - taper_y * (1.0 - t_y)

        t_z = (gz + 1.0) * 0.5  # 0 at back, 1 at front
        taper_tip = 1.0 - taper_z * t_z

        vx = gx * (sx * 0.5) * taper_x * taper_tip
        vy = gy * (sy * 0.5) * taper_tip
        vz = gz * (sz * 0.5)

        if roundness > 0:
            length = math.sqrt(vx * vx + vy * vy + vz * vz)
            if length > 1e-4:
                max_rad = max(sx, sy, sz) * 0.5
                rx = (vx / length) * max_rad
                ry = (vy / length) * max_rad
                rz = (vz / length) * max_rad
                vx = vx * (1.0 - roundness) + rx * roundness
                vy = vy * (1.0 - roundness) + ry * roundness
                vz = vz * (1.0 - roundness) + rz * roundness

        return (cx + vx, cy + vy, cz + vz)

    # 1. Front (+Z) & Back (-Z)
    for iz in (1, -1):
        gz = float(iz)
        for iy in range(div_y):
            y0 = -1.0 + 2.0 * iy / div_y
            y1 = -1.0 + 2.0 * (iy + 1) / div_y
            for ix in range(div_x):
                x0 = -1.0 + 2.0 * ix / div_x
                x1 = -1.0 + 2.0 * (ix + 1) / div_x
                if iz > 0:
                    quad = [get_vertex(x0, y0, gz), get_vertex(x1, y0, gz), get_vertex(x1, y1, gz), get_vertex(x0, y1, gz)]
                else:
                    quad = [get_vertex(x1, y0, gz), get_vertex(x0, y0, gz), get_vertex(x0, y1, gz), get_vertex(x1, y1, gz)]
                faces.append((quad, base_color, draw_contour))

    # 2. Left (-X) & Right (+X)
    for ix in (1, -1):
        gx = float(ix)
        for iy in range(div_y):
            y0 = -1.0 + 2.0 * iy / div_y
            y1 = -1.0 + 2.0 * (iy + 1) / div_y
            for iz in range(div_z):
                z0 = -1.0 + 2.0 * iz / div_z
                z1 = -1.0 + 2.0 * (iz + 1) / div_z
                if ix > 0:
                    quad = [get_vertex(gx, y0, z1), get_vertex(gx, y0, z0), get_vertex(gx, y1, z0), get_vertex(gx, y1, z1)]
                else:
                    quad = [get_vertex(gx, y0, z0), get_vertex(gx, y0, z1), get_vertex(gx, y1, z1), get_vertex(gx, y1, z0)]
                faces.append((quad, base_color, draw_contour))

    # 3. Top (+Y) & Bottom (-Y)
    for iy in (1, -1):
        gy = float(iy)
        for iz in range(div_z):
            z0 = -1.0 + 2.0 * iz / div_z
            z1 = -1.0 + 2.0 * (iz + 1) / div_z
            for ix in range(div_x):
                x0 = -1.0 + 2.0 * ix / div_x
                x1 = -1.0 + 2.0 * (ix + 1) / div_x
                if iy > 0:
                    quad = [get_vertex(x0, gy, z1), get_vertex(x1, gy, z1), get_vertex(x1, gy, z0), get_vertex(x0, gy, z0)]
                else:
                    quad = [get_vertex(x0, gy, z0), get_vertex(x1, gy, z0), get_vertex(x1, gy, z1), get_vertex(x0, gy, z1)]
                faces.append((quad, base_color, draw_contour))

    return faces


def create_oriented_box(
    p0: tuple[float, float, float],
    p1: tuple[float, float, float],
    thickness: tuple[float, float],
    base_color: tuple[int, int, int],
    subdiv_length: int = 2,
    draw_contour: bool = True,
) -> list[tuple[list[tuple[float, float, float]], tuple[int, int, int], bool]]:
    """
    Creates an oriented 3D box segment running between point p0 and point p1.
    thickness is (width_u, width_v).
    """
    x0, y0, z0 = p0
    x1, y1, z1 = p1
    dx = x1 - x0
    dy = y1 - y0
    dz = z1 - z0
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length < 1e-4:
        return []

    # Axis along segment:
    ax = (dx / length, dy / length, dz / length)

    # Find perpendicular vector:
    ref = (0.0, 1.0, 0.0) if abs(ax[1]) < 0.9 else (1.0, 0.0, 0.0)
    p1x = ax[1] * ref[2] - ax[2] * ref[1]
    p1y = ax[2] * ref[0] - ax[0] * ref[2]
    p1z = ax[0] * ref[1] - ax[1] * ref[0]
    m1 = math.sqrt(p1x * p1x + p1y * p1y + p1z * p1z)
    u = (p1x / m1, p1y / m1, p1z / m1)

    v = (
        ax[1] * u[2] - ax[2] * u[1],
        ax[2] * u[0] - ax[0] * u[2],
        ax[0] * u[1] - ax[1] * u[0],
    )

    w_u = thickness[0] * 0.5
    w_v = thickness[1] * 0.5

    faces = []
    corners = [(1, 1), (-1, 1), (-1, -1), (1, -1)]

    for step in range(subdiv_length):
        t_a = step / subdiv_length
        t_b = (step + 1) / subdiv_length

        cA = (x0 + dx * t_a, y0 + dy * t_a, z0 + dz * t_a)
        cB = (x0 + dx * t_b, y0 + dy * t_b, z0 + dz * t_b)

        pts_A = [
            (cA[0] + cu * w_u * u[0] + cv * w_v * v[0],
             cA[1] + cu * w_u * u[1] + cv * w_v * v[1],
             cA[2] + cu * w_u * u[2] + cv * w_v * v[2])
            for cu, cv in corners
        ]
        pts_B = [
            (cB[0] + cu * w_u * u[0] + cv * w_v * v[0],
             cB[1] + cu * w_u * u[1] + cv * w_v * v[1],
             cB[2] + cu * w_u * u[2] + cv * w_v * v[2])
            for cu, cv in corners
        ]

        for i in range(4):
            nxt = (i + 1) % 4
            quad = [pts_A[i], pts_A[nxt], pts_B[nxt], pts_B[i]]
            faces.append((quad, base_color, draw_contour))

    quad_start = [
        (x0 + cu * w_u * u[0] + cv * w_v * v[0],
         y0 + cu * w_u * u[1] + cv * w_v * v[1],
         z0 + cu * w_u * u[2] + cv * w_v * v[2])
        for cu, cv in [(1, -1), (-1, -1), (-1, 1), (1, 1)]
    ]
    faces.append((quad_start, base_color, draw_contour))

    quad_end = [
        (x1 + cu * w_u * u[0] + cv * w_v * v[0],
         y1 + cu * w_u * u[1] + cv * w_v * v[1],
         z1 + cu * w_u * u[2] + cv * w_v * v[2])
        for cu, cv in [(1, 1), (-1, 1), (-1, -1), (1, -1)]
    ]
    faces.append((quad_end, base_color, draw_contour))

    return faces


def lerp_vec3(a: tuple[float, float, float], b: tuple[float, float, float], t: float) -> tuple[float, float, float]:
    return (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


def rotate_faces_x(
    faces: list[tuple[list[tuple[float, float, float]], tuple[int, int, int], bool]],
    pivot_y: float,
    pivot_z: float,
    angle: float,
) -> list[tuple[list[tuple[float, float, float]], tuple[int, int, int], bool]]:
    """Rotates face vertices around an X axis passing through (pivot_y, pivot_z)."""
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    rotated = []
    for quad_verts, col, has_contour in faces:
        nq = []
        for vx, vy, vz in quad_verts:
            dy = vy - pivot_y
            dz = vz - pivot_z
            ry = dy * cos_a - dz * sin_a
            rz = dy * sin_a + dz * cos_a
            nq.append((vx, pivot_y + ry, pivot_z + rz))
        rotated.append((nq, col, has_contour))
    return rotated


class Carmelito3D:
    def __init__(self) -> None:
        self.light_dir = self._normalize((0.35, 0.85, -0.4))

    @staticmethod
    def _normalize(v: tuple[float, float, float]) -> tuple[float, float, float]:
        mag = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
        if mag < 1e-6:
            return (0.0, 1.0, 0.0)
        return (v[0] / mag, v[1] / mag, v[2] / mag)

    @staticmethod
    def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
        return (
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        )

    @staticmethod
    def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    def build_model_faces(
        self,
        mouth_open: bool = False,
        run_cycle: float = 0.0,
        is_running: bool = False,
        run_weight: float | None = None,
        is_walking: bool = False,
        walk_weight: float = 0.0,
        head_yaw: float = 0.0,
        head_pitch: float = 0.0,
        blink: float = 0.0,
        character: str = "carmelito",
        kick_amount: float = 0.0,
        kick_side: float = 1.0,
        punch_amount: float = 0.0,
        punch_side: float = 1.0,
        jump_amount: float = 0.0,
        arms_down_amount: float = 0.0,
        tag_amount: float = 0.0,
        sit_amount: float = 0.0,
        touch_ground_amount: float = 0.0,
        ragdoll: float = 0.0,
        ragdoll_seed: float = 0.0,
        ragdoll_pose: dict | None = None,
    ) -> list[tuple[list[tuple[float, float, float]], tuple[int, int, int], bool]]:
        """
        Builds Carmelito 3D model with 100% faithful storybook geometry:
        - Slender pear chick body (trim, upright, NOT fat)
        - Big cartoon eyes with cute, small/medium dark pupils (not oversized) + blink
        - Wide, short, blunt, rounded banana beak
        - DISTINCT WALKING & RUNNING ANIMATIONS:
          * Walking: Natural relaxed stride, gentle arm pendulum swing, mild knee flex.
          * Running: Athletic sprint with 90° bent elbow pump, high knee bend and push-off.
          * Standing: Fully relaxed arms and straight posture.
        - 4-lobe red crown comb.
        """
        # Pick palette and proportions according to character
        char_lower = character.lower()
        is_carmen = (char_lower in ("carmen", "卡门"))
        is_pangdun = (char_lower in ("pangdun", "小胖墩", "belino", "coquenpate"))
        is_xiaoliuzi = (char_lower in ("xiaoliuzi", "小六子", "coqsix", "克西斯"))

        if is_carmen:
            body_col = COLOR_CARMEN_YELLOW
            belly_col = COLOR_CARMEN_YELLOW
            comb_col = COLOR_CARMEN_COMB
            beak_col = COLOR_CARMEN_BEAK
            leg_col = COLOR_CARMEN_LEG
            accent_col = COLOR_CARMEN_YELLOW
            ink_col = COLOR_CARMEN_INK
        elif is_pangdun:
            body_col = COLOR_PANGDUN_WHITE
            belly_col = COLOR_PANGDUN_WHITE
            comb_col = COLOR_PANGDUN_COMB
            beak_col = COLOR_PANGDUN_BEAK
            leg_col = COLOR_PANGDUN_LEG
            accent_col = COLOR_PANGDUN_WHITE
            ink_col = COLOR_PANGDUN_INK
        elif is_xiaoliuzi:
            body_col = COLOR_XIAOLIUZI_TAN
            belly_col = COLOR_XIAOLIUZI_BELLY
            comb_col = COLOR_XIAOLIUZI_COMB
            beak_col = COLOR_XIAOLIUZI_BEAK
            leg_col = COLOR_XIAOLIUZI_LEG
            accent_col = COLOR_XIAOLIUZI_ACCENT
            ink_col = COLOR_XIAOLIUZI_INK
        else:
            body_col = COLOR_BODY_PINK
            belly_col = COLOR_BODY_PINK
            comb_col = COLOR_COMB_RED
            beak_col = COLOR_BEAK_YELLOW
            leg_col = COLOR_LEG_YELLOW
            accent_col = COLOR_BODY_PINK
            ink_col = COLOR_INK_LINE

        # Proportions for characters:
        # 小胖墩: plump round body with head completely connected to torso
        # 小六子 (Coqsix): leaner, taller adolescent young rooster with pear-shaped torso & thin neck
        head_s = 0.94 if is_pangdun else (0.94 if is_xiaoliuzi else 1.0)
        body_w = 1.58 if is_pangdun else (0.88 if is_xiaoliuzi else 1.0)
        body_h = 1.25 if is_pangdun else (1.10 if is_xiaoliuzi else 1.0)
        body_d = 1.50 if is_pangdun else (0.90 if is_xiaoliuzi else 1.0)

        if run_weight is None:
            rw = 1.0 if is_running else 0.0
        else:
            rw = max(0.0, min(1.0, run_weight))

        ww = max(0.0, min(1.0, walk_weight))
        blink_amt = max(0.0, min(1.0, blink))
        # Effective locomotion weights:
        loco_weight = max(rw, ww)

        all_faces = []
        head_faces = []

        # Running has higher bob and faster/larger swing; walking has softer cadence
        run_swing = math.sin(run_cycle * 2.0 * math.pi)
        run_bob = abs(math.sin(run_cycle * 2.0 * math.pi)) * 0.09

        walk_swing = math.sin(run_cycle * 2.0 * math.pi)
        walk_bob = abs(math.sin(run_cycle * 2.0 * math.pi)) * 0.04

        sa = max(0.0, min(1.0, sit_amount))
        tg = max(0.0, min(1.0, touch_ground_amount))

        # Blended bob + sit drop + gentle touch-grass lean drop
        bob_y = (run_bob * rw + walk_bob * (ww * (1.0 - rw))) * (1.0 - sa) - (0.38 * sa) - (0.09 * tg * (1.0 - sa))

        # --- 1. HEAD & NECK (Trim for Carmelito/Carmen; seamlessly merged for 小胖墩) ---
        head_center_y = (1.46 if is_pangdun else (1.64 if is_xiaoliuzi else 1.56)) + bob_y
        # Head cube: for Belino, lower taper flares outward directly into the shoulders/torso
        head = create_cube_grid(
            center=(0.0, head_center_y, 0.0),
            size=(0.62 if is_pangdun else 0.58, 0.58, 0.60 if is_pangdun else 0.58),
            subdivisions=(7, 6, 6),
            base_color=body_col,
            taper_y=-0.12 if is_pangdun else 0.15,
            roundness=0.78,
            draw_contour=True,
        )
        head_faces.extend(head)

        # Cheeks / Jowls:
        for side in (-1, 1):
            cheek = create_cube_grid(
                center=(side * (0.24 if is_pangdun else 0.20), head_center_y - 0.10, 0.10),
                size=(0.24 if is_pangdun else 0.20, 0.20 if is_pangdun else 0.18, 0.22 if is_pangdun else 0.20),
                subdivisions=(3, 3, 3),
                base_color=body_col,
                roundness=0.75,
                draw_contour=False,
            )
            head_faces.extend(cheek)

        # Solid connection between bottom of head and body:
        # For Belino, the entire bottom of the head is fully merged into the torso with no slender neck gap!
        if is_pangdun:
            # Broad, solid collar connecting the entire perimeter of the head bottom into the body
            neck = create_cube_grid(
                center=(0.0, head_center_y - 0.22, 0.0),
                size=(0.68, 0.32, 0.66),
                subdivisions=(6, 4, 6),
                base_color=body_col,
                taper_y=-0.18,
                roundness=0.76,
                draw_contour=False,
            )
            head_faces.extend(neck)
            # Front throat / double-chin bridge
            chin_bridge = create_cube_grid(
                center=(0.0, head_center_y - 0.25, 0.15),
                size=(0.52, 0.26, 0.34),
                subdivisions=(4, 3, 3),
                base_color=body_col,
                roundness=0.78,
                draw_contour=False,
            )
            head_faces.extend(chin_bridge)
        elif is_xiaoliuzi:
            # Noticeably thin adolescent cockerel neck connecting head to pear-shaped torso
            neck = create_cube_grid(
                center=(0.0, head_center_y - 0.30, -0.02),
                size=(0.30, 0.36, 0.30),
                subdivisions=(4, 4, 4),
                base_color=body_col,
                roundness=0.62,
                draw_contour=True,
            )
            head_faces.extend(neck)
        else:
            # Slender neck for Carmelito & Carmen
            neck = create_cube_grid(
                center=(0.0, head_center_y - 0.28, -0.02),
                size=(0.42, 0.26, 0.42),
                subdivisions=(5, 3, 5),
                base_color=body_col,
                roundness=0.6,
                draw_contour=False,
            )
            head_faces.extend(neck)

        # --- 2. COMB / CREST (Red rooster comb on top of head) ---
        # Belino's red comb is distinctly shorter; 小六子 (Coqsix) has a spiky, jaunty 5-point crest!
        comb_h_mult = 0.52 if is_pangdun else 1.0
        comb_y_shift = -0.05 if is_pangdun else 0.0
        comb_y = head_center_y + 0.29 + comb_y_shift

        if is_xiaoliuzi:
            # Bright crimson-red jagged rooster comb flopping slightly to the side!
            spike_specs = [
                ((0.00, -0.03, 0.16), (0.11, 0.18, 0.23), (0.075, 0.048), comb_col),
                ((0.01, -0.01, 0.06), (0.15, 0.26, 0.10), (0.082, 0.052), comb_col),
                ((0.01, -0.01, -0.04), (0.14, 0.24, -0.06), (0.082, 0.052), comb_col),
                ((0.00, -0.03, -0.13), (0.11, 0.18, -0.20), (0.075, 0.048), comb_col),
                ((0.00, -0.07, -0.21), (0.07, 0.10, -0.29), (0.065, 0.044), comb_col),
            ]
            for (bx, by, bz), (tx, ty, tz), thick, c_col in spike_specs:
                head_faces.extend(
                    create_oriented_box(
                        (bx, comb_y + by, bz),
                        (tx, comb_y + ty, tz),
                        thickness=thick,
                        base_color=c_col,
                        subdiv_length=2,
                        draw_contour=True,
                    )
                )
            # Small comb base ridge anchoring the flopping comb into the skull
            head_faces.extend(
                create_cube_grid(
                    center=(0.015, comb_y - 0.02, -0.03),
                    size=(0.095, 0.085, 0.36),
                    subdivisions=(2, 2, 4),
                    base_color=comb_col,
                    roundness=0.45,
                    draw_contour=True,
                )
            )
            # Two small dangling crimson-red wattles under his chin!
            for w_side in (-1, 1):
                wattle = create_cube_grid(
                    center=(w_side * 0.065, head_center_y - 0.275, 0.22),
                    size=(0.065, 0.125, 0.065),
                    subdivisions=(2, 3, 2),
                    base_color=comb_col,
                    taper_y=-0.25,
                    roundness=0.72,
                    draw_contour=True,
                )
                head_faces.extend(wattle)
        else:
            lobe_data = [
                ((0.0, 0.12 * comb_h_mult, 0.10), (0.13, 0.30 * comb_h_mult, 0.16), (2, 4, 3)),   # Lobe 1
                ((0.0, 0.08 * comb_h_mult, -0.01), (0.13, 0.28 * comb_h_mult, 0.16), (2, 4, 3)),  # Lobe 2
                ((0.0, 0.03 * comb_h_mult, -0.12), (0.12, 0.24 * comb_h_mult, 0.15), (2, 3, 3)),  # Lobe 3
                ((0.0, -0.04 * comb_h_mult, -0.21), (0.11, 0.18 * comb_h_mult, 0.13), (2, 3, 3)), # Lobe 4
            ]
            for (dx, dy, dz), (lsx, lsy, lsz), ldiv in lobe_data:
                lobe = create_cube_grid(
                    center=(dx, comb_y + dy, dz),
                    size=(lsx, lsy, lsz),
                    subdivisions=ldiv,
                    base_color=comb_col,
                    taper_y=-0.2,
                    roundness=0.65,
                    draw_contour=True,
                )
                head_faces.extend(lobe)

        # --- 3. EYES & PUPILS (Big white eyes with cute dark pupils + smooth blink) ---
        eye_y = head_center_y + (0.13 if is_xiaoliuzi else 0.11)
        eye_spacing = 0.098 if is_xiaoliuzi else 0.13
        eye_w = 0.185 if is_xiaoliuzi else 0.20
        for eye_side in (-1, 1):
            ex = eye_side * eye_spacing
            if blink_amt < 0.82:
                eye_h = max(0.045, (0.27 if is_xiaoliuzi else 0.26) * (1.0 - 0.80 * blink_amt))
                eye_r = max(0.20, (0.85 if is_xiaoliuzi else 0.80) * (1.0 - 0.65 * blink_amt))
                eye_white = create_cube_grid(
                    center=(ex, eye_y, 0.29),
                    size=(eye_w, eye_h, 0.12),
                    subdivisions=(4, 5, 2),
                    base_color=COLOR_EYE_WHITE,
                    roundness=eye_r,
                    draw_contour=True,
                )
                head_faces.extend(eye_white)

                # Small mischievous/goofy pupils for 小六子, slightly cross-centered
                p_w = 0.044 if is_xiaoliuzi else 0.065
                p_h_base = 0.056 if is_xiaoliuzi else 0.085
                pupil_h = max(0.020, p_h_base * (1.0 - 0.76 * blink_amt))
                pupil_r = max(0.18, 0.65 * (1.0 - 0.55 * blink_amt))
                p_x_off = (-eye_side * 0.008) if is_xiaoliuzi else (eye_side * 0.012)
                p_y_off = (0.012 if eye_side < 0 else -0.014) if is_xiaoliuzi else -0.01
                pupil = create_cube_grid(
                    center=(ex + p_x_off, eye_y + p_y_off, 0.36),
                    size=(p_w, pupil_h, 0.03),
                    subdivisions=(2, 2, 1),
                    base_color=COLOR_PUPIL_DARK,
                    roundness=pupil_r,
                    draw_contour=False,
                )
                head_faces.extend(pupil)
            else:
                # Closed eyelid pad + cute curved dark blink crease
                eyelid_pad = create_cube_grid(
                    center=(ex, eye_y, 0.275),
                    size=(0.18, 0.20, 0.10),
                    subdivisions=(3, 3, 2),
                    base_color=body_col,
                    roundness=0.55,
                    draw_contour=False,
                )
                head_faces.extend(eyelid_pad)

                lid_pts = [
                    (ex - 0.070, eye_y + 0.008, 0.325),
                    (ex - 0.025, eye_y - 0.014, 0.342),
                    (ex + 0.025, eye_y - 0.014, 0.342),
                    (ex + 0.070, eye_y + 0.008, 0.325),
                ]
                for i in range(len(lid_pts) - 1):
                    head_faces.extend(
                        create_oriented_box(
                            lid_pts[i],
                            lid_pts[i + 1],
                            thickness=(0.020, 0.020),
                            base_color=COLOR_PUPIL_DARK,
                            subdiv_length=1,
                            draw_contour=False,
                        )
                    )

        # Thin expressive eyebrows for 小六子 (one cocked higher for mischievous/goofy look!)
        if is_xiaoliuzi:
            for eye_side in (-1, 1):
                ex = eye_side * eye_spacing
                lift = 0.028 if eye_side < 0 else 0.0
                brow_outer = (ex + eye_side * 0.078, eye_y + 0.165 + lift, 0.29)
                brow_mid = (ex, eye_y + 0.185 + lift, 0.32)
                brow_inner = (ex - eye_side * 0.060, eye_y + 0.150 + lift * 0.4, 0.32)
                head_faces.extend(
                    create_oriented_box(
                        brow_outer, brow_mid,
                        thickness=(0.017, 0.017),
                        base_color=ink_col,
                        subdiv_length=1,
                        draw_contour=False,
                    )
                )
                head_faces.extend(
                    create_oriented_box(
                        brow_mid, brow_inner,
                        thickness=(0.017, 0.017),
                        base_color=ink_col,
                        subdiv_length=1,
                        draw_contour=False,
                    )
                )

        # --- 4. BEAK (Pointed cockerel beak for 小六子; wide banana beak for Carmelito/Carmen/Pangdun) ---
        beak_base_y = head_center_y - (0.12 if is_xiaoliuzi else 0.16)
        jaw_pivot_y = beak_base_y - 0.02
        jaw_pivot_z = 0.22

        upper_beak_faces = []
        if is_xiaoliuzi:
            # Medium-sized pointed yellow-orange beak tapering sharply to a tip
            upper_beak_faces.extend(create_cube_grid(
                center=(0.0, beak_base_y + 0.025, 0.31),
                size=(0.22, 0.11, 0.18),
                subdivisions=(4, 3, 3),
                base_color=beak_col,
                taper_y=0.22,
                taper_z=0.45,
                roundness=0.28,
                draw_contour=True,
            ))
            upper_beak_faces.extend(create_cube_grid(
                center=(0.0, beak_base_y + 0.012, 0.44),
                size=(0.13, 0.08, 0.16),
                subdivisions=(3, 2, 2),
                base_color=beak_col,
                taper_y=0.30,
                taper_z=0.72,
                roundness=0.20,
                draw_contour=True,
            ))
        else:
            upper_beak_faces.extend(create_cube_grid(
                center=(0.0, beak_base_y + 0.025, 0.28),
                size=(0.38, 0.12, 0.14),
                subdivisions=(5, 3, 3),
                base_color=beak_col,
                taper_y=0.10,
                roundness=0.35,
                draw_contour=True,
            ))
            upper_beak_faces.extend(create_cube_grid(
                center=(0.0, beak_base_y + 0.015, 0.37),
                size=(0.34, 0.11, 0.14),
                subdivisions=(5, 3, 3),
                base_color=beak_col,
                taper_y=0.12,
                roundness=0.38,
                draw_contour=True,
            ))
            upper_beak_faces.extend(create_cube_grid(
                center=(0.0, beak_base_y + 0.005, 0.45),
                size=(0.28, 0.10, 0.12),
                subdivisions=(4, 3, 2),
                base_color=beak_col,
                taper_y=0.15,
                roundness=0.42,
                draw_contour=True,
            ))

        if mouth_open or is_xiaoliuzi:
            # 小六子's beak is often slightly open mid-chatter even at rest (or wide open when talking!)
            chatter_open = mouth_open
            up_deg = -22 if chatter_open else -7
            lo_deg = 32 if chatter_open else 12
            head_faces.extend(rotate_faces_x(upper_beak_faces, jaw_pivot_y, jaw_pivot_z, math.radians(up_deg)))

            throat = create_cube_grid(
                center=(0.0, beak_base_y - 0.03, 0.28),
                size=(0.14 if is_xiaoliuzi else 0.24, 0.11 if not chatter_open else 0.15, 0.12),
                subdivisions=(3, 3, 2),
                base_color=COLOR_MOUTH_DARK,
                roundness=0.15,
                draw_contour=False,
            )
            head_faces.extend(throat)

            if chatter_open:
                tongue = create_cube_grid(
                    center=(0.0, beak_base_y - 0.045, 0.35),
                    size=(0.10 if is_xiaoliuzi else 0.14, 0.04, 0.09),
                    subdivisions=(3, 2, 2),
                    base_color=COLOR_TONGUE_PINK,
                    roundness=0.25,
                    draw_contour=False,
                )
                head_faces.extend(rotate_faces_x(tongue, jaw_pivot_y, jaw_pivot_z, math.radians(24)))

            lower_beak_faces = []
            if is_xiaoliuzi:
                lower_beak_faces.extend(create_cube_grid(
                    center=(0.0, beak_base_y - 0.042, 0.31),
                    size=(0.17, 0.06, 0.16),
                    subdivisions=(3, 2, 3),
                    base_color=beak_col,
                    taper_y=0.20,
                    taper_z=0.52,
                    roundness=0.22,
                    draw_contour=True,
                ))
                lower_beak_faces.extend(create_cube_grid(
                    center=(0.0, beak_base_y - 0.042, 0.42),
                    size=(0.10, 0.048, 0.13),
                    subdivisions=(3, 2, 2),
                    base_color=beak_col,
                    taper_y=0.25,
                    taper_z=0.72,
                    roundness=0.18,
                    draw_contour=True,
                ))
            else:
                lower_beak_faces.extend(create_cube_grid(
                    center=(0.0, beak_base_y - 0.055, 0.29),
                    size=(0.32, 0.075, 0.14),
                    subdivisions=(4, 2, 3),
                    base_color=beak_col,
                    taper_y=0.10,
                    roundness=0.22,
                    draw_contour=True,
                ))
                lower_beak_faces.extend(create_cube_grid(
                    center=(0.0, beak_base_y - 0.06, 0.38),
                    size=(0.28, 0.07, 0.13),
                    subdivisions=(4, 2, 2),
                    base_color=beak_col,
                    taper_y=0.15,
                    roundness=0.28,
                    draw_contour=True,
                ))
                lower_beak_faces.extend(create_cube_grid(
                    center=(0.0, beak_base_y - 0.06, 0.44),
                    size=(0.22, 0.065, 0.10),
                    subdivisions=(3, 2, 2),
                    base_color=beak_col,
                    taper_y=0.20,
                    roundness=0.32,
                    draw_contour=True,
                ))
            head_faces.extend(rotate_faces_x(lower_beak_faces, jaw_pivot_y, jaw_pivot_z, math.radians(lo_deg)))
        else:
            head_faces.extend(upper_beak_faces)
            lower_beak = create_cube_grid(
                center=(0.0, beak_base_y - 0.045, 0.34),
                size=(0.32, 0.08, 0.16),
                subdivisions=(4, 2, 3),
                base_color=beak_col,
                taper_y=0.15,
                roundness=0.30,
                draw_contour=True,
            )
            head_faces.extend(lower_beak)

        # Transform head faces: apply head_s (scaled around head_center_y) and neck pivot rotation
        if ragdoll > 0.001:
            rg = max(0.0, min(1.0, ragdoll))
            if ragdoll_pose is not None:
                head_yaw = head_yaw * (1.0 - rg) + float(ragdoll_pose.get("head_yaw", 0.0)) * rg
                head_pitch = head_pitch * (1.0 - rg) + float(ragdoll_pose.get("head_pitch", 0.0)) * rg
            else:
                head_yaw = head_yaw * (1.0 - rg) + 0.28 * rg
                head_pitch = head_pitch * (1.0 - rg) + 0.22 * rg
        if tg > 0.001:
            head_pitch = max(-1.25, min(1.25, head_pitch - 0.42 * tg * (1.0 - 0.35 * sa)))
        pivot_y = head_center_y - 0.28
        has_rot = (abs(head_yaw) > 1e-4 or abs(head_pitch) > 1e-4)
        cos_hy = math.cos(head_yaw) if has_rot else 1.0
        sin_hy = math.sin(head_yaw) if has_rot else 0.0
        cos_hp = math.cos(head_pitch) if has_rot else 1.0
        sin_hp = math.sin(head_pitch) if has_rot else 0.0

        for quad_verts, base_col, has_contour in head_faces:
            r_verts = []
            for vx, vy, vz in quad_verts:
                # Scale relative to head_center_y so head size adjusts cleanly
                sx = vx * head_s
                sy = head_center_y + (vy - head_center_y) * head_s
                sz = vz * head_s

                if has_rot:
                    dy = sy - pivot_y
                    rx1 = sx
                    ry1 = dy * cos_hp + sz * sin_hp
                    rz1 = -dy * sin_hp + sz * cos_hp
                    rx2 = rx1 * cos_hy + rz1 * sin_hy
                    ry2 = ry1
                    rz2 = -rx1 * sin_hy + rz1 * cos_hy
                    r_verts.append((rx2, ry2 + pivot_y, rz2))
                else:
                    r_verts.append((sx, sy, sz))
            all_faces.append((r_verts, base_col, has_contour))

        # --- 5. BODY & BELLY (Pear-shaped scrawny-yet-plump cockerel torso for 小六子) ---
        body_center_y = (0.91 if is_xiaoliuzi else 0.88) + bob_y
        body = create_cube_grid(
            center=(0.0, body_center_y, -0.02),
            size=(0.54 * body_w, 0.74 * body_h, 0.52 * body_d),
            subdivisions=(7, 6, 6),
            base_color=body_col,
            taper_y=-0.34 if is_xiaoliuzi else (-0.18 if is_pangdun else -0.22),
            roundness=0.72 if is_xiaoliuzi else (0.82 if is_pangdun else 0.75),
            draw_contour=True,
        )
        all_faces.extend(body)

        belly = create_cube_grid(
            center=(0.0, body_center_y - (0.11 if is_xiaoliuzi else 0.06), 0.14 * body_d),
            size=(0.48 * body_w, (0.42 if is_xiaoliuzi else 0.48) * body_h, 0.24 * body_d),
            subdivisions=(5, 5, 4) if is_pangdun else (4, 4, 3),
            base_color=belly_col,
            roundness=0.85 if is_pangdun else 0.75,
            draw_contour=False,
        )
        all_faces.extend(belly)

        if is_xiaoliuzi:
            # Subtle pale gray-beige watercolor shading tucked under his wings/sides
            for sh_side in (-1, 1):
                all_faces.extend(
                    create_cube_grid(
                        center=(sh_side * 0.21, body_center_y - 0.04, -0.01),
                        size=(0.12, 0.34, 0.26),
                        subdivisions=(2, 3, 2),
                        base_color=belly_col,
                        roundness=0.70,
                        draw_contour=False,
                    )
                )
            # Short, messy tuft of off-white/pale-beige tail feathers sticking up at the back!
            tail_tufts = [
                ((0.00, 0.02, -0.22), (-0.02, 0.26, -0.35), (0.075, 0.085), body_col),
                ((-0.05, 0.01, -0.22), (-0.11, 0.22, -0.33), (0.065, 0.075), accent_col),
                ((0.05, 0.02, -0.22), (0.10, 0.24, -0.32), (0.065, 0.075), body_col),
                ((0.02, -0.02, -0.22), (0.05, 0.16, -0.36), (0.065, 0.075), accent_col),
                ((-0.02, -0.03, -0.21), (-0.06, 0.13, -0.34), (0.060, 0.070), body_col),
            ]
            for (p0x, p0y, p0z), (p1x, p1y, p1z), t_thick, t_col in tail_tufts:
                all_faces.extend(
                    create_oriented_box(
                        (p0x, body_center_y + p0y, p0z),
                        (p1x, body_center_y + p1y, p1z),
                        thickness=t_thick,
                        base_color=t_col,
                        subdiv_length=2,
                        draw_contour=True,
                    )
                )
        else:
            tail_data = [
                ((0.0, 0.16, -0.32), (0.13, 0.28, 0.15)),
                ((0.0, 0.05, -0.36), (0.14, 0.22, 0.15)),
                ((0.0, -0.05, -0.32), (0.13, 0.17, 0.13)),
            ]
            for (tdx, tdy, tdz), (tsx, tsy, tsz) in tail_data:
                tail_feat = create_cube_grid(
                    center=(tdx, body_center_y + tdy, tdz),
                    size=(tsx, tsy, tsz),
                    subdivisions=(2, 3, 2),
                    base_color=body_col,
                    taper_y=0.3,
                    roundness=0.6,
                    draw_contour=True,
                )
                all_faces.extend(tail_feat)

        # --- 6. WINGS / ARMS (STAND vs WALK PENDULUM vs RUN SPRINTER PUMP) ---
        for side in (-1, 1):
            shoulder_pt = (side * 0.32, body_center_y + 0.12, 0.02)

            # 1. STANDING: Hanging down relaxed
            stand_elbow = (side * 0.32, body_center_y - 0.06, -0.01)
            stand_hand = (side * 0.33, body_center_y - 0.32, 0.01)

            # 2. WALKING: Gentle relaxed pendulum swing forward & back
            walk_arm_swing = -walk_swing * side
            walk_elbow = (
                side * 0.33,
                body_center_y - 0.06,
                walk_arm_swing * 0.10,
            )
            walk_hand = (
                side * 0.34,
                body_center_y - 0.28,
                walk_arm_swing * 0.20,
            )

            # 3. RUNNING: 90-degree bent sprinter arm pump
            run_arm_pump = -run_swing * side
            run_elbow = (
                side * 0.38,
                body_center_y - 0.04,
                -0.12 + run_arm_pump * 0.24,
            )
            run_hand = (
                side * 0.30,
                body_center_y + 0.14 + run_arm_pump * 0.22,
                run_elbow[2] + 0.34,
            )

            # Blend between standing, walking, and running:
            # First blend stand -> walk by walk_weight
            elbow_stand_walk = lerp_vec3(stand_elbow, walk_elbow, ww)
            hand_stand_walk = lerp_vec3(stand_hand, walk_hand, ww)

            # Then blend into running by run_weight
            elbow_pt = lerp_vec3(elbow_stand_walk, run_elbow, rw)
            hand_pt = lerp_vec3(hand_stand_walk, run_hand, rw)

            # Normal jump wing motion when 'J' held without looking up
            if jump_amount > 0.001 and arms_down_amount <= 0.001:
                ja = max(0.0, min(1.0, jump_amount))
                flap_phase = math.sin(run_cycle * 16.0) * 0.18
                jump_elbow = (side * (0.42 + 0.15 * ja), body_center_y + 0.12 * ja + flap_phase, 0.04)
                jump_hand = (side * (0.58 + 0.22 * ja), body_center_y + 0.28 * ja + flap_phase * 1.5, 0.10)
                elbow_pt = lerp_vec3(elbow_pt, jump_elbow, ja)
                hand_pt = lerp_vec3(hand_pt, jump_hand, ja)

            # If facing upwards while holding 'J', lower whole arm down until touching the body!
            if arms_down_amount > 0.001:
                ad = max(0.0, min(1.0, arms_down_amount))
                tuck_shoulder = (side * (0.265 * body_w), body_center_y + 0.08, 0.01)
                tuck_elbow = (side * (0.255 * body_w), body_center_y - 0.16, 0.01)
                tuck_hand = (side * (0.240 * body_w), body_center_y - 0.42, 0.02)
                shoulder_pt = lerp_vec3(shoulder_pt, tuck_shoulder, ad)
                elbow_pt = lerp_vec3(elbow_pt, tuck_elbow, ad)
                hand_pt = lerp_vec3(hand_pt, tuck_hand, ad)

            # Punch wing jab when player punches with 'P'
            if punch_amount > 0.001 and side == punch_side:
                p_ext = max(0.0, min(1.0, punch_amount))
                p_elbow = (side * 0.36, body_center_y + 0.08 * p_ext, 0.02 + 0.42 * p_ext)
                p_hand = (side * (0.30 - 0.14 * p_ext), body_center_y + 0.12 * p_ext, 0.06 + 0.78 * p_ext)
                elbow_pt = lerp_vec3(elbow_pt, p_elbow, p_ext)
                hand_pt = lerp_vec3(hand_pt, p_hand, p_ext)

            # Sitting on grass ('C'): rest wings softly forward at sides
            if sa > 0.001:
                sit_elbow = (side * 0.40, body_center_y - 0.09, 0.04)
                sit_hand = (side * 0.42, body_center_y - 0.26, 0.18)
                elbow_pt = lerp_vec3(elbow_pt, sit_elbow, sa)
                hand_pt = lerp_vec3(hand_pt, sit_hand, sa)

            # Touching the ground ('G'): reach right wing down to gently pat the ground!
            if tg > 0.001:
                pat_w = math.sin(run_cycle * 6.5)
                pat_sw = math.cos(run_cycle * 6.5)
                if side > 0:
                    tg_elbow = (0.36, body_center_y - 0.20, 0.22)
                    tg_hand = (0.16 + 0.06 * pat_sw, 0.09 + 0.045 * abs(pat_w), 0.40 + 0.07 * pat_sw)
                else:
                    tg_elbow = (-0.42, body_center_y - 0.04, -0.05)
                    tg_hand = (-0.48, body_center_y - 0.18, -0.08)
                elbow_pt = lerp_vec3(elbow_pt, tg_elbow, tg)
                hand_pt = lerp_vec3(hand_pt, tg_hand, tg)

            # Zombie tag reach when pressing 'T':
            # Follows the direction of the head in both yaw and pitch (goes down when looking down, up when looking up).
            # If the head is facing sideways, the arm on the other side rests down,
            # while the arm on the side the head is looking stays raised forward!
            if tag_amount > 0.001:
                t_ext = max(0.0, min(1.0, tag_amount))
                neck_height_y = body_center_y + 0.28

                # Determine if this arm should rest when head turns sideways:
                # side: 1.0 (right), -1.0 (left)
                # If head turns right (head_yaw > 0.18): opposite left arm (side=-1) rests.
                # If head turns left (head_yaw < -0.18): opposite right arm (side=1) rests.
                if head_yaw > 0.18:
                    arm_act = 1.0 if side > 0 else max(0.0, 1.0 - (head_yaw - 0.18) * 3.5)
                elif head_yaw < -0.18:
                    arm_act = 1.0 if side < 0 else max(0.0, 1.0 - (-head_yaw - 0.18) * 3.5)
                else:
                    arm_act = 1.0

                effective_tag = t_ext * arm_act

                # Arms aim in the direction of the head (both yaw and pitch):
                arm_look_yaw = head_yaw * 1.15
                arm_pitch_rad = head_pitch * 0.80
                cos_p = math.cos(arm_pitch_rad)
                dir_x = math.sin(arm_look_yaw) * cos_p
                dir_y = -math.sin(arm_pitch_rad)  # In model space: positive head_pitch tilts down
                dir_z = math.cos(arm_look_yaw) * cos_p

                # Straight arm reaching in head direction from shoulder:
                z_elbow = (
                    shoulder_pt[0] + dir_x * 0.42,
                    neck_height_y + dir_y * 0.42,
                    shoulder_pt[2] + dir_z * 0.42,
                )
                z_hand = (
                    shoulder_pt[0] + dir_x * 0.84,
                    neck_height_y + dir_y * 0.84,
                    shoulder_pt[2] + dir_z * 0.84,
                )

                elbow_pt = lerp_vec3(elbow_pt, z_elbow, effective_tag)
                hand_pt = lerp_vec3(hand_pt, z_hand, effective_tag)

            # Ragdoll mode: physics-simulated limp wings (no spinning!)
            if ragdoll > 0.001:
                rg = max(0.0, min(1.0, ragdoll))
                if ragdoll_pose is not None:
                    ek = "l_elbow" if side < 0 else "r_elbow"
                    hk = "l_hand" if side < 0 else "r_hand"
                    rg_elbow = ragdoll_pose.get(ek, elbow_pt)
                    rg_hand = ragdoll_pose.get(hk, hand_pt)
                else:
                    rg_elbow = (side * 0.52, body_center_y - 0.06, -0.05)
                    rg_hand = (side * 0.72, body_center_y - 0.24, -0.10)
                elbow_pt = lerp_vec3(elbow_pt, rg_elbow, rg)
                hand_pt = lerp_vec3(hand_pt, rg_hand, rg)

            # Upper Arm
            upper_arm = create_oriented_box(
                shoulder_pt, elbow_pt,
                thickness=(0.13, 0.18),
                base_color=body_col,
                subdiv_length=3,
                draw_contour=True,
            )
            all_faces.extend(upper_arm)

            # Elbow joint
            elbow_joint = create_cube_grid(
                center=elbow_pt,
                size=(0.13, 0.13, 0.13),
                subdivisions=(2, 2, 2),
                base_color=body_col,
                roundness=0.75,
                draw_contour=True,
            )
            all_faces.extend(elbow_joint)

            # Forearm
            forearm = create_oriented_box(
                elbow_pt, hand_pt,
                thickness=(0.11, 0.15),
                base_color=body_col,
                subdiv_length=3,
                draw_contour=True,
            )
            all_faces.extend(forearm)

            # Feather fingers at hand
            hx, hy, hz = hand_pt
            for finger_i, (f_dy, f_dz) in enumerate((
                (0.04 * rw, 0.05 * rw),
                (0.00, 0.08 * rw - 0.05 * (1.0 - rw)),
                (-0.04 * rw, 0.04 * rw),
            )):
                f_thick = 0.065
                finger = create_cube_grid(
                    center=(hx - side * 0.02, hy + f_dy, hz + f_dz),
                    size=(f_thick, 0.08, 0.09),
                    subdivisions=(2, 2, 2),
                    base_color=accent_col if is_xiaoliuzi else body_col,
                    roundness=0.62,
                    draw_contour=True,
                )
                all_faces.extend(finger)

        # --- 7. CHICKEN LEGS & FEET (NATURAL TWO-SEGMENT KINEMATICS) ---
        hip_y = 0.52 + bob_y
        for side in (-1, 1):
            leg_x = side * 0.14
            hip_pt = (leg_x, hip_y - 0.04, 0.0)

            # Thigh cuff locked to lower body:
            cuff = create_cube_grid(
                center=hip_pt,
                size=(0.19, 0.20, 0.19),
                subdivisions=(3, 3, 3),
                base_color=body_col,
                taper_y=0.45,
                roundness=0.75,
                draw_contour=True,
            )
            all_faces.extend(cuff)

            # Leg segment lengths:
            L_thigh = 0.22
            L_shank = 0.22
            hip_attach_y = hip_y - 0.04

            # --- 1. STANDING POSE (Straight, relaxed vertical stance) ---
            stand_knee = (leg_x, 0.30, 0.01)
            stand_ankle = (leg_x, 0.08, 0.0)
            stand_foot_angle = 0.0

            # --- 2. WALKING POSE (Smooth biological gait: foot stays level on ground, lifts in swing) ---
            walk_s = walk_swing * side
            walk_stride_z = 0.16 * walk_s
            if walk_s >= 0.0:
                # Forward swing: foot smoothly clears ground, toes slightly elevated
                walk_foot_y = 0.08 + 0.05 * walk_s
                walk_pitch = -0.15 * walk_s
            else:
                # Backward stance: foot remains level on ground, toe gently rolls off at rear
                walk_foot_y = 0.08
                w_push = -walk_s
                walk_pitch = 0.20 * w_push

            # Analytical 2-link IK solve for walking knee (always bending forward)
            w_dy = walk_foot_y - hip_attach_y
            w_dz = walk_stride_z
            w_dist = min(math.sqrt(w_dy * w_dy + w_dz * w_dz), L_thigh + L_shank - 0.001)
            w_cos_alpha = max(-1.0, min(1.0, (L_thigh * L_thigh + w_dist * w_dist - L_shank * L_shank) / (2.0 * L_thigh * w_dist)))
            w_alpha = math.acos(w_cos_alpha)
            w_base_angle = math.atan2(w_dz, -w_dy)
            w_knee_angle = w_base_angle + w_alpha

            walk_knee = (leg_x, hip_attach_y - L_thigh * math.cos(w_knee_angle), L_thigh * math.sin(w_knee_angle))
            walk_ankle = (leg_x, walk_foot_y, walk_stride_z)
            walk_foot_angle = walk_pitch

            # --- 3. RUNNING POSE (High knee lift forward kick, athletic rear push-off) ---
            run_s = run_swing * side
            run_stride_z = 0.24 * run_s
            if run_s >= 0.0:
                # Forward sprint stride: high knee lift, toe angled into stride
                run_foot_y = 0.08 + 0.14 * run_s
                run_pitch = -0.32 * run_s
            else:
                # Backward push-off: heel rises, toe digs in to propel forward
                run_foot_y = 0.08
                r_push = -run_s
                run_pitch = 0.38 * r_push

            r_dy = run_foot_y - hip_attach_y
            r_dz = run_stride_z
            r_dist = min(math.sqrt(r_dy * r_dy + r_dz * r_dz), L_thigh + L_shank - 0.001)
            r_cos_alpha = max(-1.0, min(1.0, (L_thigh * L_thigh + r_dist * r_dist - L_shank * L_shank) / (2.0 * L_thigh * r_dist)))
            r_alpha = math.acos(r_cos_alpha)
            r_base_angle = math.atan2(r_dz, -r_dy)
            r_knee_angle = r_base_angle + r_alpha

            run_knee = (leg_x, hip_attach_y - L_thigh * math.cos(r_knee_angle), L_thigh * math.sin(r_knee_angle))
            run_ankle = (leg_x, run_foot_y, run_stride_z)
            run_foot_angle = run_pitch

            # Smoothly blend between standing, walking, and running:
            knee_stand_walk = lerp_vec3(stand_knee, walk_knee, ww)
            ankle_stand_walk = lerp_vec3(stand_ankle, walk_ankle, ww)
            fa_stand_walk = stand_foot_angle + (walk_foot_angle - stand_foot_angle) * ww

            knee_pt = lerp_vec3(knee_stand_walk, run_knee, rw)
            ankle_pt = lerp_vec3(ankle_stand_walk, run_ankle, rw)
            foot_angle = fa_stand_walk + (run_foot_angle - fa_stand_walk) * rw

            # Jump animation: crouch prior to jump, then extend in flight
            if jump_amount > 0.001:
                ja = max(0.0, min(1.0, jump_amount))
                # Deep crouch: knees bend outward and body sinks down; feet stay planted flat
                crouch_knee = (leg_x * 1.18, hip_attach_y - 0.18 * ja, 0.20 * ja)
                crouch_ankle = (leg_x * 0.98, 0.08, 0.14)
                knee_pt = lerp_vec3(knee_pt, crouch_knee, ja)
                ankle_pt = lerp_vec3(ankle_pt, crouch_ankle, ja)
                foot_angle = foot_angle * (1.0 - ja)

            # Touch the ground while standing ('G'): soft knee bend, feet planted firmly on grass
            if tg > 0.001 and sa < 0.99:
                tg_eff = tg * (1.0 - sa)
                tg_knee = (leg_x * 1.06, 0.24, 0.11)
                tg_ankle = (leg_x, 0.08, 0.0)
                knee_pt = lerp_vec3(knee_pt, tg_knee, tg_eff)
                ankle_pt = lerp_vec3(ankle_pt, tg_ankle, tg_eff)
                foot_angle = foot_angle * (1.0 - tg_eff)

            # Sitting down on grass ('C'): cute legs bent forward on the grass, toes tilted up!
            if sa > 0.001:
                sit_knee = (leg_x * 1.18, 0.145, 0.24)
                sit_ankle = (leg_x * 1.12, 0.075, 0.48)
                sit_foot_ang = -0.78
                knee_pt = lerp_vec3(knee_pt, sit_knee, sa)
                ankle_pt = lerp_vec3(ankle_pt, sit_ankle, sa)
                foot_angle = foot_angle * (1.0 - sa) + sit_foot_ang * sa

            # Martial arts karate kick when player kicks with 'K'
            # Negative foot angle rotates toes upward so they point up towards the sky/forward
            if kick_amount > 0.001 and side == kick_side:
                k_ext = max(0.0, min(1.0, kick_amount))
                k_knee = (leg_x * 0.85, hip_attach_y + 0.36 * k_ext, 0.14 + 0.45 * k_ext)
                k_ankle = (leg_x * 0.70, hip_attach_y + 0.65 * k_ext, 0.18 + 0.75 * k_ext)
                k_foot_ang = -0.55 * k_ext
                knee_pt = lerp_vec3(knee_pt, k_knee, k_ext)
                ankle_pt = lerp_vec3(ankle_pt, k_ankle, k_ext)
                foot_angle = foot_angle * (1.0 - k_ext) + k_foot_ang * k_ext

            if ragdoll > 0.001:
                rg = max(0.0, min(1.0, ragdoll))
                if ragdoll_pose is not None:
                    kk = "l_knee" if side < 0 else "r_knee"
                    ak = "l_ankle" if side < 0 else "r_ankle"
                    rg_knee = ragdoll_pose.get(kk, knee_pt)
                    rg_ankle = ragdoll_pose.get(ak, ankle_pt)
                    shin_dy = rg_ankle[1] - rg_knee[1]
                    shin_dz = rg_ankle[2] - rg_knee[2]
                    rg_foot_ang = max(-0.85, min(0.85, math.atan2(shin_dz, max(0.05, -shin_dy)) * 0.55 - 0.35))
                else:
                    rg_knee = (leg_x * 1.35, hip_attach_y - 0.18, 0.10)
                    rg_ankle = (leg_x * 1.55, 0.10, 0.20)
                    rg_foot_ang = -0.55
                knee_pt = lerp_vec3(knee_pt, rg_knee, rg)
                ankle_pt = lerp_vec3(ankle_pt, rg_ankle, rg)
                foot_angle = foot_angle * (1.0 - rg) + rg_foot_ang * rg

            leg_t_thigh = 0.048 if is_xiaoliuzi else 0.075
            leg_t_shank = 0.038 if is_xiaoliuzi else 0.060
            joint_s = 0.052 if is_xiaoliuzi else 0.08

            # Thigh / Femur
            thigh = create_oriented_box(
                hip_pt, knee_pt,
                thickness=(leg_t_thigh, leg_t_thigh),
                base_color=leg_col,
                subdiv_length=2,
                draw_contour=True,
            )
            all_faces.extend(thigh)

            # Knee Joint
            knee_joint = create_cube_grid(
                center=knee_pt,
                size=(joint_s, joint_s, joint_s),
                subdivisions=(2, 2, 2),
                base_color=leg_col,
                roundness=0.5,
                draw_contour=True,
            )
            all_faces.extend(knee_joint)

            # Lower Shank
            shank = create_oriented_box(
                knee_pt, ankle_pt,
                thickness=(leg_t_shank, leg_t_shank),
                base_color=leg_col,
                subdiv_length=2,
                draw_contour=True,
            )
            all_faces.extend(shank)

            # Ankle Joint
            ankle_joint = create_cube_grid(
                center=ankle_pt,
                size=(joint_s * 0.88, joint_s * 0.88, joint_s * 0.88),
                subdivisions=(2, 2, 2),
                base_color=leg_col,
                roundness=0.4,
                draw_contour=True,
            )
            all_faces.extend(ankle_joint)

            # Articulated Foot
            ax, ay, az = ankle_pt
            cos_fa = math.cos(foot_angle)
            sin_fa = math.sin(foot_angle)

            def get_toe_point(local_x: float, local_y: float, local_z: float) -> tuple[float, float, float]:
                rot_y = local_y * cos_fa - local_z * sin_fa
                rot_z = local_y * sin_fa + local_z * cos_fa
                return (ax + local_x, ay + rot_y, az + rot_z)

            # Middle toe
            t_mid_start = get_toe_point(0.0, -0.02, 0.0)
            t_mid_end = get_toe_point(0.0, -0.02, 0.22)
            toe_mid = create_oriented_box(
                t_mid_start, t_mid_end,
                thickness=(0.05, 0.05),
                base_color=leg_col,
                subdiv_length=2,
                draw_contour=True,
            )
            all_faces.extend(toe_mid)

            # Left toe
            t_left_start = get_toe_point(0.0, -0.02, 0.0)
            t_left_end = get_toe_point(-0.08, -0.02, 0.18)
            toe_left = create_oriented_box(
                t_left_start, t_left_end,
                thickness=(0.045, 0.045),
                base_color=leg_col,
                subdiv_length=2,
                draw_contour=True,
            )
            all_faces.extend(toe_left)

            # Right toe
            t_right_start = get_toe_point(0.0, -0.02, 0.0)
            t_right_end = get_toe_point(0.08, -0.02, 0.18)
            toe_right = create_oriented_box(
                t_right_start, t_right_end,
                thickness=(0.045, 0.045),
                base_color=leg_col,
                subdiv_length=2,
                draw_contour=True,
            )
            all_faces.extend(toe_right)

            # Rear spur toe
            t_rear_start = get_toe_point(0.0, -0.01, 0.0)
            t_rear_end = get_toe_point(0.0, 0.02, -0.10)
            toe_rear = create_oriented_box(
                t_rear_start, t_rear_end,
                thickness=(0.032 if is_xiaoliuzi else 0.04, 0.032 if is_xiaoliuzi else 0.04),
                base_color=leg_col,
                subdiv_length=2,
                draw_contour=True,
            )
            all_faces.extend(toe_rear)

            # Pointed claws on three-toed clawed feet for 小六子
            if is_xiaoliuzi:
                for cx_off, cz_base, cz_tip in ((0.0, 0.22, 0.265), (-0.08, 0.18, 0.22), (0.08, 0.18, 0.22)):
                    all_faces.extend(
                        create_oriented_box(
                            get_toe_point(cx_off, -0.02, cz_base),
                            get_toe_point(cx_off * 1.1, -0.028, cz_tip),
                            thickness=(0.022, 0.022),
                            base_color=COLOR_XIAOLIUZI_CLAW,
                            subdiv_length=1,
                            draw_contour=True,
                        )
                    )

        return all_faces

    def build_first_person_feet_faces(
        self,
        ground_y: float = -3.0,
        run_cycle: float = 0.0,
        run_weight: float = 0.0,
        walk_weight: float = 0.0,
        character: str = "carmelito",
        kick_amount: float = 0.0,
        kick_side: float = 1.0,
        jump_amount: float = 0.0,
    ) -> tuple[list[tuple[list[tuple[float, float, float]], tuple[int, int, int], bool]], list[tuple[float, float, float]]]:
        char_l = character.lower()
        if char_l in ("carmen", "卡门"):
            body_col = COLOR_CARMEN_YELLOW
            leg_col = COLOR_CARMEN_LEG
            char_scale_mult = 0.82
        elif char_l in ("pangdun", "小胖墩", "belino", "coquenpate"):
            body_col = COLOR_PANGDUN_WHITE
            leg_col = COLOR_PANGDUN_LEG
            char_scale_mult = 1.15
        elif char_l in ("xiaoliuzi", "小六子", "coqsix", "克西斯"):
            body_col = COLOR_XIAOLIUZI_TAN
            leg_col = COLOR_XIAOLIUZI_LEG
            char_scale_mult = 1.08
        else:
            body_col = COLOR_BODY_PINK
            leg_col = COLOR_LEG_YELLOW
            char_scale_mult = 1.0
        """
        Builds Carmelito's lower pink torso + drumstick thigh cuffs connected through
        2-link IK yellow legs (thigh, knee, shank, ankle) into his 3-toed feet on the
        grass, tucked behind the eye plumb line so looking down shows feet firmly
        attached to legs without the belly blocking view.
        """
        scale = 1.85 * char_scale_mult
        rw = max(0.0, min(1.0, run_weight))
        ww = max(0.0, min(1.0, walk_weight))
        swing = math.sin(run_cycle * 2.0 * math.pi)
        run_bob = abs(swing) * 0.09
        walk_bob = abs(swing) * 0.04
        bob_y = run_bob * rw + walk_bob * (ww * (1.0 - rw))

        # Eyes sit in front of torso center, so hips sit at z = 0.04 and torso sits back at z = -0.22
        z_leg = 0.04
        faces: list[tuple[list[tuple[float, float, float]], tuple[int, int, int], bool]] = []
        shadows: list[tuple[float, float, float]] = []

        def to_world_unit(mx: float, my: float, mz: float, z_base: float = z_leg) -> tuple[float, float, float]:
            return (mx * scale, ground_y + my * scale, z_base + mz * scale)

        # Lower pink torso / belly tucked slightly behind eye plumb line so it frames the bottom without hiding legs/feet
        faces.extend(create_cube_grid(
            center=(0.0, ground_y + (0.72 + bob_y) * scale, -0.22),
            size=(0.44 * scale, 0.52 * scale, 0.30 * scale),
            subdivisions=(4, 4, 3),
            base_color=body_col,
            taper_y=-0.15,
            roundness=0.75,
            draw_contour=True,
        ))

        hip_y = 0.52 + bob_y
        hip_attach_y = hip_y - 0.04
        L_thigh = 0.24
        L_shank = 0.24

        for side in (-1.0, 1.0):
            leg_x = side * 0.14
            hip_pt_m = (leg_x, hip_attach_y, 0.0)

            # Pink feathered drumstick cuff permanently rooting leg into lower body
            faces.extend(create_cube_grid(
                center=to_world_unit(*hip_pt_m),
                size=(0.18 * scale, 0.20 * scale, 0.18 * scale),
                subdivisions=(3, 3, 3),
                base_color=body_col,
                taper_y=0.45,
                roundness=0.75,
                draw_contour=True,
            ))

            # Forward-natural stance & 2-link IK strides so feet stay visible in front of cuffs
            stand_knee = (leg_x, 0.30, 0.12)
            stand_ankle = (leg_x, 0.08, 0.14)
            stand_fa = 0.0

            s = swing * side
            w_dz = 0.14 + 0.14 * s
            if s >= 0.0:
                w_fy = 0.08 + 0.05 * s
                w_fa = -0.15 * s
            else:
                w_fy = 0.08
                w_fa = 0.20 * (-s)
            w_dy = w_fy - hip_attach_y
            w_dist = min(math.sqrt(w_dy * w_dy + w_dz * w_dz), L_thigh + L_shank - 0.001)
            w_cos = max(-1.0, min(1.0, (L_thigh * L_thigh + w_dist * w_dist - L_shank * L_shank) / (2.0 * L_thigh * w_dist)))
            w_ka = math.atan2(w_dz, -w_dy) + math.acos(w_cos)
            walk_knee = (leg_x, hip_attach_y - L_thigh * math.cos(w_ka), L_thigh * math.sin(w_ka))
            walk_ankle = (leg_x, w_fy, w_dz)

            r_dz = 0.14 + 0.21 * s
            if s >= 0.0:
                r_fy = 0.08 + 0.14 * s
                r_fa = -0.32 * s
            else:
                r_fy = 0.08
                r_fa = 0.36 * (-s)
            r_dy = r_fy - hip_attach_y
            r_dist = min(math.sqrt(r_dy * r_dy + r_dz * r_dz), L_thigh + L_shank - 0.001)
            r_cos = max(-1.0, min(1.0, (L_thigh * L_thigh + r_dist * r_dist - L_shank * L_shank) / (2.0 * L_thigh * r_dist)))
            r_ka = math.atan2(r_dz, -r_dy) + math.acos(r_cos)
            run_knee = (leg_x, hip_attach_y - L_thigh * math.cos(r_ka), L_thigh * math.sin(r_ka))
            run_ankle = (leg_x, r_fy, r_dz)

            knee_sw = lerp_vec3(stand_knee, walk_knee, ww)
            ankle_sw = lerp_vec3(stand_ankle, walk_ankle, ww)
            fa_sw = stand_fa + (w_fa - stand_fa) * ww

            knee_m = lerp_vec3(knee_sw, run_knee, rw)
            ankle_m = lerp_vec3(ankle_sw, run_ankle, rw)
            foot_angle = fa_sw + (r_fa - fa_sw) * rw

            # Jump crouch: knees bend forward while feet stay flat on the grass
            if jump_amount > 0.001:
                ja = max(0.0, min(1.0, jump_amount))
                c_knee = (leg_x * 1.12, 0.28 + 0.10 * ja, 0.16 + 0.14 * ja)
                c_ankle = (leg_x, 0.08, 0.14)
                knee_m = lerp_vec3(knee_m, c_knee, ja)
                ankle_m = lerp_vec3(ankle_m, c_ankle, ja)
                foot_angle = foot_angle * (1.0 - ja)

            # Martial arts karate kick when player presses 'K'
            # Negative foot angle rotates toes UPWARD (flexed martial arts kick posture)
            if kick_amount > 0.001 and side == kick_side:
                k_ext = max(0.0, min(1.0, kick_amount))
                # High forward karate kick into full camera view (prominently visible even when looking forward)
                k_ankle = (leg_x * 0.7, hip_attach_y + 0.88 * k_ext, 0.18 + 0.78 * k_ext)
                k_knee = (leg_x * 0.85, hip_attach_y + 0.48 * k_ext, 0.14 + 0.42 * k_ext)
                k_foot_ang = -0.55 * k_ext

                knee_m = lerp_vec3(knee_m, k_knee, k_ext)
                ankle_m = lerp_vec3(ankle_m, k_ankle, k_ext)
                foot_angle = foot_angle * (1.0 - k_ext) + k_foot_ang * k_ext

            hip_w = to_world_unit(*hip_pt_m)
            knee_w = to_world_unit(*knee_m)
            ankle_w = to_world_unit(*ankle_m)

            shadows.append((ankle_w[0], ground_y, ankle_w[2] + 0.14))

            # Thigh
            faces.extend(create_oriented_box(
                hip_w, knee_w,
                thickness=(0.075 * scale, 0.075 * scale),
                base_color=leg_col,
                subdiv_length=2,
                draw_contour=True,
            ))
            # Knee joint
            faces.extend(create_cube_grid(
                center=knee_w,
                size=(0.08 * scale, 0.08 * scale, 0.08 * scale),
                subdivisions=(2, 2, 2),
                base_color=leg_col,
                roundness=0.5,
                draw_contour=True,
            ))
            # Lower shank
            faces.extend(create_oriented_box(
                knee_w, ankle_w,
                thickness=(0.06 * scale, 0.06 * scale),
                base_color=leg_col,
                subdiv_length=2,
                draw_contour=True,
            ))
            # Ankle joint
            faces.extend(create_cube_grid(
                center=ankle_w,
                size=(0.07 * scale, 0.07 * scale, 0.07 * scale),
                subdivisions=(2, 2, 2),
                base_color=leg_col,
                roundness=0.45,
                draw_contour=True,
            ))

            ax, ay, az = ankle_m
            cos_fp = math.cos(foot_angle)
            sin_fp = math.sin(foot_angle)

            def toe_pt(lx: float, ly: float, lz: float) -> tuple[float, float, float]:
                ry = ly * cos_fp - lz * sin_fp
                rz = ly * sin_fp + lz * cos_fp
                return to_world_unit(ax + lx, ay + ry, az + rz)

            # Middle toe
            faces.extend(create_oriented_box(
                toe_pt(0.0, -0.02, 0.0),
                toe_pt(0.0, -0.02, 0.22),
                thickness=(0.05 * scale, 0.05 * scale),
                base_color=leg_col,
                subdiv_length=2,
                draw_contour=True,
            ))
            # Left toe
            faces.extend(create_oriented_box(
                toe_pt(0.0, -0.02, 0.0),
                toe_pt(-0.08, -0.02, 0.18),
                thickness=(0.045 * scale, 0.045 * scale),
                base_color=leg_col,
                subdiv_length=2,
                draw_contour=True,
            ))
            # Right toe
            faces.extend(create_oriented_box(
                toe_pt(0.0, -0.02, 0.0),
                toe_pt(0.08, -0.02, 0.18),
                thickness=(0.045 * scale, 0.045 * scale),
                base_color=leg_col,
                subdiv_length=2,
                draw_contour=True,
            ))
            # Rear spur toe
            faces.extend(create_oriented_box(
                toe_pt(0.0, -0.01, 0.0),
                toe_pt(0.0, 0.02, -0.10),
                thickness=(0.04 * scale, 0.04 * scale),
                base_color=leg_col,
                subdiv_length=2,
                draw_contour=True,
            ))

        return faces, shadows

    def build_first_person_jump_wings(
        self,
        jump_amount: float = 0.0,
        character: str = "carmelito",
        anim_time: float = 0.0,
    ) -> list[tuple[list[tuple[float, float, float]], tuple[int, int, int], bool]]:
        """
        Renders Carmelito's flapping wings in first-person view when jumping with 'J':
        Both wings rise up into the left and right peripheral view and flap dynamically!
        """
        if jump_amount <= 0.001:
            return []

        char_l = character.lower()
        if char_l in ("carmen", "卡门"):
            body_col = COLOR_CARMEN_YELLOW
            char_scale = 0.82
        elif char_l in ("pangdun", "小胖墩", "belino", "coquenpate"):
            body_col = COLOR_PANGDUN_WHITE
            char_scale = 1.15
        elif char_l in ("xiaoliuzi", "小六子", "coqsix", "克西斯"):
            body_col = COLOR_XIAOLIUZI_TAN
            char_scale = 1.08
        else:
            body_col = COLOR_BODY_PINK
            char_scale = 1.0

        ja = max(0.0, min(1.0, jump_amount))
        # High flapping frequency while airborne
        flap = math.sin(anim_time * 18.0) * 0.16 * ja

        faces: list[tuple[list[tuple[float, float, float]], tuple[int, int, int], bool]] = []
        for side in (-1.0, 1.0):
            # Shoulder base anchored slightly below eye level and to the side
            sh_x = side * 0.38 * char_scale
            sh_y = -0.32 * char_scale
            sh_z = 0.22 * char_scale

            # Elbow lifts up and out into view
            elb_x = side * (0.52 + 0.12 * ja) * char_scale
            elb_y = (-0.18 + 0.24 * ja + flap) * char_scale
            elb_z = (0.34 + 0.16 * ja) * char_scale

            # Wing tip / hand flaps vigorously in the upper-outer corners of view
            tip_x = side * (0.64 + 0.18 * ja) * char_scale
            tip_y = (-0.08 + 0.38 * ja + flap * 1.8) * char_scale
            tip_z = (0.42 + 0.22 * ja) * char_scale

            sh_pt = (sh_x, sh_y, sh_z)
            elb_pt = (elb_x, elb_y, elb_z)
            tip_pt = (tip_x, tip_y, tip_z)

            # Upper wing
            faces.extend(create_oriented_box(
                sh_pt, elb_pt,
                thickness=(0.09 * char_scale, 0.14 * char_scale),
                base_color=body_col,
                subdiv_length=2,
                draw_contour=True,
            ))
            # Forearm wing
            faces.extend(create_oriented_box(
                elb_pt, tip_pt,
                thickness=(0.08 * char_scale, 0.18 * char_scale),
                base_color=body_col,
                subdiv_length=2,
                draw_contour=True,
            ))
            # Primary wing flight feathers
            for f_i, (dz, dy_off) in enumerate([(0.0, 0.0), (-0.06, -0.05), (0.05, -0.04)]):
                f_start = (
                    tip_x + side * 0.02 * char_scale,
                    tip_y + dy_off * char_scale,
                    tip_z + dz * char_scale,
                )
                f_end = (
                    tip_x + side * 0.12 * char_scale,
                    tip_y + (dy_off - 0.06) * char_scale,
                    tip_z + (dz + 0.06) * char_scale,
                )
                faces.extend(create_oriented_box(
                    f_start, f_end,
                    thickness=(0.03 * char_scale, 0.06 * char_scale),
                    base_color=body_col,
                    subdiv_length=2,
                    draw_contour=True,
                ))

        return faces

    def build_first_person_tag_hands(
        self,
        ground_y: float = -3.0,
        tag_amount: float = 0.0,
        head_yaw: float = 0.0,
        head_pitch: float = 0.0,
        character: str = "carmelito",
    ) -> list[tuple[list[tuple[float, float, float]], tuple[int, int, int], bool]]:
        """
        Builds completely straight arms in first-person view:
        - Shoulders stay solidly attached to the chick's torso.
        - Arms dynamically and immediately track head pitch:
          * Looking down -> arms immediately dive down with the head towards the feet/ground!
          * Looking up -> arms immediately raise up with the head towards the sky!
        - If the head turns sideways, the opposite arm rests down while the facing arm stays raised.
        """
        if tag_amount <= 0.001:
            return []

        char_l = character.lower()
        if char_l in ("carmen", "卡门"):
            body_col = COLOR_CARMEN_YELLOW
            char_scale = 0.82
        elif char_l in ("pangdun", "小胖墩", "belino", "coquenpate"):
            body_col = COLOR_PANGDUN_WHITE
            char_scale = 1.15
        elif char_l in ("xiaoliuzi", "小六子", "coqsix", "克西斯"):
            body_col = COLOR_XIAOLIUZI_TAN
            char_scale = 1.08
        else:
            body_col = COLOR_BODY_PINK
            char_scale = 1.0

        t_ext = max(0.0, min(1.0, tag_amount))
        faces: list[tuple[list[tuple[float, float, float]], tuple[int, int, int], bool]] = []

        # Direct view-space pitch sensitivity (multiplies pitch so arms move fast and decisively):
        # In first-person camera space:
        # cy is vertical (positive up, negative down).
        # Looking down gives head_pitch < 0 -> arm_pitch_drop drops down rapidly!
        # Looking up gives head_pitch > 0 -> arm_pitch_lift raises up rapidly!
        # Natural 1:1 smooth pitch tracking (not overly exaggerated or jerky)
        pitch_vert_offset = head_pitch * 0.42 * char_scale
        pitch_angle = head_pitch * 0.75

        # Responsive sideways yaw tracking (arms move quickly and smoothly sideways with the head):
        yaw_horiz_offset = head_yaw * 0.35 * char_scale
        arm_yaw = head_yaw * 1.30

        for side in (-1.0, 1.0):
            # Opposite arm rests when looking sideways (transition smoothly)
            if head_yaw > 0.14:
                arm_act = 1.0 if side > 0 else max(0.0, 1.0 - (head_yaw - 0.14) * 4.5)
            elif head_yaw < -0.14:
                arm_act = 1.0 if side < 0 else max(0.0, 1.0 - (-head_yaw - 0.14) * 4.5)
            else:
                arm_act = 1.0

            cur_reach = t_ext * arm_act

            # Shoulder socket on body (deep in torso so it never detaches):
            sh_x = side * 0.28 * char_scale
            sh_y = (-0.32 + 0.14 * t_ext + pitch_vert_offset * 0.35) * char_scale
            sh_z = -0.06 * char_scale
            sh_pt = (sh_x, sh_y, sh_z)

            # Straight arm forward direction following head direction quickly:
            dir_x = math.sin(arm_yaw)
            dir_z = math.cos(arm_yaw) * math.cos(pitch_angle)
            dir_y = math.sin(pitch_angle)

            # Fully extended straight arms at neck level, moving swiftly sideways with the head:
            elb_reach = 0.45 * char_scale
            hand_reach = 0.88 * char_scale

            raised_elb = (
                sh_x + dir_x * elb_reach + yaw_horiz_offset * 0.50,
                sh_y + 0.08 * char_scale + dir_y * elb_reach + pitch_vert_offset * 0.40,
                sh_z + dir_z * elb_reach + 0.22 * char_scale,
            )
            raised_hand = (
                sh_x + dir_x * hand_reach + yaw_horiz_offset,
                sh_y + 0.12 * char_scale + dir_y * hand_reach + pitch_vert_offset * 0.75,
                sh_z + dir_z * hand_reach + 0.45 * char_scale,
            )

            # Resting pose (hanging down relaxed by the chick's side):
            rest_elb = (sh_x, sh_y - 0.22 * char_scale, sh_z + 0.08 * char_scale)
            rest_hand = (sh_x, sh_y - 0.42 * char_scale, sh_z + 0.10 * char_scale)

            # Interpolate between resting and raised by cur_reach:
            elb_pt = (
                rest_elb[0] + (raised_elb[0] - rest_elb[0]) * cur_reach,
                rest_elb[1] + (raised_elb[1] - rest_elb[1]) * cur_reach,
                rest_elb[2] + (raised_elb[2] - rest_elb[2]) * cur_reach,
            )
            hand_pt = (
                rest_hand[0] + (raised_hand[0] - rest_hand[0]) * cur_reach,
                rest_hand[1] + (raised_hand[1] - rest_hand[1]) * cur_reach,
                rest_hand[2] + (raised_hand[2] - rest_hand[2]) * cur_reach,
            )

            # Shoulder joint socket firmly rooted into torso
            faces.extend(create_cube_grid(
                center=sh_pt,
                size=(0.18 * char_scale, 0.20 * char_scale, 0.24 * char_scale),
                subdivisions=(2, 2, 2),
                base_color=body_col,
                roundness=0.7,
                draw_contour=True,
            ))

            # Upper arm (completely straight)
            faces.extend(create_oriented_box(
                sh_pt, elb_pt,
                thickness=(0.12 * char_scale, 0.14 * char_scale),
                base_color=body_col,
                subdiv_length=3,
                draw_contour=True,
            ))

            # Forearm (completely straight)
            faces.extend(create_oriented_box(
                elb_pt, hand_pt,
                thickness=(0.11 * char_scale, 0.13 * char_scale),
                base_color=body_col,
                subdiv_length=3,
                draw_contour=True,
            ))

            # Hand wrist / palm
            faces.extend(create_cube_grid(
                center=hand_pt,
                size=(0.15 * char_scale, 0.14 * char_scale, 0.17 * char_scale),
                subdivisions=(2, 2, 2),
                base_color=body_col,
                roundness=0.7,
                draw_contour=True,
            ))

            # Feather fingers
            hx, hy, hz = hand_pt
            for f_dx, f_dy in [(-0.035, 0.01), (0.0, 0.015), (0.035, 0.01), (side * 0.045, -0.015)]:
                f_tip = (
                    hx + (f_dx * dir_z + 0.18 * dir_x) * char_scale,
                    hy + (f_dy + 0.18 * dir_y) * char_scale,
                    hz + (-f_dx * dir_x + 0.18 * dir_z) * char_scale,
                )
                f_base = (
                    hx + (f_dx * 0.6 * dir_z + 0.06 * dir_x) * char_scale,
                    hy + (f_dy * 0.6 + 0.06 * dir_y) * char_scale,
                    hz + (-f_dx * 0.6 * dir_x + 0.06 * dir_z) * char_scale,
                )
                faces.extend(create_oriented_box(
                    f_base, f_tip,
                    thickness=(0.04 * char_scale, 0.04 * char_scale),
                    base_color=body_col,
                    subdiv_length=2,
                    draw_contour=True,
                ))

        return faces

    def build_first_person_punch_faces(
        self,
        punch_amount: float = 0.0,
        punch_side: float = 1.0,
        character: str = "carmelito",
    ) -> list[tuple[list[tuple[float, float, float]], tuple[int, int, int], bool]]:
        """
        Builds the forward punching wing/fist in first-person view:
        - Feathered wing arm extending forward towards the center of the screen
        - Clenched wing fist punching out into view
        - Color matched to character (Carmelito pink, Carmen yellow, Belino white)
        """
        if punch_amount <= 0.001:
            return []

        char_l = character.lower()
        if char_l in ("carmen", "卡门"):
            body_col = COLOR_CARMEN_YELLOW
            char_scale = 0.82
        elif char_l in ("pangdun", "小胖墩", "belino", "coquenpate"):
            body_col = COLOR_PANGDUN_WHITE
            char_scale = 1.15
        elif char_l in ("xiaoliuzi", "小六子", "coqsix", "克西斯"):
            body_col = COLOR_XIAOLIUZI_TAN
            char_scale = 1.08
        else:
            body_col = COLOR_BODY_PINK
            char_scale = 1.0

        p_ext = max(0.0, min(1.0, punch_amount))
        side = punch_side
        faces: list[tuple[list[tuple[float, float, float]], tuple[int, int, int], bool]] = []

        # Base of shoulder/upper wing
        sh_pos = (side * 0.32 * char_scale, -0.22 * char_scale, 0.12 * char_scale)
        faces.extend(create_cube_grid(
            center=sh_pos,
            size=(0.16 * char_scale, 0.18 * char_scale, 0.18 * char_scale),
            subdivisions=(2, 2, 2),
            base_color=body_col,
            roundness=0.6,
            draw_contour=True,
        ))

        # Fist center (thrusts forward along +Z, slightly angled towards center)
        fist_x = side * (0.28 - 0.14 * p_ext) * char_scale
        fist_y = (-0.16 + 0.06 * p_ext) * char_scale
        fist_z = (0.20 + 0.72 * p_ext) * char_scale
        fist_pos = (fist_x, fist_y, fist_z)

        # Mid-wing elbow / forearm
        mid_x = (sh_pos[0] + fist_x) * 0.5 + side * 0.08 * (1.0 - p_ext) * char_scale
        mid_y = (sh_pos[1] + fist_y) * 0.5 - 0.04 * (1.0 - p_ext) * char_scale
        mid_z = (sh_pos[2] + fist_z) * 0.5
        mid_pos = (mid_x, mid_y, mid_z)

        # Upper wing segment
        faces.extend(create_oriented_box(
            sh_pos, mid_pos,
            thickness=(0.14 * char_scale, 0.14 * char_scale),
            base_color=body_col,
            subdiv_length=2,
            draw_contour=True,
        ))

        # Forearm wing segment
        faces.extend(create_oriented_box(
            mid_pos, fist_pos,
            thickness=(0.13 * char_scale, 0.13 * char_scale),
            base_color=body_col,
            subdiv_length=2,
            draw_contour=True,
        ))

        # Clenched boxing wing/fist
        faces.extend(create_cube_grid(
            center=fist_pos,
            size=(0.18 * char_scale, 0.16 * char_scale, 0.22 * char_scale),
            subdivisions=(3, 3, 3),
            base_color=body_col,
            roundness=0.75,
            draw_contour=True,
        ))

        # Wing knuckle feather ridges
        for k_idx in (-1, 0, 1):
            knuckle_pos = (fist_x + k_idx * 0.04 * char_scale, fist_y, fist_z + 0.10 * char_scale)
            faces.extend(create_cube_grid(
                center=knuckle_pos,
                size=(0.045 * char_scale, 0.065 * char_scale, 0.075 * char_scale),
                subdivisions=(2, 2, 2),
                base_color=body_col,
                roundness=0.6,
                draw_contour=True,
            ))

        return faces

    def build_first_person_touch_ground_hand(
        self,
        touch_ground_amount: float = 0.0,
        pat_phase: float = 0.0,
        character: str = "carmelito",
    ) -> list[tuple[list[tuple[float, float, float]], tuple[int, int, int], bool]]:
        """Build first-person right wing reaching down to touch & gently pat the grass ('G' key)."""
        if touch_ground_amount <= 0.001:
            return []
        char_l = character.lower()
        if char_l in ("carmen", "卡门"):
            body_col = COLOR_CARMEN_YELLOW
            char_scale = 0.82
        elif char_l in ("pangdun", "小胖墩", "belino", "coquenpate"):
            body_col = COLOR_PANGDUN_WHITE
            char_scale = 1.15
        elif char_l in ("xiaoliuzi", "小六子", "coqsix", "克西斯"):
            body_col = COLOR_XIAOLIUZI_TAN
            char_scale = 1.08
        else:
            body_col = COLOR_BODY_PINK
            char_scale = 1.0

        tg = max(0.0, min(1.0, touch_ground_amount))
        pat_w = math.sin(pat_phase * 6.5)
        pat_sw = math.cos(pat_phase * 6.5)
        sh_pos = (0.36 * char_scale, -0.30 * char_scale, 0.14 * char_scale)
        elbow_pos = (0.28 * char_scale, (-0.36 - 0.14 * tg) * char_scale, (0.34 + 0.14 * tg) * char_scale)
        hand_pos = (
            (0.14 + 0.06 * pat_sw * tg) * char_scale,
            (-0.34 - 0.34 * tg + 0.05 * abs(pat_w) * tg) * char_scale,
            (0.38 + 0.34 * tg + 0.06 * pat_sw * tg) * char_scale,
        )
        faces: list[tuple[list[tuple[float, float, float]], tuple[int, int, int], bool]] = []
        faces.extend(create_oriented_box(
            sh_pos, elbow_pos,
            thickness=(0.14 * char_scale, 0.14 * char_scale),
            base_color=body_col, subdiv_length=2, draw_contour=True,
        ))
        faces.extend(create_oriented_box(
            elbow_pos, hand_pos,
            thickness=(0.12 * char_scale, 0.13 * char_scale),
            base_color=body_col, subdiv_length=2, draw_contour=True,
        ))
        faces.extend(create_cube_grid(
            center=hand_pos,
            size=(0.15 * char_scale, 0.10 * char_scale, 0.18 * char_scale),
            subdivisions=(2, 2, 2),
            base_color=body_col, roundness=0.72, draw_contour=True,
        ))
        for f_dx in (-0.04, 0.0, 0.04):
            f_tip = (hand_pos[0] + f_dx * char_scale, hand_pos[1] - 0.04 * tg * char_scale, hand_pos[2] + 0.15 * char_scale)
            faces.extend(create_oriented_box(
                hand_pos, f_tip,
                thickness=(0.042 * char_scale, 0.036 * char_scale),
                base_color=body_col, subdiv_length=2, draw_contour=True,
            ))
        return faces

    def render(
        self,
        surface: pygame.Surface,
        screen_pos: tuple[float, float],
        scale: float,
        rot_y: float = 0.0,
        rot_x: float = 0.08,
        rot_z: float = 0.0,
        lay_pitch: float = 0.0,
        ragdoll: float = 0.0,
        ragdoll_seed: float = 0.0,
        head_yaw: float = 0.0,
        head_pitch: float = 0.0,
        mouth_open: bool = False,
        run_cycle: float = 0.0,
        is_running: bool = False,
        run_weight: float | None = None,
        is_walking: bool = False,
        walk_weight: float = 0.0,
        draw_wireframe: bool = False,
        blink: float = 0.0,
        character: str = "carmelito",
        kick_amount: float = 0.0,
        kick_side: float = 1.0,
        punch_amount: float = 0.0,
        punch_side: float = 1.0,
        jump_amount: float = 0.0,
        arms_down_amount: float = 0.0,
        tag_amount: float = 0.0,
        sit_amount: float = 0.0,
        touch_ground_amount: float = 0.0,
        ragdoll_pose: dict | None = None,
        clip_min_y: float | None = None,
    ) -> None:
        """
        Projects and renders Carmelito in authentic storybook 3D.
        Uses Painter's algorithm with soft cel lighting and inked contour line art.
        """
        char_l = character.lower()
        if char_l in ("carmen", "卡门"):
            char_scale_mult = 0.82
        elif char_l in ("pangdun", "小胖墩", "belino", "coquenpate"):
            char_scale_mult = 1.15  # Plump fat chicken is larger!
        elif char_l in ("xiaoliuzi", "小六子", "coqsix", "克西斯"):
            char_scale_mult = 1.08  # Taller, leaner adolescent young rooster!
        else:
            char_scale_mult = 1.0
        scale = scale * char_scale_mult

        cx_screen, cy_screen = screen_pos
        faces = self.build_model_faces(
            mouth_open=mouth_open,
            run_cycle=run_cycle,
            is_running=is_running,
            run_weight=run_weight,
            is_walking=is_walking,
            walk_weight=walk_weight,
            head_yaw=head_yaw,
            head_pitch=head_pitch,
            blink=blink,
            character=character,
            kick_amount=kick_amount,
            kick_side=kick_side,
            punch_amount=punch_amount,
            punch_side=punch_side,
            jump_amount=jump_amount,
            arms_down_amount=arms_down_amount,
            tag_amount=tag_amount,
            sit_amount=sit_amount,
            touch_ground_amount=touch_ground_amount,
            ragdoll=ragdoll,
            ragdoll_seed=ragdoll_seed,
            ragdoll_pose=ragdoll_pose,
        )

        cos_y = math.cos(rot_y)
        sin_y = math.sin(rot_y)
        cos_x = math.cos(rot_x)
        sin_x = math.sin(rot_x)
        has_roll = abs(rot_z) > 1e-4
        cos_z = math.cos(rot_z)
        sin_z = math.sin(rot_z)
        has_lay = abs(lay_pitch) > 1e-4
        cos_lp = math.cos(lay_pitch)
        sin_lp = math.sin(lay_pitch)
        roll_pivot_y = 0.72
        # When lying flat down (lay_pitch -> ±pi/2), lower pivot smoothly so chick rests flat on the grass!
        roll_drop_y = max(abs(sin_lp) * 0.40, abs(sin_z) * 0.38)

        projected_faces = []
        lx_d, ly_d, lz_d = self.light_dir
        has_roll_or_lay = has_roll or has_lay
        six_scale = 6.0 * scale

        for quad_verts, base_col, has_contour in faces:
            trans_verts = []
            sum_z = 0.0
            sum_local_y = 0.0
            for vx, vy, vz in quad_verts:
                lvx = vx
                lvy = vy
                lvz = vz
                if has_roll:
                    dy_p = lvy - roll_pivot_y
                    lvx, lvy = lvx * cos_z - dy_p * sin_z, lvx * sin_z + dy_p * cos_z + roll_pivot_y
                if has_lay:
                    dy_l = lvy - roll_pivot_y
                    lvy, lvz = dy_l * cos_lp - lvz * sin_lp + roll_pivot_y, dy_l * sin_lp + lvz * cos_lp
                if has_roll_or_lay:
                    lvy -= roll_drop_y
                sum_local_y += lvy

                rx1 = lvx * cos_y + lvz * sin_y
                rz1 = -lvx * sin_y + lvz * cos_y
                ry2 = lvy * cos_x - rz1 * sin_x
                rz2 = lvy * sin_x + rz1 * cos_x

                trans_verts.append((rx1, ry2, rz2))
                sum_z += rz2

            if clip_min_y is not None and (sum_local_y / len(quad_verts)) < clip_min_y:
                continue

            # Fast inline cross product & backface cull before sqrt / lighting / projection
            v0 = trans_verts[0]
            v1 = trans_verts[1]
            v2 = trans_verts[2]
            e1x = v1[0] - v0[0]
            e1y = v1[1] - v0[1]
            e1z = v1[2] - v0[2]
            e2x = v2[0] - v0[0]
            e2y = v2[1] - v0[1]
            e2z = v2[2] - v0[2]
            nx = e1y * e2z - e1z * e2y
            ny = e1z * e2x - e1x * e2z
            nz = e1x * e2y - e1y * e2x

            if nz <= 0.0:
                continue

            nlen = math.sqrt(nx * nx + ny * ny + nz * nz)
            if nlen > 1e-8:
                inv_n = 1.0 / nlen
                nx *= inv_n
                ny *= inv_n
                nz *= inv_n

            diffuse = nx * lx_d + ny * ly_d + nz * lz_d
            if diffuse < 0.0:
                diffuse = 0.0
            brightness = 0.72 + 0.28 * diffuse

            r0, g0, b0 = base_col
            face_col = (
                min(255, int(r0 * brightness)),
                min(255, int(g0 * brightness)),
                min(255, int(b0 * brightness)),
            )

            is_silhouette = nz < 0.32

            screen_pts = [
                (
                    round(cx_screen + rx * (six_scale / max(0.5, 6.0 + rz))),
                    round(cy_screen - ry * (six_scale / max(0.5, 6.0 + rz))),
                )
                for rx, ry, rz in trans_verts
            ]

            avg_z = sum_z / len(trans_verts)
            if base_col == COLOR_PUPIL_DARK:
                avg_z += 0.20

            projected_faces.append((avg_z, screen_pts, face_col, has_contour and is_silhouette))

        # Sort back to front (Painter's algorithm: lowest Z drawn first, highest Z drawn last on top)
        projected_faces.sort(key=lambda item: item[0])

        if char_l in ("carmen", "卡门"):
            ink_color = COLOR_CARMEN_INK
        elif char_l in ("pangdun", "小胖墩", "belino", "coquenpate"):
            ink_color = COLOR_PANGDUN_INK
        elif char_l in ("xiaoliuzi", "小六子", "coqsix", "克西斯"):
            ink_color = COLOR_XIAOLIUZI_INK
        else:
            ink_color = COLOR_INK_LINE

        draw_poly = pygame.draw.polygon
        for _, pts, f_col, draw_ink in projected_faces:
            if len(pts) >= 3:
                draw_poly(surface, f_col, pts)
                if draw_ink:
                    draw_poly(surface, ink_color, pts, 1)
                elif draw_wireframe:
                    draw_poly(surface, COLOR_INK_LINE, pts, 1)

    def render_first_person_beak(
        self,
        surface: pygame.Surface,
        mouth_open: bool = False,
        loco_cycle: float = 0.0,
        run_weight: float = 0.0,
        walk_weight: float = 0.0,
        head_bob_y: float = 0.0,
        character: str = "carmelito",
    ) -> None:
        """
        Renders what Carmelito sees from his own eyes looking out into the world:
        - Wide, chubby yellow banana beak visible right below his sight line in the bottom center.
        - Mouth opens/closes with 'U' key.
        - Feather wings/hands pump into view along the lower corners when walking and running.
        - Inked cartoon outlines matching the storybook style.
        """
        w, h = surface.get_size()
        cx_screen = w * 0.5
        char_l = character.lower()
        is_carmen = (char_l in ("carmen", "卡门"))
        is_pangdun = (char_l in ("pangdun", "小胖墩", "belino", "coquenpate"))
        is_xiaoliuzi = (char_l in ("xiaoliuzi", "小六子", "coqsix", "克西斯"))
        if is_carmen:
            cy_screen = h * 0.90 + head_bob_y * 120.0
            scale = h * 0.45
            beak_color = COLOR_CARMEN_BEAK
        elif is_pangdun:
            cy_screen = h * 0.86 + head_bob_y * 120.0
            scale = h * 0.62  # Chunky prominent beak for 小胖墩
            beak_color = COLOR_PANGDUN_BEAK
        elif is_xiaoliuzi:
            cy_screen = h * 0.875 + head_bob_y * 120.0
            scale = h * 0.56
            beak_color = COLOR_XIAOLIUZI_BEAK
        else:
            cy_screen = h * 0.88 + head_bob_y * 120.0
            scale = h * 0.55
            beak_color = COLOR_BEAK_YELLOW

        # Build Beak & Mouth faces in POV local coords
        # Eye camera is at (0, 0, 0), looking down +Z with slight downward pitch
        pitch = -0.32
        cos_p = math.cos(pitch)
        sin_p = math.sin(pitch)

        # POV Beak geometry positioned right under eyes:
        beak_faces = []

        if is_xiaoliuzi:
            # Pointed yellow-orange cockerel beak (slightly open mid-chatter by default)
            beak_faces.extend(create_cube_grid(
                center=(0.0, -0.22, 0.44),
                size=(0.26, 0.14, 0.24),
                subdivisions=(4, 3, 3),
                base_color=beak_color,
                taper_z=0.50,
                roundness=0.30,
                draw_contour=True,
            ))
            beak_faces.extend(create_cube_grid(
                center=(0.0, -0.25, 0.63),
                size=(0.14, 0.10, 0.18),
                subdivisions=(3, 2, 2),
                base_color=beak_color,
                taper_z=0.72,
                roundness=0.22,
                draw_contour=True,
            ))
            lo_y = -0.43 if mouth_open else -0.35
            beak_faces.extend(create_cube_grid(
                center=(0.0, lo_y, 0.49),
                size=(0.20, 0.10, 0.24),
                subdivisions=(3, 2, 3),
                base_color=beak_color,
                taper_z=0.62,
                roundness=0.28,
                draw_contour=True,
            ))
            beak_faces.extend(create_cube_grid(
                center=(0.0, -0.32 if mouth_open else -0.295, 0.42),
                size=(0.16, 0.10 if mouth_open else 0.055, 0.14),
                subdivisions=(2, 2, 2),
                base_color=COLOR_MOUTH_DARK,
                roundness=0.2,
                draw_contour=False,
            ))
        else:
            # Upper Beak Base
            beak_root = create_cube_grid(
                center=(0.0, -0.22, 0.42),
                size=(0.42, 0.18, 0.22),
                subdivisions=(4, 3, 3),
                base_color=beak_color,
                roundness=0.65,
                draw_contour=True,
            )
            beak_faces.extend(beak_root)

            # Upper Beak Tip (Blunt rounded banana beak)
            beak_tip = create_cube_grid(
                center=(0.0, -0.26, 0.62),
                size=(0.38, 0.17, 0.22),
                subdivisions=(4, 3, 3),
                base_color=beak_color,
                roundness=0.82,
                draw_contour=True,
            )
            beak_faces.extend(beak_tip)

            if mouth_open:
                # Lower beak drops down
                lower_beak = create_cube_grid(
                    center=(0.0, -0.42, 0.48),
                    size=(0.34, 0.14, 0.24),
                    subdivisions=(4, 2, 3),
                    base_color=beak_color,
                    roundness=0.65,
                    draw_contour=True,
                )
                beak_faces.extend(lower_beak)
                mouth_inside = create_cube_grid(
                    center=(0.0, -0.32, 0.42),
                    size=(0.26, 0.10, 0.14),
                    subdivisions=(2, 2, 2),
                    base_color=COLOR_MOUTH_DARK,
                    roundness=0.3,
                    draw_contour=False,
                )
                beak_faces.extend(mouth_inside)
            else:
                lower_beak = create_cube_grid(
                    center=(0.0, -0.32, 0.48),
                    size=(0.36, 0.12, 0.24),
                    subdivisions=(4, 2, 3),
                    base_color=beak_color,
                    roundness=0.65,
                    draw_contour=True,
                )
                beak_faces.extend(lower_beak)

        # No arms or head in sight: purely what Carmelito sees in front

        # Project and render POV faces
        projected = []
        for quad_verts, base_col, has_contour in beak_faces:
            trans_verts = []
            sum_z = 0.0
            for vx, vy, vz in quad_verts:
                # Rotate by downward pitch
                ry = vy * cos_p - vz * sin_p
                rz = vy * sin_p + vz * cos_p
                rx = vx
                trans_verts.append((rx, ry, rz))
                sum_z += rz

            # Normal lighting
            v0, v1, v2 = trans_verts[0], trans_verts[1], trans_verts[2]
            edge1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
            edge2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
            normal = self._normalize(self._cross(edge1, edge2))
            if normal[2] <= 0.0:
                continue

            diffuse = max(0.0, self._dot(normal, self.light_dir))
            brightness = 0.75 + 0.25 * diffuse
            face_col = (
                min(255, int(base_col[0] * brightness)),
                min(255, int(base_col[1] * brightness)),
                min(255, int(base_col[2] * brightness)),
            )

            is_silhouette = normal[2] < 0.35
            screen_pts = []
            for rx, ry, rz in trans_verts:
                dist = max(0.1, rz)
                proj = 1.0 / dist
                sx = cx_screen + rx * scale * proj
                sy = cy_screen - ry * scale * proj
                screen_pts.append((round(sx), round(sy)))

            avg_z = sum_z / len(trans_verts)
            projected.append((avg_z, screen_pts, face_col, has_contour and is_silhouette))

        projected.sort(key=lambda item: item[0], reverse=True)
        for _, pts, f_col, draw_ink in projected:
            if len(pts) >= 3:
                pygame.draw.polygon(surface, f_col, pts)
                if draw_ink:
                    pygame.draw.polygon(surface, COLOR_INK_LINE, pts, 1)


class ChickRagdollSim:
    """
    Lightweight Verlet + distance-constraint + ground-floor ragdoll physics solver
    for a chick's head, wings (elbows/hands), and legs (knees/ankles).
    Limbs react to gravity, torso acceleration/velocity, and rest completely still on the grass!
    """

    JOINTS = (
        "head",
        "l_elbow", "l_hand",
        "r_elbow", "r_hand",
        "l_knee", "l_ankle",
        "r_knee", "r_ankle",
    )

    def __init__(self) -> None:
        self.active = False
        self.pos: dict[str, list[float]] = {}
        self.prev: dict[str, list[float]] = {}
        self.pose_cache: dict | None = None

    def reset(self) -> None:
        self.active = False
        self.pos.clear()
        self.prev.clear()
        self.pose_cache = None

    @staticmethod
    def _local_to_world(
        lx: float,
        ly: float,
        lz: float,
        wx: float,
        jump_y: float,
        wz: float,
        world_rot_y: float,
        rot_z: float,
        lay_pitch: float,
        scale: float,
    ) -> list[float]:
        pivot_y = 0.72
        cos_z = math.cos(rot_z)
        sin_z = math.sin(rot_z)
        cos_lp = math.cos(lay_pitch)
        sin_lp = math.sin(lay_pitch)
        roll_drop_y = max(abs(sin_lp) * 0.40, abs(sin_z) * 0.38)

        # 1. Local Z tilt
        if abs(rot_z) > 1e-4:
            dy = ly - pivot_y
            tx = lx * cos_z - dy * sin_z
            ty = lx * sin_z + dy * cos_z + pivot_y
            tz = lz
        else:
            tx, ty, tz = lx, ly, lz

        # 2. Local X lay pitch
        if abs(lay_pitch) > 1e-4:
            dy = ty - pivot_y
            ny = dy * cos_lp - tz * sin_lp + pivot_y
            nz = dy * sin_lp + tz * cos_lp
            ty, tz = ny, nz

        if abs(rot_z) > 1e-4 or abs(lay_pitch) > 1e-4:
            ty -= roll_drop_y

        # 3. Scale & world yaw around Y
        sx = tx * scale
        sy = ty * scale
        sz = tz * scale
        cos_y = math.cos(world_rot_y)
        sin_y = math.sin(world_rot_y)
        # Forward (+Z local) aligns with (sin(world_rot_y), cos(world_rot_y)), Right (+X local) aligns with (-cos, sin)
        world_x = wx - sx * cos_y + sz * sin_y
        world_y = jump_y + sy
        world_z = wz + sx * sin_y + sz * cos_y
        return [world_x, world_y, world_z]

    @staticmethod
    def _world_to_local(
        px: float,
        py: float,
        pz: float,
        wx: float,
        jump_y: float,
        wz: float,
        world_rot_y: float,
        rot_z: float,
        lay_pitch: float,
        scale: float,
    ) -> tuple[float, float, float]:
        # Inverse step 3: undo translation, world yaw, scale
        dx = px - wx
        dy_w = py - jump_y
        dz = pz - wz
        cos_y = math.cos(world_rot_y)
        sin_y = math.sin(world_rot_y)
        inv_s = 1.0 / max(0.1, scale)
        tx = (-dx * cos_y + dz * sin_y) * inv_s
        ty = dy_w * inv_s
        tz = (dx * sin_y + dz * cos_y) * inv_s

        pivot_y = 0.72
        cos_z = math.cos(rot_z)
        sin_z = math.sin(rot_z)
        cos_lp = math.cos(lay_pitch)
        sin_lp = math.sin(lay_pitch)
        roll_drop_y = max(abs(sin_lp) * 0.40, abs(sin_z) * 0.38)
        if abs(rot_z) > 1e-4 or abs(lay_pitch) > 1e-4:
            ty += roll_drop_y

        # Inverse step 2: undo lay_pitch (-lay_pitch)
        if abs(lay_pitch) > 1e-4:
            dy = ty - pivot_y
            ny = dy * cos_lp + tz * sin_lp + pivot_y
            nz = -dy * sin_lp + tz * cos_lp
            ty, tz = ny, nz

        # Inverse step 1: undo rot_z (-rot_z)
        if abs(rot_z) > 1e-4:
            dy = ty - pivot_y
            nx = tx * cos_z + dy * sin_z
            ny = -tx * sin_z + dy * cos_z + pivot_y
            tx, ty = nx, ny

        return (tx, ty, tz)

    @staticmethod
    def _constrain_dist(p_a: list[float], p_b: list[float], target_len: float, pin_a: bool = False) -> None:
        dx = p_b[0] - p_a[0]
        dy = p_b[1] - p_a[1]
        dz = p_b[2] - p_a[2]
        d = math.sqrt(dx * dx + dy * dy + dz * dz)
        if d < 1e-6:
            p_b[1] -= target_len
            return
        diff = (d - target_len) / d
        if pin_a:
            p_b[0] -= dx * diff
            p_b[1] -= dy * diff
            p_b[2] -= dz * diff
        else:
            half = 0.5 * diff
            p_a[0] += dx * half
            p_a[1] += dy * half
            p_a[2] += dz * half
            p_b[0] -= dx * half
            p_b[1] -= dy * half
            p_b[2] -= dz * half

    def step(
        self,
        dt: float,
        wx: float,
        jump_y: float,
        wz: float,
        world_rot_y: float,
        rot_z: float,
        lay_pitch: float,
        ragdoll: float,
        scale: float = 1.0,
    ) -> dict | None:
        if ragdoll <= 0.01:
            if self.active:
                self.reset()
            return None

        l2w = lambda lx, ly, lz: self._local_to_world(
            lx, ly, lz, wx, jump_y, wz, world_rot_y, rot_z, lay_pitch, scale
        )
        w2l = lambda p: self._world_to_local(
            p[0], p[1], p[2], wx, jump_y, wz, world_rot_y, rot_z, lay_pitch, scale
        )

        # Default standing anchors in local space
        l_sh_loc = (-0.32, 1.00, 0.02)
        r_sh_loc = (0.32, 1.00, 0.02)
        l_hp_loc = (-0.14, 0.48, 0.0)
        r_hp_loc = (0.14, 0.48, 0.0)
        nk_loc = (0.0, 1.16, 0.0)

        if not self.active:
            self.active = True
            init_locals = {
                "head": (0.0, 1.46, 0.0),
                "l_elbow": (-0.38, 0.82, -0.02),
                "l_hand": (-0.42, 0.56, 0.02),
                "r_elbow": (0.38, 0.82, -0.02),
                "r_hand": (0.42, 0.56, 0.02),
                "l_knee": (-0.16, 0.28, 0.02),
                "l_ankle": (-0.17, 0.08, 0.01),
                "r_knee": (0.16, 0.28, 0.02),
                "r_ankle": (0.17, 0.08, 0.01),
            }
            for k, loc in init_locals.items():
                p = l2w(*loc)
                self.pos[k] = list(p)
                self.prev[k] = list(p)

        dt_clamped = max(1e-4, min(0.033, dt))
        sub_steps = 2
        sub_dt = dt_clamped / sub_steps

        l_sh = l2w(*l_sh_loc)
        r_sh = l2w(*r_sh_loc)
        l_hp = l2w(*l_hp_loc)
        r_hp = l2w(*r_hp_loc)
        nk = l2w(*nk_loc)
        torso_c = l2w(0.0, 0.86, 0.0)

        len_neck = 0.30 * scale
        len_uarm = 0.24 * scale
        len_farm = 0.28 * scale
        len_thigh = 0.24 * scale
        len_shank = 0.24 * scale
        torso_rad = 0.33 * scale

        radii = {
            "head": 0.26 * scale,
            "l_elbow": 0.08 * scale,
            "l_hand": 0.07 * scale,
            "r_elbow": 0.08 * scale,
            "r_hand": 0.07 * scale,
            "l_knee": 0.08 * scale,
            "l_ankle": 0.07 * scale,
            "r_knee": 0.08 * scale,
            "r_ankle": 0.07 * scale,
        }

        for _ in range(sub_steps):
            # 1. Verlet integration with gravity & air/ground damping
            for k in self.JOINTS:
                p = self.pos[k]
                pr = self.prev[k]
                floor_y = radii[k]
                on_ground = p[1] <= floor_y + 0.015
                damp = 0.65 if on_ground else 0.965
                vx = (p[0] - pr[0]) * damp
                vy = (p[1] - pr[1]) * damp
                vz = (p[2] - pr[2]) * damp
                # Sleep dead micro-jitter when resting on grass
                if on_ground and (vx * vx + vy * vy + vz * vz) < 1e-6:
                    pr[0], pr[1], pr[2] = p[0], p[1], p[2]
                    continue
                nx = p[0] + vx
                ny = p[1] + vy - 24.0 * sub_dt * sub_dt
                nz = p[2] + vz
                pr[0], pr[1], pr[2] = p[0], p[1], p[2]
                p[0], p[1], p[2] = nx, ny, nz

            # 2. Distance constraints + torso push-out + grass floor collision
            for _it in range(4):
                self._constrain_dist(nk, self.pos["head"], len_neck, pin_a=True)
                self._constrain_dist(l_sh, self.pos["l_elbow"], len_uarm, pin_a=True)
                self._constrain_dist(self.pos["l_elbow"], self.pos["l_hand"], len_farm, pin_a=False)
                self._constrain_dist(r_sh, self.pos["r_elbow"], len_uarm, pin_a=True)
                self._constrain_dist(self.pos["r_elbow"], self.pos["r_hand"], len_farm, pin_a=False)
                self._constrain_dist(l_hp, self.pos["l_knee"], len_thigh, pin_a=True)
                self._constrain_dist(self.pos["l_knee"], self.pos["l_ankle"], len_shank, pin_a=False)
                self._constrain_dist(r_hp, self.pos["r_knee"], len_thigh, pin_a=True)
                self._constrain_dist(self.pos["r_knee"], self.pos["r_ankle"], len_shank, pin_a=False)

                for k in self.JOINTS:
                    p = self.pos[k]
                    # Prevent limbs clipping into torso belly
                    if k != "head":
                        tdx = p[0] - torso_c[0]
                        tdy = p[1] - torso_c[1]
                        tdz = p[2] - torso_c[2]
                        td2 = tdx * tdx + tdy * tdy + tdz * tdz
                        if 1e-6 < td2 < torso_rad * torso_rad:
                            td = math.sqrt(td2)
                            push = (torso_rad - td) / td
                            p[0] += tdx * push
                            p[1] += tdy * push
                            p[2] += tdz * push
                    # Grass floor collision with strong ground friction
                    floor_y = radii[k]
                    if p[1] < floor_y:
                        p[1] = floor_y
                        pr = self.prev[k]
                        pr[0] = p[0] - (p[0] - pr[0]) * 0.30
                        pr[2] = p[2] - (p[2] - pr[2]) * 0.30
                        if pr[1] < floor_y:
                            pr[1] = floor_y

        # 3. Convert solved world particles back into chick local pose
        head_loc = w2l(self.pos["head"])
        hdx = head_loc[0] - nk_loc[0]
        hdy = head_loc[1] - nk_loc[1]
        hdz = head_loc[2] - nk_loc[2]
        head_yaw = max(-0.55, min(0.55, math.atan2(hdx, max(0.14, hdy))))
        head_pitch = max(-0.55, min(0.55, math.atan2(hdz, max(0.14, hdy))))

        self.pose_cache = {
            "l_elbow": w2l(self.pos["l_elbow"]),
            "l_hand": w2l(self.pos["l_hand"]),
            "r_elbow": w2l(self.pos["r_elbow"]),
            "r_hand": w2l(self.pos["r_hand"]),
            "l_knee": w2l(self.pos["l_knee"]),
            "l_ankle": w2l(self.pos["l_ankle"]),
            "r_knee": w2l(self.pos["r_knee"]),
            "r_ankle": w2l(self.pos["r_ankle"]),
            "head_yaw": head_yaw,
            "head_pitch": head_pitch,
        }
        return self.pose_cache
