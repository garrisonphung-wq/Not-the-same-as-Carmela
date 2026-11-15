import argparse
import asyncio
import json
import math
import os
import sys
import threading
from typing import Any
from urllib.parse import urlparse

import pygame
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

import server as game_server
from carmelito_3d import Carmelito3D

WINDOW_TITLE = "不一样的卡梅拉"
DEFAULT_SERVER_URL = os.environ.get("GAME_SERVER_URL", "ws://127.0.0.1:8765")

# Pure white background, clean ground grid ready for grass
BG_COLOR = (255, 255, 255)
GROUND_GRID_COLOR = (205, 220, 215)  # Muted pastel sage grid (ready to turn into grass)
LOCAL_DOT_COLOR = (255, 175, 195)
REMOTE_DOT_COLOR = (120, 195, 255)

REMOTE_LERP_SPEED = 24.0
NETWORK_SEND_HZ = 60.0
TARGET_FPS = 60.0
WALK_SPEED = 3.2
RUN_SPEED = 6.8
TURN_SPEED = 2.2

# Normal tall human eye height
GROUND_Y = -3.0
GRID_STEP = 2.0
GRID_EXTENT = 50.0

# Anatomical neck rotation limits (less than 90 degrees sideways, can tilt up into the sky)
MAX_HEAD_YAW = math.radians(72.0)       # ~72 degrees max turn left/right (close to sideways, but less than sideways)
MAX_HEAD_PITCH_UP = math.radians(52.0)  # ~52 degrees max upward tilt
MAX_HEAD_PITCH_DOWN = math.radians(35.0)# ~35 degrees max downward tilt
HEAD_SMOOTH_SPEED = 14.0                # Smooth realistic neck following rate


def create_window(fullscreen: bool) -> pygame.Surface:
    desktop_sizes = pygame.display.get_desktop_sizes()
    desktop_w, desktop_h = desktop_sizes[0] if desktop_sizes else (1280, 720)
    if fullscreen:
        return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    win_w = max(800, int(desktop_w * 0.8))
    win_h = max(600, int(desktop_h * 0.8))
    return pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)


def is_local_server_url(server_url: str) -> tuple[bool, int]:
    parsed = urlparse(server_url)
    host = (parsed.hostname or "").lower()
    port = parsed.port or (443 if parsed.scheme == "wss" else 8765)
    return host in {"127.0.0.1", "localhost", "::1", "0.0.0.0"}, port


class NetworkClient:
    def __init__(self, server_url: str = DEFAULT_SERVER_URL, auto_host: bool = True) -> None:
        self.server_url = server_url
        self.auto_host = auto_host

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._host_started = False

        self.connected = False
        self.is_host = False
        self.my_id: int | None = None
        self.my_color = LOCAL_DOT_COLOR

        self.remote_players: dict[int, dict[str, Any]] = {}

        self._local_nx = 0.5
        self._local_ny = 0.4
        self._local_running = False
        self._local_walking = False
        self._local_mouth = False
        self._local_rot_y = 0.0
        self._pos_dirty = True

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def update_local_state(
        self,
        nx: float,
        ny: float,
        is_running: bool,
        mouth_open: bool,
        is_walking: bool = False,
        rot_y: float = 0.0,
    ) -> None:
        nx = max(0.05, min(0.95, nx))
        ny = max(0.05, min(0.95, ny))
        with self._lock:
            pos_changed = (abs(nx - self._local_nx) > 0.0001) or (abs(ny - self._local_ny) > 0.0001)
            state_changed = (
                (is_running != self._local_running)
                or (is_walking != self._local_walking)
                or (mouth_open != self._local_mouth)
                or (abs(rot_y - self._local_rot_y) > 0.01)
            )
            if pos_changed or state_changed:
                self._local_nx = nx
                self._local_ny = ny
                self._local_running = is_running
                self._local_walking = is_walking
                self._local_mouth = mouth_open
                self._local_rot_y = rot_y
                self._pos_dirty = True

    def get_snapshot(self) -> tuple[bool, bool, int | None, tuple[int, int, int], dict[int, dict[str, Any]]]:
        with self._lock:
            players_copy = {
                pid: {
                    "nx": data["nx"],
                    "ny": data["ny"],
                    "running": data.get("running", False),
                    "walking": data.get("walking", False),
                    "mouth": data.get("mouth", False),
                    "rot_y": data.get("rot_y", 0.0),
                    "color": data["color"],
                    "name": data.get("name"),
                    "is_carmelito": data.get("is_carmelito", False),
                }
                for pid, data in self.remote_players.items()
            }
            return self.connected, self.is_host, self.my_id, self.my_color, players_copy

    def stop(self) -> None:
        self._stop_event.set()

    def _start_embedded_server(self, port: int) -> None:
        if self._host_started:
            return
        self._host_started = True

        def server_runner() -> None:
            try:
                asyncio.run(game_server.run_server(host="0.0.0.0", port=port))
            except OSError:
                pass

        thread = threading.Thread(target=server_runner, daemon=True)
        thread.start()
        with self._lock:
            self.is_host = True

    def _run_loop(self) -> None:
        asyncio.run(self._network_main())

    async def _network_main(self) -> None:
        is_local, port = is_local_server_url(self.server_url)
        while not self._stop_event.is_set():
            try:
                async with connect(self.server_url, ping_interval=15, ping_timeout=15) as ws:
                    with self._lock:
                        self.connected = True
                    send_task = asyncio.create_task(self._sender_loop(ws))
                    recv_task = asyncio.create_task(self._receiver_loop(ws))
                    done, pending = await asyncio.wait(
                        {send_task, recv_task},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for t in pending:
                        t.cancel()
                    for t in done:
                        if not t.cancelled():
                            exc = t.exception()
                            if exc is not None and not isinstance(exc, ConnectionClosed):
                                raise exc
            except (ConnectionRefusedError, OSError):
                if is_local and self.auto_host and not self._host_started:
                    self._start_embedded_server(port)
                    await asyncio.sleep(0.15)
                    continue
                with self._lock:
                    self.connected = False
                    self.remote_players.clear()
            except Exception:
                with self._lock:
                    self.connected = False
                    self.remote_players.clear()

            if not self._stop_event.is_set():
                await asyncio.sleep(1.5)

    async def _sender_loop(self, ws: Any) -> None:
        interval = 1.0 / NETWORK_SEND_HZ
        while not self._stop_event.is_set():
            payload = None
            with self._lock:
                if self._pos_dirty:
                    payload = json.dumps(
                        {
                            "type": "pos",
                            "x": round(self._local_nx, 5),
                            "y": round(self._local_ny, 5),
                            "running": self._local_running,
                            "walking": self._local_walking,
                            "mouth": self._local_mouth,
                            "rot_y": round(self._local_rot_y, 4),
                            "is_carmelito": True,
                        },
                        separators=(",", ":"),
                    )
                    self._pos_dirty = False
            if payload is not None:
                await ws.send(payload)
            await asyncio.sleep(interval)

    async def _receiver_loop(self, ws: Any) -> None:
        async for raw in ws:
            if self._stop_event.is_set():
                return
            if not isinstance(raw, str):
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")
            if msg_type == "welcome":
                my_id = int(msg["id"])
                my_color = tuple(int(c) for c in msg["color"])
                raw_players = msg.get("players", {})
                with self._lock:
                    self.my_id = my_id
                    self.my_color = my_color
                    self.remote_players.clear()
                    for pid_str, pdata in raw_players.items():
                        pid = int(pid_str)
                        if pid == my_id:
                            continue
                        self.remote_players[pid] = {
                            "nx": float(pdata["x"]),
                            "ny": float(pdata["y"]),
                            "running": bool(pdata.get("running", False)),
                            "walking": bool(pdata.get("walking", False)),
                            "mouth": bool(pdata.get("mouth", False)),
                            "rot_y": float(pdata.get("rot_y", 0.0)),
                            "color": tuple(int(c) for c in pdata["color"]),
                            "name": pdata.get("name"),
                            "is_carmelito": bool(pdata.get("is_carmelito", False)),
                        }

            elif msg_type == "join":
                pid = int(msg["id"])
                with self._lock:
                    if pid != self.my_id:
                        self.remote_players[pid] = {
                            "nx": float(msg["x"]),
                            "ny": float(msg["y"]),
                            "running": bool(msg.get("running", False)),
                            "walking": bool(msg.get("walking", False)),
                            "mouth": bool(msg.get("mouth", False)),
                            "rot_y": float(msg.get("rot_y", 0.0)),
                            "color": tuple(int(c) for c in msg["color"]),
                            "name": msg.get("name"),
                            "is_carmelito": bool(msg.get("is_carmelito", False)),
                        }

            elif msg_type == "pos":
                pid = int(msg["id"])
                with self._lock:
                    if pid in self.remote_players:
                        self.remote_players[pid]["nx"] = float(msg["x"])
                        self.remote_players[pid]["ny"] = float(msg["y"])
                        self.remote_players[pid]["running"] = bool(msg.get("running", False))
                        self.remote_players[pid]["walking"] = bool(msg.get("walking", False))
                        self.remote_players[pid]["mouth"] = bool(msg.get("mouth", False))
                        if "rot_y" in msg:
                            self.remote_players[pid]["rot_y"] = float(msg["rot_y"])
                        if "is_carmelito" in msg:
                            self.remote_players[pid]["is_carmelito"] = bool(msg["is_carmelito"])
                        if "name" in msg and msg["name"]:
                            self.remote_players[pid]["name"] = msg["name"]

            elif msg_type == "leave":
                pid = int(msg["id"])
                with self._lock:
                    self.remote_players.pop(pid, None)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carmelito 3D Game")
    parser.add_argument(
        "--server",
        default=DEFAULT_SERVER_URL,
        help=f"WebSocket server URL (default: {DEFAULT_SERVER_URL})",
    )
    parser.add_argument(
        "--windowed",
        action="store_true",
        help="Start in a resizable window instead of fullscreen",
    )
    parser.add_argument(
        "--no-auto-host",
        action="store_true",
        help="Do not auto-start a local server if localhost is unreachable",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    pygame.init()
    pygame.display.set_caption(WINDOW_TITLE)

    fullscreen = not args.windowed
    screen = create_window(fullscreen)
    clock = pygame.time.Clock()
    pygame.mouse.set_visible(True)

    model_3d = Carmelito3D()

    # Carmelito's body position and body yaw in 3D space
    cam_x = 0.0
    cam_z = -3.5
    cam_yaw = 0.0         # Body facing angle around Y axis

    # Head neck yaw and pitch offsets (controlled by mouse)
    head_yaw = 0.0
    head_pitch = 0.0

    mouth_open = False
    anim_time = 0.0

    # Locomotion states & smooth weights
    run_weight = 0.0      # 0.0 = not running, 1.0 = full sprint
    walk_weight = 0.0     # 0.0 = not walking, 1.0 = full walk
    motion_cycle = 0.0    # Continuous stride cadence

    net = NetworkClient(server_url=args.server, auto_host=not args.no_auto_host)
    remote_world_pos: dict[int, list[float]] = {}

    running = True
    while running:
        dt = min(clock.tick(TARGET_FPS) / 1000.0, 0.05)
        anim_time += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_F11, pygame.K_f):
                    fullscreen = not fullscreen
                    screen = create_window(fullscreen)
                elif event.key == pygame.K_u:
                    # Toggle mouth open / close
                    mouth_open = not mouth_open

        keys = pygame.key.get_pressed()
        win_w, win_h = screen.get_size()

        # --- HEAD FOLLOWS MOUSE POINTER ---
        # Mouse position relative to center of screen [-1.0, 1.0]
        mx, my = pygame.mouse.get_pos()
        norm_mx = (mx - win_w * 0.5) / max(1.0, win_w * 0.5)
        norm_my = (my - win_h * 0.5) / max(1.0, win_h * 0.5)

        # Human neck turning limits:
        # Yaw: close to sideways (~72 degrees), but strictly less than 90 degrees sideways
        target_head_yaw = max(-MAX_HEAD_YAW, min(MAX_HEAD_YAW, norm_mx * MAX_HEAD_YAW))

        # Pitch: moving mouse up tilts head up (can look up into sky), moving down tilts down
        if norm_my < 0.0:
            target_head_pitch = -norm_my * MAX_HEAD_PITCH_UP
        else:
            target_head_pitch = -norm_my * MAX_HEAD_PITCH_DOWN
        target_head_pitch = max(-MAX_HEAD_PITCH_DOWN, min(MAX_HEAD_PITCH_UP, target_head_pitch))

        # Smooth neck interpolation
        head_alpha = 1.0 - math.exp(-HEAD_SMOOTH_SPEED * dt)
        head_yaw += (target_head_yaw - head_yaw) * head_alpha
        head_pitch += (target_head_pitch - head_pitch) * head_alpha

        # --- BODY TURNING CONTROLS ---
        # Left Arrow / Right Arrow turns the entire body smoothly
        turn_input = 0.0
        if keys[pygame.K_LEFT]:
            turn_input -= 1.0
        if keys[pygame.K_RIGHT]:
            turn_input += 1.0
        cam_yaw += turn_input * TURN_SPEED * dt

        # Total eye gaze direction = Body yaw + Head neck yaw & pitch
        total_yaw = cam_yaw + head_yaw
        total_pitch = head_pitch

        # Up Arrow: Walk/Run forward in the direction Carmelito is facing
        # Down Arrow: Walk/Run backward
        move_fwd = 0.0
        if keys[pygame.K_UP]:
            move_fwd += 1.0
        if keys[pygame.K_DOWN]:
            move_fwd -= 1.0

        is_moving = (move_fwd != 0.0)
        space_pressed = keys[pygame.K_SPACE]
        is_running = is_moving and space_pressed
        is_walking = is_moving and not space_pressed

        # Target locomotion blend weights
        target_run_weight = 1.0 if is_running else 0.0
        target_walk_weight = 1.0 if is_walking else 0.0

        # Smooth run transition
        if run_weight < target_run_weight:
            run_weight = min(target_run_weight, run_weight + 8.0 * dt)
        elif run_weight > target_run_weight:
            run_weight = max(target_run_weight, run_weight - 4.5 * dt)

        # Smooth walk transition
        if walk_weight < target_walk_weight:
            walk_weight = min(target_walk_weight, walk_weight + 8.0 * dt)
        elif walk_weight > target_walk_weight:
            walk_weight = max(target_walk_weight, walk_weight - 5.0 * dt)

        # Advance stride cadence
        active_loco = max(run_weight, walk_weight)
        if active_loco > 0.001:
            stride_speed = (3.2 * run_weight) + (1.8 * walk_weight * (1.0 - run_weight))
            motion_cycle += dt * max(0.4, stride_speed)

        # Move forward in the direction Carmelito's body is facing
        speed = (RUN_SPEED if is_running else WALK_SPEED) * move_fwd
        cam_x += math.sin(cam_yaw) * speed * dt
        cam_z += math.cos(cam_yaw) * speed * dt

        # Biological head bob during locomotion
        head_bob = math.sin(motion_cycle * 2.0 * math.pi) * (0.04 * run_weight + 0.02 * walk_weight)
        eye_y = head_bob

        # Sync position with network
        norm_x = (cam_x + 12.0) / 24.0 * 0.8 + 0.1
        norm_y = (cam_z + 12.0) / 24.0 * 0.8 + 0.1
        net.update_local_state(norm_x, norm_y, is_running, mouth_open, is_walking=is_walking, rot_y=cam_yaw)

        connected, is_host, my_id, my_color, remote_players = net.get_snapshot()

        # Update remote player positions in 3D space
        for pid in list(remote_world_pos.keys()):
            if pid not in remote_players:
                remote_world_pos.pop(pid, None)

        remote_alpha = 1.0 - math.exp(-REMOTE_LERP_SPEED * dt)
        for pid, pdata in remote_players.items():
            tw_x = (pdata["nx"] - 0.1) / 0.8 * 24.0 - 12.0
            tw_z = (pdata["ny"] - 0.1) / 0.8 * 24.0 - 12.0
            if pid not in remote_world_pos:
                remote_world_pos[pid] = [tw_x, tw_z]
            else:
                remote_world_pos[pid][0] += (tw_x - remote_world_pos[pid][0]) * remote_alpha
                remote_world_pos[pid][1] += (tw_z - remote_world_pos[pid][1]) * remote_alpha

        # --- 1. RENDER WHAT CARMELITO IS SEEING THROUGH HIS EYES (MAIN VIEW) ---
        screen.fill(BG_COLOR)

        focal = win_w * 0.75
        cos_yaw = math.cos(total_yaw)
        sin_yaw = math.sin(total_yaw)
        cos_pitch = math.cos(total_pitch)
        sin_pitch = math.sin(total_pitch)

        # 3D GROUND GRID (Perspective grid responding to head yaw & upward tilt)
        def clip_and_project_line(
            p1: tuple[float, float, float],
            p2: tuple[float, float, float],
        ) -> tuple[tuple[int, int], tuple[int, int]] | None:
            # Point 1: camera space yaw rotation
            dx1, dy1, dz1 = p1[0] - cam_x, p1[1] - eye_y, p1[2] - cam_z
            rx1 = dx1 * cos_yaw - dz1 * sin_yaw
            rz1 = dx1 * sin_yaw + dz1 * cos_yaw
            ry1 = dy1

            # Point 1: camera space pitch rotation
            rx1_p = rx1
            ry1_p = ry1 * cos_pitch - rz1 * sin_pitch
            rz1_p = ry1 * sin_pitch + rz1 * cos_pitch

            # Point 2: camera space yaw rotation
            dx2, dy2, dz2 = p2[0] - cam_x, p2[1] - eye_y, p2[2] - cam_z
            rx2 = dx2 * cos_yaw - dz2 * sin_yaw
            rz2 = dx2 * sin_yaw + dz2 * cos_yaw
            ry2 = dy2

            # Point 2: camera space pitch rotation
            rx2_p = rx2
            ry2_p = ry2 * cos_pitch - rz2 * sin_pitch
            rz2_p = ry2 * sin_pitch + rz2 * cos_pitch

            near_z = 0.25
            if rz1_p < near_z and rz2_p < near_z:
                return None

            # Clip line against camera near plane
            if rz1_p < near_z:
                t = (near_z - rz1_p) / (rz2_p - rz1_p)
                rx1_p = rx1_p + t * (rx2_p - rx1_p)
                ry1_p = ry1_p + t * (ry2_p - ry1_p)
                rz1_p = near_z
            elif rz2_p < near_z:
                t = (near_z - rz2_p) / (rz1_p - rz2_p)
                rx2_p = rx2_p + t * (rx1_p - rx2_p)
                ry2_p = ry2_p + t * (ry1_p - ry2_p)
                rz2_p = near_z

            sx1 = win_w * 0.5 + (rx1_p / rz1_p) * focal
            sy1 = win_h * 0.5 - (ry1_p / rz1_p) * focal
            sx2 = win_w * 0.5 + (rx2_p / rz2_p) * focal
            sy2 = win_h * 0.5 - (ry2_p / rz2_p) * focal
            return (round(sx1), round(sy1)), (round(sx2), round(sy2))

        # Dynamically center grid around Carmelito for infinite continuous scrolling
        cx_grid = round(cam_x / GRID_STEP) * GRID_STEP
        cz_grid = round(cam_z / GRID_STEP) * GRID_STEP
        gx_min = cx_grid - GRID_EXTENT
        gx_max = cx_grid + GRID_EXTENT
        gz_min = cz_grid - GRID_EXTENT
        gz_max = cz_grid + GRID_EXTENT

        cur_x = gx_min
        while cur_x <= gx_max:
            seg = clip_and_project_line((cur_x, GROUND_Y, gz_min), (cur_x, GROUND_Y, gz_max))
            if seg:
                pygame.draw.line(screen, GROUND_GRID_COLOR, seg[0], seg[1], 1)
            cur_x += GRID_STEP

        cur_z = gz_min
        while cur_z <= gz_max:
            seg = clip_and_project_line((gx_min, GROUND_Y, cur_z), (gx_max, GROUND_Y, cur_z))
            if seg:
                pygame.draw.line(screen, GROUND_GRID_COLOR, seg[0], seg[1], 1)
            cur_z += GRID_STEP

        # RENDER THE AI COMPANION IN CARMELITO'S 3D FIELD OF VIEW
        for pid, pdata in remote_players.items():
            if pid not in remote_world_pos:
                continue
            rwx, rwz = remote_world_pos[pid]
            # Floating companion directly ahead at eye level
            rwy = 0.0 + 0.12 * math.sin(anim_time * 2.8)

            dx = rwx - cam_x
            dz = rwz - cam_z
            dy = rwy - eye_y

            # 3D Camera yaw rotation
            rx = dx * cos_yaw - dz * sin_yaw
            rz = dx * sin_yaw + dz * cos_yaw
            ry = dy

            # 3D Camera pitch rotation
            rx_p = rx
            ry_p = ry * cos_pitch - rz * sin_pitch
            rz_p = ry * sin_pitch + rz * cos_pitch

            # If the AI companion is in front of Carmelito's eyes (rz_p > 0.25)
            if rz_p > 0.25:
                sx = win_w * 0.5 + (rx_p / rz_p) * focal
                sy = win_h * 0.5 - (ry_p / rz_p) * focal
                radius = max(6, int((0.45 / rz_p) * focal))

                color = pdata.get("color", REMOTE_DOT_COLOR)
                pygame.draw.circle(screen, color, (round(sx), round(sy)), radius)
                pygame.draw.circle(screen, (220, 225, 235), (round(sx), round(sy)), radius + 1, max(1, radius // 8))

        # --- 2. TOP-LEFT CORNER PICTURE: CARMELITO'S LIVE 3D BODY MODEL ---
        # Framed picture in the top left corner:
        # - Body stays facing forward (rot_y = 0.0) so you cannot see his body turn.
        # - Head turns and tilts (head_yaw, head_pitch) following the mouse pointer.
        # - Legs and arms walk & run with smooth animated strides and pumps.
        pic_rect = pygame.Rect(16, 16, 180, 200)
        shadow_rect = pygame.Rect(18, 18, 180, 200)
        pygame.draw.rect(screen, (232, 236, 242), shadow_rect, border_radius=16)
        pygame.draw.rect(screen, (255, 255, 255), pic_rect, border_radius=16)
        pygame.draw.rect(screen, (215, 224, 232), pic_rect, width=2, border_radius=16)

        model_3d.render(
            surface=screen,
            screen_pos=(106, 185),
            scale=72,
            rot_y=0.0,              # Body stays permanently facing front (cant see body turn)
            rot_x=0.06,             # Gentle storybook forward angle
            head_yaw=head_yaw,      # Head turns with mouse!
            head_pitch=head_pitch,  # Head tilts with mouse!
            mouth_open=mouth_open,  # Opens/closes with 'U'
            run_cycle=motion_cycle,
            is_running=is_running,
            run_weight=run_weight,
            is_walking=is_walking,
            walk_weight=walk_weight,
        )

        pygame.display.flip()

    net.stop()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
