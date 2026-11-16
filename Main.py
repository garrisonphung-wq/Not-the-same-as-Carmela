import argparse
import asyncio
import json
import math
import os
import random
import sys
import threading
from typing import Any
from urllib.parse import urlparse

import pygame
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

import server as game_server
from carmelito_3d import COLOR_INK_LINE, Carmelito3D

WINDOW_TITLE = "不一样的卡梅拉"
CHICK_NAME = "卡梅利多"
DEFAULT_SERVER_URL = os.environ.get("GAME_SERVER_URL", "ws://127.0.0.1:8765")

# Pure white sky/background, seamless lush green grass ground (no grid)
BG_COLOR = (255, 255, 255)
GRASS_GROUND_COLOR = (138, 202, 114)
GRASS_SHADOW_COLOR = (108, 170, 84)
GRASS_BLADE_NEAR_DARK = (90, 164, 70)
GRASS_BLADE_NEAR_LIGHT = (108, 182, 86)
GRASS_BLADE_FAR_DARK = (114, 182, 94)
GRASS_BLADE_FAR_LIGHT = (124, 192, 102)

# Giant Island colors (storybook cliffs, beach rim, lush top plateau)
ISLAND_TOP_COLOR = (138, 202, 114)
ISLAND_RIM_SAND = (228, 218, 176)
ISLAND_CLIFF_LIGHT = (182, 154, 122)
ISLAND_CLIFF_DARK = (146, 120, 92)
ISLAND_SHADOW = (118, 96, 74)
OCEAN_WATER_COLOR = (180, 222, 245)
OCEAN_FOAM_COLOR = (235, 248, 255)

LOCAL_DOT_COLOR = (255, 175, 195)
REMOTE_DOT_COLOR = (120, 195, 255)

REMOTE_LERP_SPEED = 18.0
NETWORK_SEND_HZ = 60.0
TARGET_FPS = 60.0
WALK_SPEED = 3.2
RUN_SPEED = 6.8
TURN_SPEED = 2.2

# Normal tall human eye height / island top ground height
GROUND_Y = -3.0
CARMELITO_WORLD_SCALE = 1.85  # Matches Carmelito's ~3.0 eye height above GROUND_Y

# Multi-ring grass blade distribution reaching far across the meadow:
# (patch_step, min_dist, max_dist, tufts_per_patch, blade_scale, sway_amp)
GRASS_RINGS = (
    (2.0, 0.0, 24.0, 4, 1.0, 1.0),
    (4.0, 24.0, 64.0, 4, 1.4, 0.6),
    (8.0, 64.0, 140.0, 3, 2.1, 0.0),
)

# Giant Island geometry constants - EVEN MORE GIANT!
ISLAND_RADIUS = 112.0     # Double the size for an expansive, colossal storybook island
ISLAND_SEGMENTS = 72      # Smoother organic shoreline for the colossal island
ISLAND_CLIFF_DEPTH = 28.0 # Taller rock cliffs plunging into the sea
ISLAND_WATER_Y = GROUND_Y - ISLAND_CLIFF_DEPTH

# Fixed overview camera: true top-down view looking directly down at the top of the island
OVERVIEW_CAM_X = 0.0
OVERVIEW_CAM_Y = 295.0    # High above island center for a full bird's-eye view of the top
OVERVIEW_CAM_Z = 24.0     # Positioned so island is centered below title and play buttons
OVERVIEW_CAM_YAW = 0.0    # Fixed north orientation
OVERVIEW_CAM_PITCH = math.radians(-89.9)  # Looking straight down at the top of the island

# Anatomical neck rotation limits (less than 90 degrees sideways, can look up to sky & down at feet)
MAX_HEAD_YAW = math.radians(72.0)        # ~72 degrees max turn left/right (close to sideways, but less than sideways)
MAX_HEAD_PITCH_UP = math.radians(52.0)   # ~52 degrees max upward tilt
MAX_HEAD_PITCH_DOWN = math.radians(68.0) # ~68 degrees chin-down tilt so you can see your own feet
HEAD_SMOOTH_SPEED = 14.0                 # Smooth realistic neck following rate

_CHINESE_FONT_PATH: str | None = None
_CHINESE_FONT_SEARCHED = False
_CHINESE_FONT_CACHE: dict[int, pygame.font.Font] = {}
_NAMEPLATE_CACHE: dict[tuple[str, int, tuple[int, int, int], tuple[int, int, int]], pygame.Surface] = {}
_OUTLINED_TEXT_CACHE: dict[tuple[str, int, int], pygame.Surface] = {}


def get_chinese_font(size: int) -> pygame.font.Font:
    global _CHINESE_FONT_PATH, _CHINESE_FONT_SEARCHED
    if not _CHINESE_FONT_SEARCHED:
        _CHINESE_FONT_SEARCHED = True
        for candidate in (
            "pingfang",
            "hiraginosansgb",
            "stheitimedium",
            "songti",
            "arialunicode",
            "notosanscjksc",
            "microsoftyahei",
            "simhei",
        ):
            matched = pygame.font.match_font(candidate)
            if matched:
                _CHINESE_FONT_PATH = matched
                break

    if size not in _CHINESE_FONT_CACHE:
        if _CHINESE_FONT_PATH:
            _CHINESE_FONT_CACHE[size] = pygame.font.Font(_CHINESE_FONT_PATH, size)
        else:
            _CHINESE_FONT_CACHE[size] = pygame.font.SysFont(
                "PingFang SC,Hiragino Sans GB,STHeiti,Microsoft YaHei,SimHei", size
            )
    return _CHINESE_FONT_CACHE[size]


def get_nameplate_surface(
    text: str,
    font_size: int,
    text_color: tuple[int, int, int] = COLOR_INK_LINE,
    border_color: tuple[int, int, int] = (215, 224, 232),
) -> pygame.Surface:
    key = (text, font_size, text_color, border_color)
    cached = _NAMEPLATE_CACHE.get(key)
    if cached is not None:
        return cached

    font = get_chinese_font(font_size)
    txt_surf = font.render(text, True, text_color)
    pad_x = max(6, round(font_size * 0.42))
    pad_y = max(2, round(font_size * 0.16))
    pill_w = txt_surf.get_width() + pad_x * 2
    pill_h = txt_surf.get_height() + pad_y * 2

    badge = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
    pygame.draw.rect(badge, (255, 255, 255, 232), badge.get_rect(), border_radius=max(6, pill_h // 2))
    pygame.draw.rect(badge, (*border_color, 235), badge.get_rect(), width=1, border_radius=max(6, pill_h // 2))
    badge.blit(txt_surf, (pad_x, pad_y))
    _NAMEPLATE_CACHE[key] = badge
    return badge


def draw_chat_bubble(
    surface: pygame.Surface,
    text: str,
    center_x: int,
    bottom_y: int,
    font_size: int,
    alpha: float,
    tail_direction: str = "down",
) -> int:
    """
    Draws a cute storybook chat bubble with rounded corners and a small tail.
    Returns the total height of the bubble so stacked bubbles can offset upward.
    """
    if alpha <= 0.01:
        return 0

    font = get_chinese_font(font_size)
    txt_surf = font.render(text, True, (35, 42, 50))
    pad_x = max(12, round(font_size * 0.6))
    pad_y = max(8, round(font_size * 0.4))
    bw = txt_surf.get_width() + pad_x * 2
    bh = txt_surf.get_height() + pad_y * 2
    tail_h = max(6, round(font_size * 0.28))
    tail_w = max(8, round(font_size * 0.38))

    bubble_surf = pygame.Surface((bw + 8, bh + tail_h + 8), pygame.SRCALPHA)
    rect = pygame.Rect(4, 4, bw, bh)
    alpha_byte = max(0, min(255, round(255 * alpha)))

    # Bubble background & outline
    pygame.draw.rect(bubble_surf, (255, 255, 255, min(245, alpha_byte)), rect, border_radius=max(8, bh // 3))
    pygame.draw.rect(bubble_surf, (70, 85, 105, min(230, alpha_byte)), rect, width=2, border_radius=max(8, bh // 3))

    # Tail pointing toward speaker
    if tail_direction == "down":
        tail_tip = (4 + bw // 2, 4 + bh + tail_h)
        tail_left = (4 + bw // 2 - tail_w, 4 + bh - 1)
        tail_right = (4 + bw // 2 + tail_w, 4 + bh - 1)
        pygame.draw.polygon(bubble_surf, (255, 255, 255, min(245, alpha_byte)), [tail_left, tail_tip, tail_right])
        pygame.draw.line(bubble_surf, (70, 85, 105, min(230, alpha_byte)), tail_left, tail_tip, 2)
        pygame.draw.line(bubble_surf, (70, 85, 105, min(230, alpha_byte)), tail_tip, tail_right, 2)
    elif tail_direction == "up":
        tail_tip = (4 + bw // 2, 4 - tail_h + 2)
        tail_left = (4 + bw // 2 - tail_w, 4 + 1)
        tail_right = (4 + bw // 2 + tail_w, 4 + 1)
        pygame.draw.polygon(bubble_surf, (255, 255, 255, min(245, alpha_byte)), [tail_left, tail_tip, tail_right])
        pygame.draw.line(bubble_surf, (70, 85, 105, min(230, alpha_byte)), tail_left, tail_tip, 2)
        pygame.draw.line(bubble_surf, (70, 85, 105, min(230, alpha_byte)), tail_tip, tail_right, 2)

    # Text blit with alpha
    txt_surf.set_alpha(alpha_byte)
    bubble_surf.blit(txt_surf, (4 + pad_x, 4 + pad_y))

    blit_x = center_x - bubble_surf.get_width() // 2
    blit_y = bottom_y - bubble_surf.get_height()
    surface.blit(bubble_surf, (blit_x, blit_y))
    return bh + tail_h + 6


def get_outlined_text_surface(text: str, font_size: int, outline_px: int = 4) -> pygame.Surface:
    key = (text, font_size, outline_px)
    cached = _OUTLINED_TEXT_CACHE.get(key)
    if cached is not None:
        return cached

    font = get_chinese_font(font_size)
    fill_surf = font.render(text, True, (255, 255, 255))
    outline_surf = font.render(text, True, (0, 0, 0))

    w = fill_surf.get_width() + outline_px * 2
    h = fill_surf.get_height() + outline_px * 2
    surf = pygame.Surface((w, h), pygame.SRCALPHA)

    r2 = outline_px * outline_px + 1
    for dy in range(-outline_px, outline_px + 1):
        for dx in range(-outline_px, outline_px + 1):
            if dx == 0 and dy == 0:
                continue
            if dx * dx + dy * dy <= r2:
                surf.blit(outline_surf, (outline_px + dx, outline_px + dy))

    surf.blit(fill_surf, (outline_px, outline_px))
    _OUTLINED_TEXT_CACHE[key] = surf
    return surf


def wrap_angle(angle: float) -> float:
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


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
    def __init__(
        self,
        server_url: str = DEFAULT_SERVER_URL,
        auto_host: bool = True,
        is_online: bool = True,
    ) -> None:
        self.server_url = server_url
        self.auto_host = auto_host

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._host_started = False
        self._is_online = is_online

        self.connected = False
        self.is_host = False
        self.my_id: int | None = None
        self.my_color = LOCAL_DOT_COLOR

        self.remote_players: dict[int, dict[str, Any]] = {}

        self._local_nx = 0.5
        self._local_ny = 0.4
        self._local_wx = 0.0
        self._local_wz = -3.5
        self._local_running = False
        self._local_walking = False
        self._local_mouth = False
        self._local_blink = False
        self._local_rot_y = 0.0
        self._local_head_yaw = 0.0
        self._local_head_pitch = 0.0
        self._pos_dirty = True

        self._outgoing_chats: list[str] = []
        self._incoming_chats: list[dict[str, Any]] = []

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def set_online(self, online: bool = True) -> None:
        with self._lock:
            self._is_online = online
            self._pos_dirty = True

    @property
    def is_online(self) -> bool:
        with self._lock:
            return self._is_online

    def update_local_state(
        self,
        nx: float,
        ny: float,
        is_running: bool,
        mouth_open: bool,
        is_walking: bool = False,
        rot_y: float = 0.0,
        wx: float = 0.0,
        wz: float = 0.0,
        head_yaw: float = 0.0,
        head_pitch: float = 0.0,
        blink: bool = False,
    ) -> None:
        nx = max(0.05, min(0.95, nx))
        ny = max(0.05, min(0.95, ny))
        with self._lock:
            pos_changed = (
                (abs(nx - self._local_nx) > 0.0001)
                or (abs(ny - self._local_ny) > 0.0001)
                or (abs(wx - self._local_wx) > 0.002)
                or (abs(wz - self._local_wz) > 0.002)
            )
            state_changed = (
                (is_running != self._local_running)
                or (is_walking != self._local_walking)
                or (mouth_open != self._local_mouth)
                or (blink != self._local_blink)
                or (abs(rot_y - self._local_rot_y) > 0.01)
                or (abs(head_yaw - self._local_head_yaw) > 0.01)
                or (abs(head_pitch - self._local_head_pitch) > 0.01)
            )
            if pos_changed or state_changed:
                self._local_nx = nx
                self._local_ny = ny
                self._local_wx = wx
                self._local_wz = wz
                self._local_running = is_running
                self._local_walking = is_walking
                self._local_mouth = mouth_open
                self._local_blink = blink
                self._local_rot_y = rot_y
                self._local_head_yaw = head_yaw
                self._local_head_pitch = head_pitch
                self._pos_dirty = True

    def get_snapshot(self) -> tuple[bool, bool, int | None, tuple[int, int, int], dict[int, dict[str, Any]]]:
        with self._lock:
            players_copy = {
                pid: {
                    "nx": data["nx"],
                    "ny": data["ny"],
                    "wx": data.get("wx"),
                    "wz": data.get("wz"),
                    "running": data.get("running", False),
                    "walking": data.get("walking", False),
                    "mouth": data.get("mouth", False),
                    "blink": data.get("blink", False),
                    "rot_y": data.get("rot_y", 0.0),
                    "head_yaw": data.get("head_yaw", 0.0),
                    "head_pitch": data.get("head_pitch", 0.0),
                    "color": data["color"],
                    "name": data.get("name"),
                    "chick_name": data.get("chick_name") or CHICK_NAME,
                    "is_carmelito": data.get("is_carmelito", True),
                }
                for pid, data in self.remote_players.items()
            }
            return self.connected, self.is_host, self.my_id, self.my_color, players_copy

    def send_chat(self, text: str) -> None:
        clean_text = str(text).strip()[:100]
        if clean_text:
            with self._lock:
                self._outgoing_chats.append(clean_text)

    def fetch_new_chats(self) -> list[dict[str, Any]]:
        with self._lock:
            if not self._incoming_chats:
                return []
            chats = list(self._incoming_chats)
            self._incoming_chats.clear()
            return chats

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
                    tasks = [
                        asyncio.create_task(self._receiver_loop(ws)),
                        asyncio.create_task(self._sender_loop(ws)),
                    ]
                    done, pending = await asyncio.wait(
                        tasks,
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
            out_chats = []
            with self._lock:
                if self._outgoing_chats:
                    out_chats = list(self._outgoing_chats)
                    self._outgoing_chats.clear()

            for c_text in out_chats:
                try:
                    await ws.send(json.dumps({"type": "chat", "text": c_text, "name": CHICK_NAME}))
                except Exception:
                    pass

            payload = None
            with self._lock:
                if self._is_online and self._pos_dirty:
                    payload = json.dumps(
                        {
                            "type": "pos",
                            "x": round(self._local_nx, 5),
                            "y": round(self._local_ny, 5),
                            "wx": round(self._local_wx, 4),
                            "wz": round(self._local_wz, 4),
                            "running": self._local_running,
                            "walking": self._local_walking,
                            "mouth": self._local_mouth,
                            "blink": self._local_blink,
                            "rot_y": round(self._local_rot_y, 4),
                            "head_yaw": round(self._local_head_yaw, 4),
                            "head_pitch": round(self._local_head_pitch, 4),
                            "is_carmelito": True,
                            "chick_name": CHICK_NAME,
                        },
                        separators=(",", ":"),
                    )
                    self._pos_dirty = False
            if payload is not None:
                await ws.send(payload)
            await asyncio.sleep(interval)

    @staticmethod
    def _parse_remote_player(pdata: dict[str, Any]) -> dict[str, Any]:
        nx = float(pdata.get("x", 0.5))
        ny = float(pdata.get("y", 0.5))
        raw_color = pdata.get("color", REMOTE_DOT_COLOR)
        return {
            "nx": nx,
            "ny": ny,
            "wx": float(pdata["wx"]) if "wx" in pdata else None,
            "wz": float(pdata["wz"]) if "wz" in pdata else None,
            "running": bool(pdata.get("running", False)),
            "walking": bool(pdata.get("walking", False)),
            "mouth": bool(pdata.get("mouth", False)),
            "blink": bool(pdata.get("blink", False)),
            "rot_y": float(pdata.get("rot_y", 0.0)),
            "head_yaw": float(pdata.get("head_yaw", 0.0)),
            "head_pitch": float(pdata.get("head_pitch", 0.0)),
            "color": tuple(int(c) for c in raw_color),
            "name": pdata.get("name"),
            "chick_name": pdata.get("chick_name") or CHICK_NAME,
            "is_carmelito": bool(pdata.get("is_carmelito", True)),
        }

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
                        self.remote_players[pid] = self._parse_remote_player(pdata)

            elif msg_type == "join":
                pid = int(msg["id"])
                with self._lock:
                    if pid != self.my_id:
                        self.remote_players[pid] = self._parse_remote_player(msg)

            elif msg_type == "pos":
                pid = int(msg["id"])
                with self._lock:
                    if pid != self.my_id and pid not in self.remote_players:
                        self.remote_players[pid] = self._parse_remote_player(msg)
                    elif pid in self.remote_players:
                        rp = self.remote_players[pid]
                        rp["nx"] = float(msg["x"])
                        rp["ny"] = float(msg["y"])
                        if "wx" in msg:
                            rp["wx"] = float(msg["wx"])
                        if "wz" in msg:
                            rp["wz"] = float(msg["wz"])
                        rp["running"] = bool(msg.get("running", False))
                        rp["walking"] = bool(msg.get("walking", False))
                        rp["mouth"] = bool(msg.get("mouth", False))
                        rp["blink"] = bool(msg.get("blink", False))
                        if "rot_y" in msg:
                            rp["rot_y"] = float(msg["rot_y"])
                        if "head_yaw" in msg:
                            rp["head_yaw"] = float(msg["head_yaw"])
                        if "head_pitch" in msg:
                            rp["head_pitch"] = float(msg["head_pitch"])
                        if "is_carmelito" in msg:
                            rp["is_carmelito"] = bool(msg["is_carmelito"])
                        if "chick_name" in msg and msg["chick_name"]:
                            rp["chick_name"] = msg["chick_name"]
                        if "name" in msg and msg["name"]:
                            rp["name"] = msg["name"]

            elif msg_type == "leave":
                pid = int(msg["id"])
                with self._lock:
                    self.remote_players.pop(pid, None)

            elif msg_type == "chat":
                with self._lock:
                    self._incoming_chats.append(msg)


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

    anim_time = 0.0
    is_online = False     # You start offline staring down at the island until you click Play

    # Carmelito's ground-level gameplay coordinates
    ground_cam_x = 0.0
    ground_cam_z = -3.5
    ground_cam_yaw = 0.0

    # Current camera variables (initialized to overview camera)
    cam_x = OVERVIEW_CAM_X
    cam_y = OVERVIEW_CAM_Y
    cam_z = OVERVIEW_CAM_Z
    cam_yaw = OVERVIEW_CAM_YAW
    head_yaw = 0.0
    head_pitch = OVERVIEW_CAM_PITCH

    # Offline overview rotation state (turned by dragging left mouse)
    overview_yaw = 0.0
    is_dragging_island = False
    drag_start_pos: tuple[int, int] | None = None

    mouth_open = False

    # Natural automatic blinking + manual 'B' key blinking (for online player mode)
    blink_amount = 0.0
    blink_hold_timer = 0.0
    auto_blink_timer = random.uniform(2.2, 4.2)

    # Locomotion states & smooth weights
    run_weight = 0.0      # 0.0 = not running, 1.0 = full sprint
    walk_weight = 0.0     # 0.0 = not walking, 1.0 = full walk
    motion_cycle = 0.0    # Continuous stride cadence

    net = NetworkClient(server_url=args.server, auto_host=not args.no_auto_host, is_online=is_online)
    remote_states: dict[int, dict[str, float]] = {}

    play_button_rect = pygame.Rect(0, 0, 10, 10)

    # Chat system state
    is_typing_chat = False
    chat_input_text = ""
    # Active chat bubbles per player: {player_id: [{"text": str, "timer": float, "duration": float}]}
    # Player id -1 represents local player
    chat_bubbles: dict[int, list[dict[str, Any]]] = {}

    running = True
    while running:
        dt = min(clock.tick(TARGET_FPS) / 1000.0, 0.05)
        anim_time += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if is_online and is_typing_chat:
                    if event.key == pygame.K_ESCAPE:
                        # Cancel typing
                        is_typing_chat = False
                        chat_input_text = ""
                    elif event.key == pygame.K_RETURN:
                        # Pressing ENTER sends chat and creates a chat bubble over the player!
                        clean = chat_input_text.strip()
                        if clean:
                            net.send_chat(clean)
                            # Create local chat bubble (duration 5.5s)
                            if -1 not in chat_bubbles:
                                chat_bubbles[-1] = []
                            chat_bubbles[-1].append({"text": clean, "timer": 5.5, "duration": 5.5})
                        is_typing_chat = False
                        chat_input_text = ""
                    elif event.key == pygame.K_BACKSPACE:
                        chat_input_text = chat_input_text[:-1]
                    else:
                        if event.unicode and len(chat_input_text) < 60:
                            chat_input_text += event.unicode
                else:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key in (pygame.K_F11, pygame.K_f):
                        fullscreen = not fullscreen
                        screen = create_window(fullscreen)
                    elif is_online and event.key == pygame.K_SPACE:
                        # Pressing SPACE while in game opens the typing box
                        is_typing_chat = True
                        chat_input_text = ""
                    elif is_online and event.key == pygame.K_u:
                        # Toggle mouth open / close
                        mouth_open = not mouth_open
                    elif is_online and event.key == pygame.K_b:
                        # Trigger a blink on demand (and holding B keeps eyes closed)
                        blink_hold_timer = 0.16
                        auto_blink_timer = random.uniform(2.8, 5.0)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # When clicking the PLAY button in offline mode: equip Carmelito and join the game!
                if not is_online:
                    if play_button_rect.collidepoint(event.pos):
                        is_online = True
                        net.set_online(True)
                        # Transition camera to ground-level Carmelito first-person view
                        cam_x = ground_cam_x
                        cam_z = ground_cam_z
                        cam_yaw = ground_cam_yaw
                        head_yaw = 0.0
                        head_pitch = 0.0
                        is_dragging_island = False
                    else:
                        is_dragging_island = True
                        drag_start_pos = event.pos
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                is_dragging_island = False
                drag_start_pos = None
            elif event.type == pygame.MOUSEMOTION:
                if not is_online and is_dragging_island:
                    # Dragging mouse rotates the island view around its center
                    overview_yaw += event.rel[0] * 0.008

        keys = pygame.key.get_pressed()
        win_w, win_h = screen.get_size()

        # In offline mode: top-down view of the island, rotated by dragging mouse
        if not is_online:
            cam_x = OVERVIEW_CAM_X
            cam_y = OVERVIEW_CAM_Y
            cam_z = OVERVIEW_CAM_Z
            cam_yaw = overview_yaw
            head_yaw = 0.0
            head_pitch = OVERVIEW_CAM_PITCH
            total_yaw = cam_yaw
            total_pitch = head_pitch
            eye_y = cam_y
            blink_amount = 0.0
            is_blinking = False
        else:
            # --- BLINKING (when online: automatic natural blinks + 'B' key manual blink) ---
            auto_blink_timer -= dt
            if auto_blink_timer <= 0.0:
                blink_hold_timer = 0.16
                auto_blink_timer = random.uniform(0.18, 0.28) if random.random() < 0.18 else random.uniform(2.8, 5.0)

            if blink_hold_timer > 0.0:
                blink_hold_timer = max(0.0, blink_hold_timer - dt)

            target_blink = 1.0 if (blink_hold_timer > 0.0 or keys[pygame.K_b]) else 0.0
            if blink_amount < target_blink:
                blink_amount = min(target_blink, blink_amount + 18.0 * dt)
            elif blink_amount > target_blink:
                blink_amount = max(target_blink, blink_amount - 14.0 * dt)
            is_blinking = blink_amount >= 0.45

            # --- HEAD / CAMERA LOOK FOLLOWS MOUSE POINTER ---
            mx, my = pygame.mouse.get_pos()
            norm_mx = (mx - win_w * 0.5) / max(1.0, win_w * 0.5)
            norm_my = (my - win_h * 0.5) / max(1.0, win_h * 0.5)

            target_head_yaw = max(-MAX_HEAD_YAW, min(MAX_HEAD_YAW, norm_mx * MAX_HEAD_YAW))
            if norm_my < 0.0:
                target_head_pitch = -norm_my * MAX_HEAD_PITCH_UP
            else:
                target_head_pitch = -norm_my * MAX_HEAD_PITCH_DOWN
            target_head_pitch = max(-MAX_HEAD_PITCH_DOWN, min(MAX_HEAD_PITCH_UP, target_head_pitch))

            head_alpha = 1.0 - math.exp(-HEAD_SMOOTH_SPEED * dt)
            head_yaw += (target_head_yaw - head_yaw) * head_alpha
            head_pitch += (target_head_pitch - head_pitch) * head_alpha

            # --- VIEW TURNING CONTROLS ---
            turn_input = 0.0
            if not is_typing_chat:
                if keys[pygame.K_LEFT]:
                    turn_input -= 1.0
                if keys[pygame.K_RIGHT]:
                    turn_input += 1.0
            cam_yaw += turn_input * TURN_SPEED * dt

            total_yaw = cam_yaw + head_yaw
            total_pitch = head_pitch

            # --- MOVEMENT CONTROLS (Arrow Up/Down + WASD) ---
            move_fwd = 0.0
            move_side = 0.0
            if not is_typing_chat:
                if keys[pygame.K_UP] or keys[pygame.K_w]:
                    move_fwd += 1.0
                if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                    move_fwd -= 1.0
                if keys[pygame.K_d]:
                    move_side += 1.0
                if keys[pygame.K_a]:
                    move_side -= 1.0

            move_mag = math.hypot(move_fwd, move_side)
            is_moving = move_mag > 0.0
            # Run when shift is held or while moving; space opens chat box
            shift_pressed = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
            is_running = is_moving and shift_pressed
            is_walking = is_moving and not shift_pressed

            target_run_weight = 1.0 if is_running else 0.0
            target_walk_weight = 1.0 if is_walking else 0.0

            if run_weight < target_run_weight:
                run_weight = min(target_run_weight, run_weight + 8.0 * dt)
            elif run_weight > target_run_weight:
                run_weight = max(target_run_weight, run_weight - 4.5 * dt)

            if walk_weight < target_walk_weight:
                walk_weight = min(target_walk_weight, walk_weight + 8.0 * dt)
            elif walk_weight > target_walk_weight:
                walk_weight = max(target_walk_weight, walk_weight - 5.0 * dt)

            active_loco = max(run_weight, walk_weight)
            if active_loco > 0.001:
                stride_speed = (3.2 * run_weight) + (1.8 * walk_weight * (1.0 - run_weight))
                motion_cycle += dt * max(0.4, stride_speed)

            if is_moving:
                fwd_n = move_fwd / move_mag
                side_n = move_side / move_mag
                speed = RUN_SPEED if is_running else WALK_SPEED
                sin_b = math.sin(cam_yaw)
                cos_b = math.cos(cam_yaw)
                cam_x += (sin_b * fwd_n + cos_b * side_n) * speed * dt
                cam_z += (cos_b * fwd_n - sin_b * side_n) * speed * dt

            head_bob = math.sin(motion_cycle * 2.0 * math.pi) * (0.04 * run_weight + 0.02 * walk_weight)
            eye_y = head_bob

            # Sync position & posture with network only if online
            norm_x = max(0.05, min(0.95, (cam_x + 42.0) / 84.0 * 0.9 + 0.05))
            norm_y = max(0.05, min(0.95, (cam_z + 42.0) / 84.0 * 0.9 + 0.05))
            net.update_local_state(
                norm_x,
                norm_y,
                is_running,
                mouth_open,
                is_walking=is_walking,
                rot_y=cam_yaw,
                wx=cam_x,
                wz=cam_z,
                head_yaw=head_yaw,
                head_pitch=head_pitch,
                blink=is_blinking,
            )

        connected, is_host, my_id, my_color, remote_players = net.get_snapshot()

        # Fetch and dispatch incoming chats from remote chickens / players
        for chat_msg in net.fetch_new_chats():
            sender_id = int(chat_msg.get("id", -1))
            c_text = str(chat_msg.get("text", "")).strip()
            if not c_text:
                continue
            # If from someone else or local
            target_pid = -1 if (my_id is not None and sender_id == my_id) else sender_id
            if target_pid not in chat_bubbles:
                chat_bubbles[target_pid] = []
            chat_bubbles[target_pid].append({"text": c_text, "timer": 5.5, "duration": 5.5})

        # Update timers and fade out chat bubbles
        for pid in list(chat_bubbles.keys()):
            for b in chat_bubbles[pid]:
                b["timer"] -= dt
            chat_bubbles[pid] = [b for b in chat_bubbles[pid] if b["timer"] > 0.0]
            if not chat_bubbles[pid]:
                chat_bubbles.pop(pid, None)

        # Update remote player world positions and smooth animation weights
        for pid in list(remote_states.keys()):
            if pid not in remote_players:
                remote_states.pop(pid, None)

        remote_alpha = 1.0 - math.exp(-REMOTE_LERP_SPEED * dt)
        for pid, pdata in remote_players.items():
            if pdata["wx"] is not None and pdata["wz"] is not None:
                tw_x = pdata["wx"]
                tw_z = pdata["wz"]
            else:
                tw_x = (pdata["nx"] - 0.1) / 0.8 * 24.0 - 12.0
                tw_z = (pdata["ny"] - 0.1) / 0.8 * 24.0 - 12.0

            t_rot_y = pdata.get("rot_y", 0.0)
            t_head_yaw = pdata.get("head_yaw", 0.0)
            t_head_pitch = pdata.get("head_pitch", 0.0)
            t_run = 1.0 if pdata.get("running", False) else 0.0
            t_walk = 1.0 if pdata.get("walking", False) else 0.0
            t_blink = 1.0 if pdata.get("blink", False) else 0.0

            if pid not in remote_states:
                remote_states[pid] = {
                    "wx": tw_x,
                    "wz": tw_z,
                    "rot_y": t_rot_y,
                    "head_yaw": t_head_yaw,
                    "head_pitch": t_head_pitch,
                    "run_weight": t_run,
                    "walk_weight": t_walk,
                    "blink_amount": t_blink,
                    "motion_cycle": 0.0,
                }
            else:
                rs = remote_states[pid]
                rs["wx"] += (tw_x - rs["wx"]) * remote_alpha
                rs["wz"] += (tw_z - rs["wz"]) * remote_alpha
                rs["rot_y"] = wrap_angle(rs["rot_y"] + wrap_angle(t_rot_y - rs["rot_y"]) * remote_alpha)
                rs["head_yaw"] += (t_head_yaw - rs["head_yaw"]) * remote_alpha
                rs["head_pitch"] += (t_head_pitch - rs["head_pitch"]) * remote_alpha
                rs["run_weight"] += (t_run - rs["run_weight"]) * min(1.0, 8.0 * dt)
                rs["walk_weight"] += (t_walk - rs["walk_weight"]) * min(1.0, 8.0 * dt)
                if rs["blink_amount"] < t_blink:
                    rs["blink_amount"] = min(t_blink, rs["blink_amount"] + 18.0 * dt)
                elif rs["blink_amount"] > t_blink:
                    rs["blink_amount"] = max(t_blink, rs["blink_amount"] - 14.0 * dt)
                loco = max(rs["run_weight"], rs["walk_weight"])
                if loco > 0.001:
                    stride_spd = (3.2 * rs["run_weight"]) + (1.8 * rs["walk_weight"] * (1.0 - rs["run_weight"]))
                    rs["motion_cycle"] += dt * max(0.4, stride_spd)

        # --- 1. RENDER WHAT YOU SEE: THE GIANT ISLAND, CHICKENS, GRASS, HORIZON ---
        screen.fill(BG_COLOR)

        focal = win_w * 0.75
        hw = win_w * 0.5
        hh = win_h * 0.5
        cos_yaw = math.cos(total_yaw)
        sin_yaw = math.sin(total_yaw)
        cos_pitch = math.cos(total_pitch)
        sin_pitch = math.sin(total_pitch)
        near_z = 0.25
        half_fov_tan = hw / focal

        def to_cam(wx: float, wy: float, wz: float) -> tuple[float, float, float]:
            dx = wx - cam_x
            dy = wy - eye_y
            dz = wz - cam_z
            rx = dx * cos_yaw - dz * sin_yaw
            rz = dx * sin_yaw + dz * cos_yaw
            return (rx, dy * cos_pitch - rz * sin_pitch, dy * sin_pitch + rz * cos_pitch)

        # 1a. Horizon & ground / ocean rendering:
        horizon_y = max(0, min(win_h, round(hh + math.tan(total_pitch) * focal)))

        if is_online:
            # When playing the game, you are standing on the lush green island meadow!
            # The seamless green grass extends all the way to the horizon (no exposed ocean water lines).
            if horizon_y < win_h:
                screen.fill(GRASS_GROUND_COLOR, pygame.Rect(0, horizon_y, win_w, win_h - horizon_y))
        else:
            # In offline overview mode: ocean water surrounds the giant island on all sides
            screen.fill(OCEAN_WATER_COLOR)

            # Render the Giant Island (Top lush plateau, Sandy beach edge, and 3D Rocky Cliffs)
            # Compute island outline vertices at top plateau (GROUND_Y) and water base (ISLAND_WATER_Y)
            top_rim_cam: list[tuple[float, float, float]] = []
            top_rim_scr: list[tuple[int, int] | None] = []
            bot_rim_cam: list[tuple[float, float, float]] = []
            bot_rim_scr: list[tuple[int, int] | None] = []

            for i in range(ISLAND_SEGMENTS):
                ang = (2.0 * math.pi * i) / ISLAND_SEGMENTS
                # Organic island shape with wavy shorelines
                r = ISLAND_RADIUS + 5.5 * math.sin(ang * 4.0) + 3.2 * math.cos(ang * 7.0)
                ix = math.sin(ang) * r
                iz = math.cos(ang) * r

                tc = to_cam(ix, GROUND_Y, iz)
                top_rim_cam.append(tc)
                if tc[2] > near_z:
                    top_rim_scr.append((round(hw + (tc[0] / tc[2]) * focal), round(hh - (tc[1] / tc[2]) * focal)))
                else:
                    top_rim_scr.append(None)

                bc = to_cam(ix * 1.05, ISLAND_WATER_Y, iz * 1.05)
                bot_rim_cam.append(bc)
                if bc[2] > near_z:
                    bot_rim_scr.append((round(hw + (bc[0] / bc[2]) * focal), round(hh - (bc[1] / bc[2]) * focal)))
                else:
                    bot_rim_scr.append(None)

            # Island top plateau lush green surface
            valid_top = [pt for pt in top_rim_scr if pt is not None]
            if len(valid_top) >= 3:
                # Sandy rim stroke
                pygame.draw.polygon(screen, ISLAND_RIM_SAND, valid_top)
                # Lush green plateau fill slightly inset
                pygame.draw.polygon(screen, ISLAND_TOP_COLOR, valid_top)

            # (Sides of the island are omitted so only the lush top of the island is seen)

        # 1c. Render 3D grass blades across the island
        base_sway = math.sin(anim_time * 2.2) * 0.045
        blades: list[tuple[float, float, float, tuple[float, float, float], int, float, float]] = []

        # When staring from overview, render grass patches across the colossal island surface
        for step, min_d, max_d, tufts, b_scale, sway_amp in (
            ((6.0, 0.0, 100.0, 3, 2.0, 0.6), (12.0, 40.0, 140.0, 2, 2.8, 0.0))
            if not is_online
            else GRASS_RINGS
        ):
            ix_c = round(cam_x / step)
            iz_c = round(cam_z / step)
            half_cells = int(max_d / step) + 1
            min_d2 = min_d * min_d
            max_d2 = max_d * max_d
            step_salt = int(step) * 2654435761

            for iz in range(iz_c - half_cells, iz_c + half_cells + 1):
                cz = (iz + 0.5) * step
                dz_c = cz - cam_z
                for ix in range(ix_c - half_cells, ix_c + half_cells + 1):
                    cx = (ix + 0.5) * step
                    dx_c = cx - cam_x
                    d2 = dx_c * dx_c + dz_c * dz_c
                    if d2 < min_d2 or d2 > max_d2:
                        continue
                    # Stay within giant island radius
                    if math.hypot(cx, cz) > ISLAND_RADIUS - 1.5:
                        continue

                    c_cam = to_cam(cx, GROUND_Y, cz)
                    if c_cam[2] < near_z - step:
                        continue
                    if abs(c_cam[0]) > max(near_z, c_cam[2]) * half_fov_tan + step * 1.5:
                        continue

                    for ti in range(tufts):
                        th = ((ix * 374761393) ^ (iz * 668265263) ^ (ti * 1442695041) ^ step_salt) & 0xFFFF
                        fx = ((th & 255) / 255.0) * 0.9 + 0.05
                        fz = (((th >> 8) & 255) / 255.0) * 0.9 + 0.05
                        bx = (ix + fx) * step
                        bz = (iz + fz) * step
                        if math.hypot(bx, bz) > ISLAND_RADIUS - 1.5:
                            continue

                        b_cam = to_cam(bx, GROUND_Y, bz)
                        if b_cam[2] > near_z and abs(b_cam[0]) <= b_cam[2] * half_fov_tan + 0.5:
                            blades.append((b_cam[2], bx, bz, b_cam, th, b_scale, sway_amp))

        blades.sort(key=lambda item: item[0], reverse=True)
        for bz_cam, bx, bz, b_cam, th, b_scale, sway_amp in blades:
            height = (0.22 + ((th >> 4) & 7) * 0.02) * b_scale
            local_sway = (base_sway + math.sin(anim_time * 2.6 + bx * 0.9 + bz * 0.7) * 0.03) * sway_amp
            t_cam = to_cam(bx + local_sway, GROUND_Y + height, bz)
            if t_cam[2] <= near_z:
                continue

            bsx = round(hw + (b_cam[0] / b_cam[2]) * focal)
            bsy = round(hh - (b_cam[1] / b_cam[2]) * focal)
            tsx = round(hw + (t_cam[0] / t_cam[2]) * focal)
            tsy = round(hh - (t_cam[1] / t_cam[2]) * focal)

            blade_col = GRASS_BLADE_NEAR_DARK if (th & 1) else GRASS_BLADE_NEAR_LIGHT
            width = 2 if bz_cam < 36.0 else 1
            pygame.draw.line(screen, blade_col, (bsx, bsy), (tsx, tsy), width)

        # 1d. RENDER CHICKENS / OTHER PLAYERS IN 3D SPACE (with Chinese name "卡梅利多" and player names)
        visible_remotes: list[tuple[float, int, dict[str, Any], dict[str, float], float, float, float]] = []
        for pid, pdata in remote_players.items():
            if pid not in remote_states:
                continue
            rs = remote_states[pid]
            rwx, rwz = rs["wx"], rs["wz"]
            is_carmelito = pdata.get("is_carmelito", True)
            rwy = GROUND_Y if is_carmelito else (0.0 + 0.12 * math.sin(anim_time * 2.8))

            rx_p, ry_p, rz_p = to_cam(rwx, rwy, rwz)
            min_z = 0.65 if is_carmelito else 0.25
            if rz_p > min_z:
                visible_remotes.append((rz_p, pid, pdata, rs, rx_p, ry_p, rz_p))

        visible_remotes.sort(key=lambda item: item[0], reverse=True)
        for _, pid, pdata, rs, rx_p, ry_p, rz_p in visible_remotes:
            sx = hw + (rx_p / rz_p) * focal
            sy = hh - (ry_p / rz_p) * focal

            if pdata.get("is_carmelito", True):
                # Soft shadow on the grass right beneath the Carmelito chick's feet
                sh_w = max(8, round((1.15 / rz_p) * focal))
                sh_h = max(3, round((0.36 / rz_p) * focal))
                shadow_rect = pygame.Rect(round(sx - sh_w * 0.5), round(sy - sh_h * 0.4), sh_w, sh_h)
                pygame.draw.ellipse(screen, GRASS_SHADOW_COLOR, shadow_rect)

                model_scale = (CARMELITO_WORLD_SCALE / rz_p) * focal
                rel_rot_y = math.pi - (rs["rot_y"] - total_yaw)
                rel_rot_x = max(-0.55, min(0.65, 0.04 - total_pitch))

                model_3d.render(
                    surface=screen,
                    screen_pos=(sx, sy),
                    scale=model_scale,
                    rot_y=rel_rot_y,
                    rot_x=rel_rot_x,
                    head_yaw=rs["head_yaw"],
                    head_pitch=rs["head_pitch"],
                    mouth_open=pdata.get("mouth", False),
                    run_cycle=rs["motion_cycle"],
                    is_running=pdata.get("running", False),
                    run_weight=rs["run_weight"],
                    is_walking=pdata.get("walking", False),
                    walk_weight=rs["walk_weight"],
                    blink=rs["blink_amount"],
                )

                # Floating nameplates above Carmelito's comb:
                # 1) Chicken's Chinese name ("卡梅利多")
                # 2) AI / player's name (e.g. "Antigravity (AI)") stacked right above it
                label_cam = to_cam(rs["wx"], GROUND_Y + 2.38 * CARMELITO_WORLD_SCALE, rs["wz"])
                if label_cam[2] > near_z:
                    lsx = round(hw + (label_cam[0] / label_cam[2]) * focal)
                    lsy = round(hh - (label_cam[1] / label_cam[2]) * focal)
                    raw_px = max(13, min(30, round((0.46 / label_cam[2]) * focal)))
                    bucket_px = max(12, min(30, (raw_px // 2) * 2))
                    chick_text = pdata.get("chick_name") or CHICK_NAME
                    chick_badge = get_nameplate_surface(chick_text, bucket_px)
                    chick_y = lsy - chick_badge.get_height() // 2
                    screen.blit(chick_badge, (lsx - chick_badge.get_width() // 2, chick_y))

                    top_badge_y = chick_y
                    player_name = pdata.get("name")
                    if player_name:
                        name_px = max(10, min(24, ((round(bucket_px * 0.78)) // 2) * 2))
                        name_badge = get_nameplate_surface(
                            str(player_name),
                            name_px,
                            text_color=(45, 95, 145),
                            border_color=(175, 210, 240),
                        )
                        gap = max(3, bucket_px // 5)
                        name_y = chick_y - gap - name_badge.get_height()
                        screen.blit(name_badge, (lsx - name_badge.get_width() // 2, name_y))
                        top_badge_y = name_y

                    # Stacking chat bubbles above remote chicken
                    if pid in chat_bubbles:
                        cur_bottom = top_badge_y - 8
                        bubble_font_size = max(14, min(24, bucket_px))
                        # Newer bubbles are at the bottom, older bubbles pushed above
                        for b in reversed(chat_bubbles[pid]):
                            progress = b["timer"] / b["duration"]
                            alpha = min(1.0, progress * 3.0)
                            b_h = draw_chat_bubble(
                                screen,
                                b["text"],
                                center_x=lsx,
                                bottom_y=cur_bottom,
                                font_size=bubble_font_size,
                                alpha=alpha,
                                tail_direction="down",
                            )
                            cur_bottom -= b_h
            else:
                radius = max(6, int((0.45 / rz_p) * focal))
                color = pdata.get("color", REMOTE_DOT_COLOR)
                pygame.draw.circle(screen, color, (round(sx), round(sy)), radius)
                pygame.draw.circle(screen, (220, 225, 235), (round(sx), round(sy)), radius + 1, max(1, radius // 8))

        # 1e. RENDER OWN FEET ONLY WHEN ONLINE
        if is_online and head_pitch < -0.35:
            cos_body = math.cos(cam_yaw)
            sin_body = math.sin(cam_yaw)

            def body_to_cam(bx: float, by: float, bz: float) -> tuple[float, float, float]:
                wx = cam_x + bx * cos_body + bz * sin_body
                wz = cam_z - bx * sin_body + bz * cos_body
                return to_cam(wx, by, wz)

            feet_faces, foot_shadows = model_3d.build_first_person_feet_faces(
                ground_y=GROUND_Y,
                run_cycle=motion_cycle,
                run_weight=run_weight,
                walk_weight=walk_weight,
            )

            for sbx, sby, sbz in foot_shadows:
                scam = body_to_cam(sbx, sby, sbz)
                if scam[2] > near_z:
                    ssx = hw + (scam[0] / scam[2]) * focal
                    ssy = hh - (scam[1] / scam[2]) * focal
                    sh_w = max(10, round((0.68 / scam[2]) * focal))
                    sh_h = max(4, round((0.44 / scam[2]) * focal))
                    pygame.draw.ellipse(
                        screen,
                        GRASS_SHADOW_COLOR,
                        pygame.Rect(round(ssx - sh_w * 0.5), round(ssy - sh_h * 0.5), sh_w, sh_h),
                    )

            feet_projected: list[tuple[float, list[tuple[int, int]], tuple[int, int, int], bool]] = []
            for quad_verts, base_col, has_contour in feet_faces:
                cam_verts = [body_to_cam(*v) for v in quad_verts]
                if any(cv[2] <= near_z for cv in cam_verts):
                    continue

                v0, v1, v2 = cam_verts[0], cam_verts[1], cam_verts[2]
                e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
                e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
                nx = e1[1] * e2[2] - e1[2] * e2[1]
                ny = e1[2] * e2[0] - e1[0] * e2[2]
                nz = e1[0] * e2[1] - e1[1] * e2[0]
                n_mag = math.sqrt(nx * nx + ny * ny + nz * nz)
                if n_mag < 1e-6:
                    continue
                nx /= n_mag
                ny /= n_mag
                nz /= n_mag

                to_eye_dot = -(nx * v0[0] + ny * v0[1] + nz * v0[2])
                if to_eye_dot <= 0.0:
                    continue

                v_mag = math.sqrt(v0[0] * v0[0] + v0[1] * v0[1] + v0[2] * v0[2])
                view_cos = to_eye_dot / max(1e-4, v_mag)

                diffuse = max(0.0, nx * model_3d.light_dir[0] + ny * model_3d.light_dir[1] + nz * model_3d.light_dir[2])
                brightness = 0.76 + 0.24 * diffuse
                face_col = (
                    min(255, int(base_col[0] * brightness)),
                    min(255, int(base_col[1] * brightness)),
                    min(255, int(base_col[2] * brightness)),
                )

                pts = [
                    (round(hw + (cv[0] / cv[2]) * focal), round(hh - (cv[1] / cv[2]) * focal))
                    for cv in cam_verts
                ]
                avg_z = sum(cv[2] for cv in cam_verts) / len(cam_verts)
                feet_projected.append((avg_z, pts, face_col, has_contour and view_cos < 0.34))

            feet_projected.sort(key=lambda item: item[0], reverse=True)
            for _, pts, f_col, draw_ink in feet_projected:
                if len(pts) >= 3:
                    pygame.draw.polygon(screen, f_col, pts)
                    if draw_ink:
                        pygame.draw.polygon(screen, COLOR_INK_LINE, pts, 1)

        # --- 2. TOP-LEFT CORNER PICTURE: ONLY VISIBLE WHEN ONLINE (EQUIPPED CARMELITO) ---
        if is_online:
            pic_rect = pygame.Rect(16, 16, 180, 200)
            shadow_rect = pygame.Rect(18, 18, 180, 200)
            pygame.draw.rect(screen, (232, 236, 242), shadow_rect, border_radius=16)
            pygame.draw.rect(screen, (255, 255, 255), pic_rect, border_radius=16)
            pygame.draw.rect(screen, (215, 224, 232), pic_rect, width=2, border_radius=16)

            model_3d.render(
                surface=screen,
                screen_pos=(106, 185),
                scale=72,
                rot_y=0.0,
                rot_x=0.06,
                head_yaw=head_yaw,
                head_pitch=head_pitch,
                mouth_open=mouth_open,
                run_cycle=motion_cycle,
                is_running=is_running,
                run_weight=run_weight,
                is_walking=is_walking,
                walk_weight=walk_weight,
                blink=blink_amount,
            )

        # --- 2b. CHAT BUBBLES & TYPING BOX FOR LOCAL PLAYER (ON TOP OF ME, NOT THE PICTURE) ---
        if is_online:
            # Stacking chat bubbles for local player (-1):
            # Floating above Carmelito's view (in upper-middle screen area, not over portrait)
            if -1 in chat_bubbles:
                cur_bottom = max(70, round(win_h * 0.28))
                local_font_size = max(18, min(28, round(win_h * 0.032)))
                for b in reversed(chat_bubbles[-1]):
                    progress = b["timer"] / b["duration"]
                    alpha = min(1.0, progress * 3.0)
                    b_h = draw_chat_bubble(
                        screen,
                        b["text"],
                        center_x=win_w // 2,
                        bottom_y=cur_bottom,
                        font_size=local_font_size,
                        alpha=alpha,
                        tail_direction="down",
                    )
                    cur_bottom -= b_h

            # Typing input box at bottom center of screen (opened with Space)
            if is_typing_chat:
                box_w = min(600, win_w - 40)
                box_h = 44
                box_x = (win_w - box_w) // 2
                box_y = win_h - box_h - 24

                # Box background & outline
                box_rect = pygame.Rect(box_x, box_y, box_w, box_h)
                s_rect = pygame.Rect(box_x + 2, box_y + 2, box_w, box_h)
                pygame.draw.rect(screen, (0, 0, 0, 50), s_rect, border_radius=12)
                pygame.draw.rect(screen, (255, 255, 255, 245), box_rect, border_radius=12)
                pygame.draw.rect(screen, (70, 130, 210), box_rect, width=2, border_radius=12)

                # Cursor blinking
                cursor_visible = (int(anim_time * 2.5) % 2) == 0
                display_txt = chat_input_text + ("|" if cursor_visible else "")
                font_chat = get_chinese_font(20)
                if not chat_input_text:
                    prompt_surf = font_chat.render("说点什么... (按Enter发送，Esc取消)", True, (155, 165, 175))
                    screen.blit(prompt_surf, (box_x + 14, box_y + (box_h - prompt_surf.get_height()) // 2))
                else:
                    txt_surf = font_chat.render(display_txt, True, (25, 30, 40))
                    screen.blit(txt_surf, (box_x + 14, box_y + (box_h - txt_surf.get_height()) // 2))

        # --- 3. TITLE SCREEN UI OVERLAYS (ONLY VISIBLE WHEN OFFLINE, DISAPPEARS ON JOIN) ---
        if not is_online:
            # 3a. Game title at top center: white text with black outline
            title_px = max(36, min(88, ((round(win_h * 0.085)) // 2) * 2))
            title_outline_px = max(2, round(title_px * 0.065))
            title_surf = get_outlined_text_surface(WINDOW_TITLE, title_px, outline_px=title_outline_px)
            title_x = (win_w - title_surf.get_width()) // 2
            title_y = max(14, round(win_h * 0.03))
            screen.blit(title_surf, (title_x, title_y))

            # 3b. PLAY button: white text with black outline positioned neatly below the title text
            play_px = max(24, min(52, ((round(title_px * 0.52)) // 2) * 2))
            play_outline_px = max(2, round(play_px * 0.07))
            play_surf = get_outlined_text_surface("PLAY", play_px, outline_px=play_outline_px)
            play_x = (win_w - play_surf.get_width()) // 2
            play_gap = max(24, round(win_h * 0.05))
            play_y = title_y + title_surf.get_height() + play_gap

            # Store the clickable boundary of the PLAY text button
            play_button_rect = pygame.Rect(
                play_x - 10,
                play_y - 6,
                play_surf.get_width() + 20,
                play_surf.get_height() + 12,
            )
            screen.blit(play_surf, (play_x, play_y))

        pygame.display.flip()

    net.stop()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
