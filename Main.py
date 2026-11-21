import argparse
import asyncio
import json
import math
import os
import random
import sys
import threading
import time
from typing import Any
from urllib.parse import urlparse

# Enable native OS IME candidate window (e.g. macOS Chinese Pinyin via Fn/Globe key)
os.environ.setdefault("SDL_IME_SHOW_UI", "1")

import pygame
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

import server as game_server
from carmelito_3d import COLOR_INK_LINE, COLOR_XIAOLIUZI_INK, Carmelito3D, ChickRagdollSim
from pinyin_ime import lookup_pinyin

WINDOW_TITLE = "不一样的卡梅拉"
CHICK_NAME = "卡梅利多"
CARMEN_NAME = "卡门"
PANGDUN_NAME = "小胖墩"
XIAOLIUZI_NAME = "小六子"
DEFAULT_SERVER_URL = os.environ.get("GAME_SERVER_URL", "ws://127.0.0.1:8765")

# Storybook light sky blue sky/background, seamless lush green grass ground (no grid)
SKY_BLUE_COLOR = (175, 225, 252)  # Bright, soft, lighter storybook sky blue
SKY_CLOUD_WHITE = (255, 255, 255)
SKY_CLOUD_SHADOW = (222, 238, 250)
BG_COLOR = SKY_BLUE_COLOR
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
    (2.0, 0.0, 32.0, 4, 1.0, 1.0),
    (5.0, 32.0, 110.0, 4, 1.4, 0.6),
    (12.0, 110.0, 240.0, 3, 2.2, 0.2),
    (24.0, 240.0, 480.0, 2, 3.2, 0.0),
)

# Giant Island geometry constants - COLORADO SIZE (269,837 km²)!
# Colorado dimensions: ~610 km East-West x 450 km North-South -> Equivalent radius ~295,000 meters!
COLORADO_RADIUS_KM = 295.0
ISLAND_RADIUS = 295000.0   # 295 km radius = same area as Colorado (269,837 km²)!
ISLAND_SEGMENTS = 128     # Smooth perimeter for the continent-sized island
ISLAND_CLIFF_DEPTH = 380.0 # Colossal coastal bluffs plunging into the ocean
ISLAND_WATER_Y = GROUND_Y - ISLAND_CLIFF_DEPTH

# Overview camera: satellite/orbital view looking directly down at the top of the Colorado island
OVERVIEW_CAM_X = 0.0
OVERVIEW_CAM_Y = 780000.0  # 780 km altitude in low Earth orbit to view all of Colorado below!
OVERVIEW_CAM_Z = 65000.0   # Perfectly centered below title and character carousel
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


def get_outlined_text_surface(
    text: str,
    font_size: int,
    outline_px: int = 4,
    fill_color: tuple[int, int, int] = (255, 255, 255),
    outline_color: tuple[int, int, int] = (0, 0, 0),
) -> pygame.Surface:
    key = (text, font_size, outline_px, fill_color, outline_color)
    cached = _OUTLINED_TEXT_CACHE.get(key)
    if cached is not None:
        return cached

    font = get_chinese_font(font_size)
    fill_surf = font.render(text, True, fill_color)
    outline_surf = font.render(text, True, outline_color)

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



def resolve_character_id(pdata: dict) -> str:
    c = (pdata.get("character") or "").strip().lower()
    if c in ("carmen", "卡门"):
        return "carmen"
    if c in ("pangdun", "小胖墩", "belino", "coquenpate"):
        return "pangdun"
    if c in ("xiaoliuzi", "小六子", "coqsix", "克西斯"):
        return "xiaoliuzi"
    if c:
        return c
    cn = (pdata.get("chick_name") or "").strip()
    if cn in ("卡门", "Carmen"):
        return "carmen"
    if cn in ("小胖墩", "Belino", "Coquenpâte"):
        return "pangdun"
    if cn in ("小六子", "Coqsix", "克西斯"):
        return "xiaoliuzi"
    return "carmelito"


def wrap_text_lines(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Wrap mixed Chinese/English text into lines fitting within max_width pixels."""
    if not text:
        return [""]
    lines: list[str] = []
    cur_line = ""
    for ch in text:
        test_line = cur_line + ch
        if font.size(test_line)[0] <= max_width or not cur_line:
            cur_line = test_line
        else:
            lines.append(cur_line)
            cur_line = ch
    if cur_line:
        lines.append(cur_line)
    return lines


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
        self.chick_name = CHICK_NAME
        self.character_id = "carmelito"

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
        self._local_rot_z = 0.0
        self._local_lay_pitch = 0.0
        self._local_ragdoll = 0.0
        self._local_head_yaw = 0.0
        self._local_head_pitch = 0.0
        self._local_kick_amount = 0.0
        self._local_kick_side = 1.0
        self._local_punch_amount = 0.0
        self._local_punch_side = 1.0
        self._local_jump_offset_y = 0.0
        self._local_jump_amount = 0.0
        self._local_tag_amount = 0.0
        self._pos_dirty = True

        self._outgoing_chats: list[str] = []
        self._incoming_chats: list[dict[str, Any]] = []
        self._outgoing_kick_hits: list[dict[str, Any]] = []
        self._incoming_kick_hits: list[dict[str, Any]] = []
        self._outgoing_punch_hits: list[dict[str, Any]] = []
        self._incoming_punch_hits: list[dict[str, Any]] = []

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def set_character(self, character_id: str, chick_name: str) -> None:
        with self._lock:
            self.character_id = character_id
            self.chick_name = chick_name
            self._pos_dirty = True

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
        rot_z: float = 0.0,
        lay_pitch: float = 0.0,
        ragdoll: float = 0.0,
        wx: float = 0.0,
        wz: float = 0.0,
        head_yaw: float = 0.0,
        head_pitch: float = 0.0,
        blink: bool = False,
        kick_amount: float = 0.0,
        kick_side: float = 1.0,
        punch_amount: float = 0.0,
        punch_side: float = 1.0,
        jump_offset_y: float = 0.0,
        jump_amount: float = 0.0,
        tag_amount: float = 0.0,
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
                or (abs(rot_z - self._local_rot_z) > 0.01)
                or (abs(lay_pitch - self._local_lay_pitch) > 0.01)
                or (abs(ragdoll - self._local_ragdoll) > 0.02)
                or (abs(head_yaw - self._local_head_yaw) > 0.01)
                or (abs(head_pitch - self._local_head_pitch) > 0.01)
                or (abs(kick_amount - self._local_kick_amount) > 0.02)
                or (kick_side != self._local_kick_side)
                or (abs(punch_amount - self._local_punch_amount) > 0.02)
                or (punch_side != self._local_punch_side)
                or (abs(jump_offset_y - self._local_jump_offset_y) > 0.02)
                or (abs(jump_amount - self._local_jump_amount) > 0.02)
                or (abs(tag_amount - self._local_tag_amount) > 0.02)
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
                self._local_rot_z = rot_z
                self._local_lay_pitch = lay_pitch
                self._local_ragdoll = ragdoll
                self._local_head_yaw = head_yaw
                self._local_head_pitch = head_pitch
                self._local_kick_amount = kick_amount
                self._local_kick_side = kick_side
                self._local_punch_amount = punch_amount
                self._local_punch_side = punch_side
                self._local_jump_offset_y = jump_offset_y
                self._local_jump_amount = jump_amount
                self._local_tag_amount = tag_amount
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
                    "rot_z": data.get("rot_z", 0.0),
                    "lay_pitch": data.get("lay_pitch", 0.0),
                    "ragdoll": data.get("ragdoll", 0.0),
                    "head_yaw": data.get("head_yaw", 0.0),
                    "head_pitch": data.get("head_pitch", 0.0),
                    "color": data["color"],
                    "name": data.get("name"),
                    "chick_name": data.get("chick_name") or CHICK_NAME,
                    "character": data.get("character"),
                    "is_carmelito": data.get("is_carmelito", True),
                    "kick_amount": data.get("kick_amount", 0.0),
                    "kick_side": data.get("kick_side", 1.0),
                    "punch_amount": data.get("punch_amount", 0.0),
                    "punch_side": data.get("punch_side", 1.0),
                    "jump_offset_y": data.get("jump_offset_y", 0.0),
                    "jump_amount": data.get("jump_amount", 0.0),
                    "tag_amount": data.get("tag_amount", 0.0),
                }
                for pid, data in self.remote_players.items()
            }
            return self.connected, self.is_host, self.my_id, self.my_color, players_copy

    def send_punch_hit(self, target_id: int, dir_x: float, dir_z: float, headshot: bool, punch_side: float = 1.0) -> None:
        with self._lock:
            self._outgoing_punch_hits.append({
                "type": "punch_hit",
                "target_id": int(target_id),
                "dir_x": round(dir_x, 4),
                "dir_z": round(dir_z, 4),
                "headshot": bool(headshot),
                "punch_side": 1.0 if punch_side >= 0.0 else -1.0,
            })

    def pop_incoming_punch_hits(self) -> list[dict[str, Any]]:
        with self._lock:
            if not self._incoming_punch_hits:
                return []
            out = list(self._incoming_punch_hits)
            self._incoming_punch_hits.clear()
            return out

    def send_kick_hit(self, target_id: int, dir_x: float, dir_z: float, launch: bool, roll_dir: float) -> None:
        with self._lock:
            self._outgoing_kick_hits.append(
                {
                    "type": "kick_hit",
                    "target_id": int(target_id),
                    "dir_x": round(float(dir_x), 4),
                    "dir_z": round(float(dir_z), 4),
                    "launch": bool(launch),
                    "roll_dir": 1.0 if roll_dir >= 0.0 else -1.0,
                }
            )

    def pop_incoming_kick_hits(self) -> list[dict[str, Any]]:
        with self._lock:
            if not self._incoming_kick_hits:
                return []
            hits = list(self._incoming_kick_hits)
            self._incoming_kick_hits.clear()
            return hits

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

        # Launch exactly 1 intelligent, companion AI chick player into the game!
        ai_chick_configs = [
            # Carmen: witty, clever companion chick who runs, jumps, kicks, punches, and chats
            {"name": "卡门 (AI)", "character": "carmen", "chick_name": "卡门", "delay": 0.5},
        ]

        def launch_single_ai(cfg: dict[str, Any]) -> None:
            time.sleep(cfg["delay"])
            try:
                import ai_player
                # Spawn in a pleasant nearby view in front of the player (around 6-9 meters away)
                spawn_theta = random.uniform(-0.45, 0.45)
                spawn_r = random.uniform(5.5, 9.0)
                rand_x = math.sin(spawn_theta) * spawn_r
                rand_z = math.cos(spawn_theta) * spawn_r

                bot = ai_player.AICodeCompanion(
                    server_url=f"ws://127.0.0.1:{port}",
                    name=cfg["name"],
                    character=cfg["character"],
                    chick_name=cfg["chick_name"],
                    auto_host=False,
                )
                bot.wx = rand_x
                bot.wz = rand_z
                bot.dest_x = rand_x
                bot.dest_z = rand_z
                asyncio.run(bot.run())
            except Exception:
                pass

        for cfg in ai_chick_configs:
            threading.Thread(target=launch_single_ai, args=(cfg,), daemon=True).start()

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
                    await ws.send(json.dumps({"type": "chat", "text": c_text, "name": self.chick_name}))
                except Exception:
                    pass

            out_kicks = []
            with self._lock:
                if self._outgoing_kick_hits:
                    out_kicks = list(self._outgoing_kick_hits)
                    self._outgoing_kick_hits.clear()

            for k_evt in out_kicks:
                try:
                    await ws.send(json.dumps(k_evt, separators=(",", ":")))
                except Exception:
                    pass

            out_punches = []
            with self._lock:
                if self._outgoing_punch_hits:
                    out_punches = list(self._outgoing_punch_hits)
                    self._outgoing_punch_hits.clear()

            for p_evt in out_punches:
                try:
                    await ws.send(json.dumps(p_evt, separators=(",", ":")))
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
                            "rot_z": round(self._local_rot_z, 4),
                            "lay_pitch": round(self._local_lay_pitch, 4),
                            "ragdoll": round(self._local_ragdoll, 3),
                            "head_yaw": round(self._local_head_yaw, 4),
                            "head_pitch": round(self._local_head_pitch, 4),
                            "is_carmelito": True,
                            "chick_name": self.chick_name,
                            "character": self.character_id,
                            "kick_amount": round(self._local_kick_amount, 3),
                            "kick_side": round(self._local_kick_side, 1),
                            "punch_amount": round(self._local_punch_amount, 3),
                            "punch_side": round(self._local_punch_side, 1),
                            "jump_offset_y": round(self._local_jump_offset_y, 3),
                            "jump_amount": round(self._local_jump_amount, 3),
                            "tag_amount": round(self._local_tag_amount, 3),
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
            "rot_z": float(pdata.get("rot_z", 0.0)),
            "lay_pitch": float(pdata.get("lay_pitch", 0.0)),
            "ragdoll": float(pdata.get("ragdoll", 0.0)),
            "head_yaw": float(pdata.get("head_yaw", 0.0)),
            "head_pitch": float(pdata.get("head_pitch", 0.0)),
            "color": tuple(int(c) for c in raw_color),
            "name": pdata.get("name"),
            "chick_name": pdata.get("chick_name") or CHICK_NAME,
            "character": resolve_character_id(pdata),
            "is_carmelito": bool(pdata.get("is_carmelito", True)),
            "kick_amount": float(pdata.get("kick_amount", 0.0)),
            "kick_side": float(pdata.get("kick_side", 1.0)),
            "punch_amount": float(pdata.get("punch_amount", 0.0)),
            "punch_side": float(pdata.get("punch_side", 1.0)),
            "jump_offset_y": float(pdata.get("jump_offset_y", 0.0)),
            "jump_amount": float(pdata.get("jump_amount", 0.0)),
            "tag_amount": float(pdata.get("tag_amount", 0.0)),
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
                        if "rot_z" in msg:
                            rp["rot_z"] = float(msg["rot_z"])
                        if "lay_pitch" in msg:
                            rp["lay_pitch"] = float(msg["lay_pitch"])
                        if "ragdoll" in msg:
                            rp["ragdoll"] = float(msg["ragdoll"])
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
                        if "character" in msg and msg["character"]:
                            rp["character"] = msg["character"]
                        if "kick_amount" in msg:
                            rp["kick_amount"] = float(msg["kick_amount"])
                        if "kick_side" in msg:
                            rp["kick_side"] = float(msg["kick_side"])
                        if "punch_amount" in msg:
                            rp["punch_amount"] = float(msg["punch_amount"])
                        if "punch_side" in msg:
                            rp["punch_side"] = float(msg["punch_side"])
                        if "jump_offset_y" in msg:
                            rp["jump_offset_y"] = float(msg["jump_offset_y"])
                        if "jump_amount" in msg:
                            rp["jump_amount"] = float(msg["jump_amount"])
                        if "tag_amount" in msg:
                            rp["tag_amount"] = float(msg["tag_amount"])

            elif msg_type == "leave":
                pid = int(msg["id"])
                with self._lock:
                    self.remote_players.pop(pid, None)

            elif msg_type == "kick_hit":
                with self._lock:
                    self._incoming_kick_hits.append(msg)

            elif msg_type == "punch_hit":
                with self._lock:
                    self._incoming_punch_hits.append(msg)

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
    if hasattr(pygame.key, "stop_text_input"):
        pygame.key.stop_text_input()
    clock = pygame.time.Clock()
    pygame.mouse.set_visible(True)

    model_3d = Carmelito3D()

    anim_time = 0.0
    is_online = False     # You start offline staring down at the island until you click Play
    has_entered_game = False
    menu_state = "title"  # "title" -> "character_select" -> "character_used"
    use_button_rect = pygame.Rect(-100, -100, 0, 0)
    arrow_right_rect = pygame.Rect(-100, -100, 0, 0)
    arrow_left_rect = pygame.Rect(-100, -100, 0, 0)
    carousel_index = 0
    available_characters = [
        ("carmelito", CHICK_NAME),
        ("carmen", CARMEN_NAME),
        ("pangdun", PANGDUN_NAME),
        ("xiaoliuzi", XIAOLIUZI_NAME),
    ]

    # Fight System between Carmelito & Belino (小胖墩)
    is_fighting = False
    fight_player_pressed = False
    fight_belino_pressed = False
    belino_auto_press_timer = -1.0
    fight_timer = 0.0
    fight_carmelito_x = 0.0
    fight_carmelito_z = 0.0
    fight_belino_x = 0.0
    fight_belino_z = 0.0
    fight_opponent_pid: int | None = None
    carmelito_fight_button_rect = pygame.Rect(-100, -100, 0, 0)
    belino_fight_button_rect = pygame.Rect(-100, -100, 0, 0)
    fight_leave_button_rect = pygame.Rect(-100, -100, 0, 0)
    near_belino = False
    action_banner_text = ""
    dust_sparks: list[dict[str, Any]] = []

    # Jump action (triggered with 'J' key) - crisp crouch windup then explosive leap!
    jump_offset_y = 0.0
    jump_velocity_y = 0.0
    jump_state = "idle"   # "idle" -> "crouching" -> "airborne"
    crouch_timer = 0.0
    crouch_duration = 0.14 # Quick snappy crouch before launching up
    jump_amount = 0.0      # Crouch depth (1.0 = deep crouch, 0.0 = standing/jumping)
    wing_flap_amount = 0.0 # Wings flap when airborne
    JUMP_IMPULSE = 8.5     # High energetic leap into the sky
    GRAVITY = 22.0         # Crisp realistic gravity

    # First-person kick action (triggered with 'K' key)
    is_kicking = False
    kick_timer = 0.0
    kick_duration = 0.48
    kick_side = 1.0  # 1.0 for right leg, -1.0 for left leg
    kick_hit_victims: set[int] = set()
    punch_hit_victims: set[int] = set()
    local_headshot_phase = "none"
    local_headshot_timer = 0.0
    local_headshot_face_yaw = 0.0
    knock_vx = 0.0
    knock_vz = 0.0
    launch_accel_timer = 0.0
    is_kick_launched = False
    kick_roll_dir = 1.0
    local_rot_z = 0.0
    local_lay_pitch = 0.0
    local_ragdoll = 0.0
    kick_lay_dir = -1.0
    kick_bounced = False
    side_lying_timer = 0.0
    remote_ragdolls: dict[int, ChickRagdollSim] = {}

    # First-person punch action (triggered with 'P' key)
    is_punching = False
    punch_timer = 0.0
    punch_duration = 0.38
    punch_side = 1.0  # 1.0 for right wing punch, -1.0 for left wing punch

    # Zombie tag hand reach (triggered by 'T' key)
    # Both arms raise forward and stop right at neck level
    is_tagging = False
    tag_amount = 0.0
    selected_character = "carmelito"
    selected_chick_name = CHICK_NAME
    has_selected_character = False

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
    # Riding / piggyback state (when jumped onto another player's back/head):
    riding_player_id: int | None = None
    riding_prev_base_pos: tuple[float, float] | None = None

    # Natural automatic blinking + manual 'B' key blinking (for online player mode)
    blink_amount = 0.0
    blink_hold_timer = 0.0
    blink_cover_progress = 0.0
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
    ime_comp_text = ""          # Live OS IME composition string (e.g. macOS Pinyin preedit)
    ime_last_active_time = -10.0 # Timestamp of last OS IME composition/commit to avoid Enter race
    builtin_pinyin_mode = False # Toggleable built-in Pinyin IME (Tab or click badge)
    pinyin_buffer = ""
    pinyin_page = 0
    consumed_pinyin_texts: set[str] = set()
    pinyin_toggle_rect = pygame.Rect(-100, -100, 0, 0)
    candidate_click_rects: list[tuple[pygame.Rect, str]] = []
    chat_log_rect = pygame.Rect(-100, -100, 0, 0)
    # Persistent chatbox history: [{"sender": str, "text": str, "is_self": bool, "sender_id": int}]
    chat_history: list[dict[str, Any]] = []
    # Active chat bubbles per player: {player_id: [{"text": str, "timer": float, "duration": float}]}
    # Player id -1 represents local player
    chat_bubbles: dict[int, list[dict[str, Any]]] = {}

    def open_chat_input() -> None:
        nonlocal is_typing_chat, chat_input_text, ime_comp_text, pinyin_buffer, pinyin_page
        is_typing_chat = True
        chat_input_text = ""
        ime_comp_text = ""
        pinyin_buffer = ""
        pinyin_page = 0
        if hasattr(pygame.key, "start_text_input"):
            pygame.key.start_text_input()

    def close_chat_input() -> None:
        nonlocal is_typing_chat, chat_input_text, ime_comp_text, pinyin_buffer, pinyin_page
        is_typing_chat = False
        chat_input_text = ""
        ime_comp_text = ""
        pinyin_buffer = ""
        pinyin_page = 0
        if hasattr(pygame.key, "stop_text_input"):
            pygame.key.stop_text_input()

        # Storybook fluffy white clouds drifting across the sky dome:
    # Each cloud has azimuth (heading), elevation angle above horizon, radius scale, and puffs
    sky_clouds_data = [
        {"az": 0.05, "el": 0.28, "scale": 17.0, "drift_spd": 0.012},
        {"az": 0.58, "el": 0.19, "scale": 22.0, "drift_spd": 0.010},
        {"az": 1.15, "el": 0.36, "scale": 19.0, "drift_spd": 0.011},
        {"az": 1.72, "el": 0.24, "scale": 25.0, "drift_spd": 0.009},
        {"az": 2.30, "el": 0.32, "scale": 18.0, "drift_spd": 0.013},
        {"az": 2.85, "el": 0.18, "scale": 24.0, "drift_spd": 0.010},
        {"az": 3.42, "el": 0.40, "scale": 21.0, "drift_spd": 0.011},
        {"az": 4.02, "el": 0.22, "scale": 26.0, "drift_spd": 0.008},
        {"az": 4.60, "el": 0.34, "scale": 19.0, "drift_spd": 0.012},
        {"az": 5.18, "el": 0.20, "scale": 23.0, "drift_spd": 0.010},
        {"az": 5.75, "el": 0.30, "scale": 20.0, "drift_spd": 0.011},
    ]
    cloud_puffs = [
        (0.0, 0.0, 1.0, 0.65),
        (-0.55, 0.06, 0.72, 0.55),
        (0.55, 0.06, 0.72, 0.55),
        (-0.28, -0.22, 0.75, 0.68),
        (0.28, -0.20, 0.78, 0.70),
        (0.0, -0.28, 0.65, 0.65),
    ]

    running = True
    while running:
        dt = min(clock.tick(TARGET_FPS) / 1000.0, 0.05)
        anim_time += dt

        consumed_pinyin_texts.clear()
        ime_was_active_at_frame_start = bool(ime_comp_text)
        ime_event_this_frame = False
        pending_submit_chat = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif is_online and is_typing_chat and event.type == getattr(pygame, "TEXTEDITING", -1):
                # Native OS IME composition preview (e.g. macOS Pinyin before committing)
                ime_comp_text = str(getattr(event, "text", "") or "")
                ime_event_this_frame = True
                ime_last_active_time = anim_time
            elif is_online and is_typing_chat and event.type == pygame.TEXTINPUT:
                ime_comp_text = ""
                txt_in = str(getattr(event, "text", "") or "")
                if not txt_in or txt_in in consumed_pinyin_texts:
                    continue
                if not txt_in.isascii():
                    ime_event_this_frame = True
                    ime_last_active_time = anim_time
                if builtin_pinyin_mode and txt_in.isascii() and txt_in.isalpha():
                    if len(pinyin_buffer) < 24:
                        pinyin_buffer += txt_in.lower()
                        pinyin_page = 0
                else:
                    # Append committed text (handles both English and OS IME Chinese)
                    if len(chat_input_text) < 60:
                        chat_input_text += txt_in
            elif event.type == pygame.KEYDOWN:
                # Accept both standard Return/Enter and Numpad Enter:
                is_enter_key = event.key in (pygame.K_RETURN, getattr(pygame, "K_KP_ENTER", pygame.K_RETURN))
                if is_online and is_typing_chat:
                    if event.key == pygame.K_TAB:
                        # Toggle built-in Chinese Pinyin mode
                        if builtin_pinyin_mode and pinyin_buffer:
                            chat_input_text = (chat_input_text + pinyin_buffer)[:60]
                            pinyin_buffer = ""
                            pinyin_page = 0
                        builtin_pinyin_mode = not builtin_pinyin_mode
                    elif builtin_pinyin_mode and pinyin_buffer:
                        cands = lookup_pinyin(pinyin_buffer)
                        page_cands = cands[pinyin_page * 5 : (pinyin_page + 1) * 5]
                        digit_keys = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5)
                        kp_digit_keys = tuple(getattr(pygame, f"K_KP{i}", -1) for i in range(1, 6))
                        if event.key in digit_keys or event.key in kp_digit_keys:
                            c_idx = digit_keys.index(event.key) if event.key in digit_keys else kp_digit_keys.index(event.key)
                            if c_idx < len(page_cands):
                                chat_input_text = (chat_input_text + page_cands[c_idx])[:60]
                                pinyin_buffer = ""
                                pinyin_page = 0
                                consumed_pinyin_texts.add(str(c_idx + 1))
                        elif event.key == pygame.K_SPACE:
                            chosen = page_cands[0] if page_cands else pinyin_buffer
                            chat_input_text = (chat_input_text + chosen)[:60]
                            pinyin_buffer = ""
                            pinyin_page = 0
                            consumed_pinyin_texts.add(" ")
                        elif event.key in (pygame.K_EQUALS, pygame.K_RIGHTBRACKET, pygame.K_DOWN):
                            if (pinyin_page + 1) * 5 < len(cands):
                                pinyin_page += 1
                            consumed_pinyin_texts.update({"=", "]"})
                        elif event.key in (pygame.K_MINUS, pygame.K_LEFTBRACKET, pygame.K_UP):
                            if pinyin_page > 0:
                                pinyin_page -= 1
                            consumed_pinyin_texts.update({"-", "["})
                        elif event.key == pygame.K_BACKSPACE:
                            pinyin_buffer = pinyin_buffer[:-1]
                            pinyin_page = 0
                        elif is_enter_key:
                            chat_input_text = (chat_input_text + pinyin_buffer)[:60]
                            pinyin_buffer = ""
                            pinyin_page = 0
                        elif event.key == pygame.K_ESCAPE:
                            pinyin_buffer = ""
                            pinyin_page = 0
                    elif not ime_comp_text:
                        if event.key == pygame.K_ESCAPE:
                            close_chat_input()
                        elif is_enter_key:
                            # Defer submit until AFTER all TEXTINPUT/TEXTEDITING events in this frame
                            # have been processed! Prevents macOS IME Enter/select race from dropping Chinese text!
                            pending_submit_chat = True
                        elif event.key == pygame.K_BACKSPACE:
                            if not ime_event_this_frame:
                                chat_input_text = chat_input_text[:-1]
                else:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_F11:
                        fullscreen = not fullscreen
                        screen = create_window(fullscreen)
                    elif is_online and is_enter_key:
                        # Pressing RETURN/ENTER while in game opens the typing box
                        open_chat_input()
                    elif is_online and event.key == pygame.K_u:
                        # Toggle mouth open / close
                        mouth_open = not mouth_open
                    elif is_online and event.key == pygame.K_b:
                        # Trigger a blink on demand (and holding B keeps eyes closed)
                        blink_hold_timer = 0.16
                        auto_blink_timer = random.uniform(2.8, 5.0)
                    elif is_online and not is_fighting and not (is_kick_launched or side_lying_timer > 0.0 or local_ragdoll > 0.05 or local_headshot_phase != "none") and event.key == pygame.K_j:
                        # Pressing 'J' makes you crouch and jump! (Disabled during ragdoll mode)
                        if jump_state == "idle":
                            jump_state = "crouching"
                            crouch_timer = 0.0
                            jump_amount = 0.0
                            wing_flap_amount = 0.0
                    elif is_online and not is_fighting and not (is_kick_launched or side_lying_timer > 0.0 or local_ragdoll > 0.05 or local_headshot_phase != "none") and event.key == pygame.K_k:
                        # Pressing 'K' triggers a forward martial arts karate kick! (Disabled during ragdoll mode)
                        is_kicking = True
                        kick_timer = 0.0
                        kick_side = -kick_side  # alternate between right and left leg!
                        kick_hit_victims.clear()
                    elif is_online and not is_fighting and not (is_kick_launched or side_lying_timer > 0.0 or local_ragdoll > 0.05 or local_headshot_phase != "none") and event.key == pygame.K_p:
                        # Pressing 'P' triggers a forward boxing punch / wing strike! (Disabled during ragdoll mode)
                        is_punching = True
                        punch_timer = 0.0
                        punch_side = -punch_side  # alternate between right and left wing!
                        punch_hit_victims.clear()
                    elif is_online and not is_fighting and not (is_kick_launched or side_lying_timer > 0.0 or local_ragdoll > 0.05 or local_headshot_phase != "none") and event.key == pygame.K_t:
                        # Pressing 'T' toggles raising both arms forward like a zombie (Disabled during ragdoll mode)
                        is_tagging = not is_tagging
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Menu navigation and joining in offline mode
                if not is_online:
                    if menu_state == "title":
                        if play_button_rect.collidepoint(event.pos):
                            # Clicking PLAY opens character select: Carmelito appears spinning, with name and USE button
                            menu_state = "character_select"
                            is_dragging_island = False
                        else:
                            is_dragging_island = True
                            drag_start_pos = event.pos
                    elif menu_state in ("character_select", "character_used"):
                        if arrow_right_rect.collidepoint(event.pos):
                            # Click right arrow to switch to the next chick!
                            carousel_index = (carousel_index + 1) % len(available_characters)
                            is_dragging_island = False
                        elif arrow_left_rect.collidepoint(event.pos):
                            # Click left arrow to switch to previous chick
                            carousel_index = (carousel_index - 1) % len(available_characters)
                            is_dragging_island = False
                        elif use_button_rect.collidepoint(event.pos):
                            # Equip the currently displayed chick
                            curr_char, curr_name = available_characters[carousel_index]
                            selected_character = curr_char
                            selected_chick_name = curr_name
                            has_selected_character = True
                            menu_state = "character_used"
                            net.set_character(selected_character, selected_chick_name)
                            is_dragging_island = False
                        elif menu_state == "character_used" and play_button_rect.collidepoint(event.pos):
                            # Clicking spawned PLAY button launches the game with chosen chick!
                            is_online = True
                            has_entered_game = True
                            net.set_character(selected_character, selected_chick_name)
                            net.set_online(True)
                            cam_x = ground_cam_x
                            cam_z = ground_cam_z
                            cam_yaw = ground_cam_yaw
                            head_yaw = 0.0
                            head_pitch = 0.0
                            is_dragging_island = False
                        else:
                            is_dragging_island = True
                            drag_start_pos = event.pos
                else:
                    # Chat UI clicks (Pinyin toggle, candidate pills, or opening chatbox)
                    handled_chat_click = False
                    if is_typing_chat:
                        if pinyin_toggle_rect.collidepoint(event.pos):
                            if builtin_pinyin_mode and pinyin_buffer:
                                chat_input_text = (chat_input_text + pinyin_buffer)[:60]
                                pinyin_buffer = ""
                                pinyin_page = 0
                            builtin_pinyin_mode = not builtin_pinyin_mode
                            handled_chat_click = True
                        else:
                            for cand_r, cand_str in candidate_click_rects:
                                if cand_r.collidepoint(event.pos):
                                    chat_input_text = (chat_input_text + cand_str)[:60]
                                    pinyin_buffer = ""
                                    pinyin_page = 0
                                    handled_chat_click = True
                                    break
                    elif chat_log_rect.collidepoint(event.pos):
                        open_chat_input()
                        handled_chat_click = True

                    # In-game interactive button clicks
                    if handled_chat_click:
                        pass
                    elif is_fighting:
                        if fight_leave_button_rect.collidepoint(event.pos):
                            # Leave the fight, reset buttons, and return to 1st-person POV!
                            is_fighting = False
                            fight_player_pressed = False
                            fight_belino_pressed = False
                            belino_auto_press_timer = -1.0
                            cam_x = fight_carmelito_x
                            cam_z = fight_carmelito_z
                            cam_yaw = ground_cam_yaw
                    elif near_belino and selected_character == "carmelito":
                        if carmelito_fight_button_rect.collidepoint(event.pos):
                            fight_player_pressed = True
                            # Belino AI rival excitedly accepts right after!
                            if not fight_belino_pressed and belino_auto_press_timer < 0.0:
                                belino_auto_press_timer = 0.35
                        elif belino_fight_button_rect.collidepoint(event.pos):
                            fight_belino_pressed = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                is_dragging_island = False
                drag_start_pos = None
            elif event.type == pygame.MOUSEMOTION:
                if not is_online and is_dragging_island:
                    # Dragging mouse rotates the island view around its center
                    overview_yaw += event.rel[0] * 0.008

        if is_online and is_typing_chat and pending_submit_chat:
            # If OS IME was active at the start of this frame or fired TEXTEDITING/TEXTINPUT
            # alongside Enter (e.g. confirming a macOS Pinyin candidate), keep chat open so
            # the newly committed Chinese characters stay visible instead of closing blank!
            if ime_was_active_at_frame_start or ime_event_this_frame or ime_comp_text:
                pass
            else:
                clean = chat_input_text.strip()
                if clean:
                    net.send_chat(clean)
                    # Create local chat bubble (duration 5.5s)
                    if -1 not in chat_bubbles:
                        chat_bubbles[-1] = []
                    chat_bubbles[-1].append({"text": clean, "timer": 5.5, "duration": 5.5})
                    chat_bubbles[-1] = chat_bubbles[-1][-4:]  # Limit to 4 stacked bubbles
                    # Append to persistent chatbox history
                    chat_history.append({
                        "sender": selected_chick_name,
                        "text": clean,
                        "is_self": True,
                        "sender_id": -1,
                    })
                    if len(chat_history) > 40:
                        del chat_history[:-40]
                    close_chat_input()
                elif (anim_time - ime_last_active_time) >= 0.18:
                    # Only close empty chat if no recent IME commit just happened
                    close_chat_input()

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
            blink_cover_progress = 0.0
            is_blinking = False
        else:
            # --- BLINKING (when online: automatic natural blinks + 'B' key manual blink) ---
            auto_blink_timer -= dt
            if auto_blink_timer <= 0.0:
                blink_hold_timer = 0.16
                auto_blink_timer = random.uniform(0.18, 0.28) if random.random() < 0.18 else random.uniform(2.8, 5.0)

            if blink_hold_timer > 0.0:
                blink_hold_timer = max(0.0, blink_hold_timer - dt)

            holding_b = (not is_typing_chat) and bool(keys[pygame.K_b])
            if holding_b:
                blink_cover_progress = min(1.0, blink_cover_progress + 8.5 * dt)
            else:
                blink_cover_progress = max(0.0, blink_cover_progress - 8.5 * dt)

            target_blink = 1.0 if (blink_hold_timer > 0.0 or holding_b) else 0.0
            if blink_amount < target_blink:
                blink_amount = min(target_blink, blink_amount + 18.0 * dt)
            elif blink_amount > target_blink:
                blink_amount = max(target_blink, blink_amount - 14.0 * dt)
            is_blinking = blink_amount >= 0.45

            # --- HEAD / CAMERA LOOK FOLLOWS MOUSE POINTER ---
            mx, my = pygame.mouse.get_pos()
            norm_mx = (mx - win_w * 0.5) / max(1.0, win_w * 0.5)
            norm_my = (my - win_h * 0.5) / max(1.0, win_h * 0.5)

            is_ragdoll_mode = (is_kick_launched or side_lying_timer > 0.0 or local_ragdoll > 0.05 or local_headshot_phase != "none")
            if is_ragdoll_mode:
                target_head_yaw = 0.0
                target_head_pitch = 0.0
            else:
                target_head_yaw = max(-MAX_HEAD_YAW, min(MAX_HEAD_YAW, norm_mx * MAX_HEAD_YAW))
                if norm_my < 0.0:
                    target_head_pitch = -norm_my * MAX_HEAD_PITCH_UP
                else:
                    target_head_pitch = -norm_my * MAX_HEAD_PITCH_DOWN
                target_head_pitch = max(-MAX_HEAD_PITCH_DOWN, min(MAX_HEAD_PITCH_UP, target_head_pitch))

            if local_headshot_phase == "none":
                head_alpha = 1.0 - math.exp(-HEAD_SMOOTH_SPEED * dt)
                head_yaw += (target_head_yaw - head_yaw) * head_alpha
                head_pitch += (target_head_pitch - head_pitch) * head_alpha

            # Proximity to Belino (小胖墩) when player is Carmelito
            near_belino = False
            active_belino_pid: int | None = None
            active_belino_wx = 0.0
            active_belino_wz = 0.0

            if selected_character == "carmelito" and not is_fighting:
                for pid, pdata in remote_players.items():
                    rs = remote_states.get(pid)
                    if not rs:
                        continue
                    r_char = resolve_character_id(pdata)
                    if r_char in ("pangdun", "小胖墩", "belino", "coquenpate"):
                        dist = math.hypot(rs["wx"] - cam_x, rs["wz"] - cam_z)
                        if dist <= 5.8:
                            near_belino = True
                            active_belino_pid = pid
                            active_belino_wx = rs["wx"]
                            active_belino_wz = rs["wz"]
                            break

                if not near_belino:
                    fight_player_pressed = False
                    fight_belino_pressed = False
                    belino_auto_press_timer = -1.0
                else:
                    if belino_auto_press_timer > 0.0:
                        belino_auto_press_timer -= dt
                        if belino_auto_press_timer <= 0.0:
                            fight_belino_pressed = True

                    # When BOTH buttons are pressed -> START THE FIGHT!
                    if fight_player_pressed and fight_belino_pressed:
                        is_fighting = True
                        fight_timer = 0.0
                        fight_carmelito_x = cam_x
                        fight_carmelito_z = cam_z
                        fight_belino_x = active_belino_wx
                        fight_belino_z = active_belino_wz
                        fight_opponent_pid = active_belino_pid

            # --- VIEW TURNING CONTROLS (Left/Right Arrows + Q/E) ---
            turn_input = 0.0
            if not is_typing_chat and not is_fighting and not is_ragdoll_mode:
                if keys[pygame.K_LEFT] or keys[pygame.K_q]:
                    turn_input -= 1.0
                if keys[pygame.K_RIGHT] or keys[pygame.K_e]:
                    turn_input += 1.0
            cam_yaw += turn_input * TURN_SPEED * dt

            if is_fighting:
                fight_timer += dt
                # Step out of Carmelito's sight: 3rd-person spectator battle cam orbiting both chickens!
                battle_mid_x = (fight_carmelito_x + fight_belino_x) * 0.5
                battle_mid_z = (fight_carmelito_z + fight_belino_z) * 0.5
                base_angle = math.atan2(fight_belino_x - fight_carmelito_x, fight_belino_z - fight_carmelito_z) + math.pi * 0.5
                orbit_angle = base_angle + math.sin(fight_timer * 0.8) * 0.35
                orbit_dist = 5.2

                cam_x = battle_mid_x + math.sin(orbit_angle) * orbit_dist
                cam_z = battle_mid_z + math.cos(orbit_angle) * orbit_dist
                cam_yaw = orbit_angle + math.pi
                total_yaw = cam_yaw
                total_pitch = -0.18
                head_yaw = 0.0
                head_pitch = 0.0
            else:
                total_yaw = cam_yaw + head_yaw
                total_pitch = head_pitch

            # --- MOVEMENT CONTROLS (Arrow Up/Down + WASD) ---
            move_fwd = 0.0
            move_side = 0.0
            if not is_typing_chat and not is_ragdoll_mode:
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
            # Moving: normal walk / run speed
            # Run when shift or space is held while moving
            run_key_pressed = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] or keys[pygame.K_SPACE]
            is_running = is_moving and run_key_pressed
            is_walking = is_moving and not run_key_pressed

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

            # Process any incoming kick hits from other players / AI
            if is_online and not is_fighting:
                for kh in net.pop_incoming_kick_hits():
                    dx_k = float(kh.get("dir_x", 0.0))
                    dz_k = float(kh.get("dir_z", 1.0))
                    dlen_k = math.hypot(dx_k, dz_k)
                    nx_k = dx_k / dlen_k if dlen_k > 1e-4 else 0.0
                    nz_k = dz_k / dlen_k if dlen_k > 1e-4 else 1.0
                    if bool(kh.get("launch", False)):
                        # 25% kick outcome: pushed + accelerate up + ragdoll mode + land laying down on grass for 1 sec!
                        knock_vx = nx_k * 11.5
                        knock_vz = nz_k * 11.5
                        is_kick_launched = True
                        launch_accel_timer = 0.18
                        jump_state = "airborne"
                        jump_velocity_y = 0.6
                        jump_offset_y = max(jump_offset_y, 0.08)
                        kick_roll_dir = 1.0 if float(kh.get("roll_dir", 1.0)) >= 0.0 else -1.0
                        fwd_dot = nx_k * math.sin(cam_yaw) + nz_k * math.cos(cam_yaw)
                        kick_lay_dir = 1.0 if fwd_dot > 0.0 else -1.0
                        local_ragdoll = 1.0
                        kick_bounced = False
                        side_lying_timer = 0.0
                        # Cancel any active kick/punch/tag/flap on entering ragdoll mode
                        is_kicking = False
                        kick_timer = 0.0
                        is_punching = False
                        punch_timer = 0.0
                        is_tagging = False
                        tag_amount = 0.0
                        jump_amount = 0.0
                        wing_flap_amount = 0.0
                    else:
                        # 75% kick outcome: just get pushed horizontally
                        knock_vx = nx_k * 9.5
                        knock_vz = nz_k * 9.5

                for ph in net.pop_incoming_punch_hits():
                    dx_p = float(ph.get("dir_x", 0.0))
                    dz_p = float(ph.get("dir_z", 1.0))
                    dlen_p = math.hypot(dx_p, dz_p)
                    nx_p = dx_p / dlen_p if dlen_p > 1e-4 else 0.0
                    nz_p = dz_p / dlen_p if dlen_p > 1e-4 else 1.0
                    if bool(ph.get("headshot", False)):
                        # 30% punch headshot: face attacker, head moves up to sky, fall backward onto grass for 1 sec!
                        knock_vx = nx_p * 5.2
                        knock_vz = nz_p * 5.2
                        local_headshot_face_yaw = math.atan2(-nx_p, -nz_p)
                        local_headshot_phase = "head_up"
                        local_headshot_timer = 0.0
                        kick_lay_dir = -1.0
                        kick_roll_dir = 0.0
                        is_kick_launched = False
                        side_lying_timer = 0.0
                        local_ragdoll = 0.0
                        is_kicking = False
                        kick_timer = 0.0
                        is_punching = False
                        punch_timer = 0.0
                        is_tagging = False
                        tag_amount = 0.0
                        jump_amount = 0.0
                        wing_flap_amount = 0.0
                    else:
                        # 70% punch outcome: just pushed back
                        knock_vx = nx_p * 8.2
                        knock_vz = nz_p * 8.2

                # Apply active knockback push velocity
                if abs(knock_vx) > 0.01 or abs(knock_vz) > 0.01:
                    new_kx = cam_x + knock_vx * dt
                    new_kz = cam_z + knock_vz * dt
                    if math.hypot(new_kx, new_kz) <= ISLAND_RADIUS - 2.5:
                        cam_x = new_kx
                        cam_z = new_kz
                    else:
                        cur_ang = math.atan2(new_kx, new_kz)
                        max_r = ISLAND_RADIUS - 2.5
                        cam_x = math.sin(cur_ang) * max_r
                        cam_z = math.cos(cur_ang) * max_r
                    drag = 1.1 if jump_state == "airborne" else 5.5
                    decay = max(0.0, 1.0 - drag * dt)
                    knock_vx *= decay
                    knock_vz *= decay

                # 30% punch headshot animation: head tilts up -> fall down backward facing attacker -> lay 1s
                if local_headshot_phase == "head_up":
                    local_headshot_timer += dt
                    diff_y = (local_headshot_face_yaw - cam_yaw + math.pi) % (2.0 * math.pi) - math.pi
                    t_step = 16.0 * dt
                    if abs(diff_y) <= t_step:
                        cam_yaw = local_headshot_face_yaw
                    else:
                        cam_yaw = (cam_yaw + math.copysign(t_step, diff_y) + math.pi) % (2.0 * math.pi) - math.pi
                    head_yaw += (0.0 - head_yaw) * min(1.0, 14.0 * dt)
                    head_pitch = min(math.pi * 0.5, head_pitch + 7.0 * dt)
                    is_moving = False
                    is_walking = False
                    is_running = False
                    if local_headshot_timer >= 0.28 and head_pitch >= math.pi * 0.46:
                        local_headshot_phase = "fall_back"
                        local_headshot_timer = 0.0
                        cam_yaw = local_headshot_face_yaw
                elif local_headshot_phase == "fall_back":
                    local_headshot_timer += dt
                    cam_yaw = local_headshot_face_yaw
                    fall_speed = math.radians(260.0 + 180.0 * min(1.0, local_headshot_timer * 2.5))
                    local_lay_pitch = max(-math.pi * 0.5, local_lay_pitch - fall_speed * dt)
                    progress = min(1.0, abs(local_lay_pitch) / (math.pi * 0.5))
                    head_pitch = (math.pi * 0.5) * (1.0 - progress) + 0.12 * progress
                    is_moving = False
                    is_walking = False
                    is_running = False
                    if local_lay_pitch <= -math.pi * 0.5 + 1e-4:
                        local_lay_pitch = -math.pi * 0.5
                        local_rot_z = 0.0
                        local_ragdoll = 1.0
                        local_headshot_phase = "none"
                        side_lying_timer = 1.0
                # Laying down on grass recovery (1.0 sec ragdoll rest) after 25% launch or 30% headshot
                elif side_lying_timer > 0.0:
                    side_lying_timer = max(0.0, side_lying_timer - dt)
                    local_lay_pitch = kick_lay_dir * (math.pi * 0.5)
                    local_ragdoll = 1.0
                    is_moving = False
                    is_walking = False
                    is_running = False
                elif not is_kick_launched and (abs(local_lay_pitch) > 1e-3 or abs(local_rot_z) > 1e-3 or local_ragdoll > 1e-3):
                    rec_step = math.radians(280.0) * dt
                    if abs(local_lay_pitch) <= rec_step:
                        local_lay_pitch = 0.0
                    else:
                        local_lay_pitch -= math.copysign(rec_step, local_lay_pitch)
                    if abs(local_rot_z) <= rec_step:
                        local_rot_z = 0.0
                    else:
                        local_rot_z -= math.copysign(rec_step, local_rot_z)
                    local_ragdoll = max(0.0, local_ragdoll - 3.5 * dt)

            if is_moving and not is_fighting:
                fwd_n = move_fwd / move_mag
                side_n = move_side / move_mag
                speed = RUN_SPEED if is_running else WALK_SPEED
                sin_b = math.sin(cam_yaw)
                cos_b = math.cos(cam_yaw)
                new_cx = cam_x + (sin_b * fwd_n + cos_b * side_n) * speed * dt
                new_cz = cam_z + (cos_b * fwd_n - sin_b * side_n) * speed * dt
                if math.hypot(new_cx, new_cz) <= ISLAND_RADIUS - 2.5:
                    cam_x = new_cx
                    cam_z = new_cz
                else:
                    # Slide along island perimeter
                    cur_ang = math.atan2(new_cx, new_cz)
                    max_r = ISLAND_RADIUS - 2.5
                    cam_x = math.sin(cur_ang) * max_r
                    cam_z = math.cos(cur_ang) * max_r

            # --- CHICK-TO-CHICK COLLISION, DYNAMIC PUSHING & PIGGYBACK RIDING ---
            # 1. Players cannot walk through each other.
            # 2. If one player is stationary and the other rams/moves into them, the moving player pushes them.
            # 3. If both players are walking/running into each other, they push each other with mutual resistance.
            # 4. If a player jumps onto another chick, they land and stay firmly on top of them!
            #    When the bottom chick walks or runs, the top player rides along smoothly without falling off!
            landing_support_y = 0.0
            found_carrier_id: int | None = None
            CHICK_BODY_RADIUS = 0.58
            MIN_CHICK_DIST = CHICK_BODY_RADIUS * 2.0  # 1.16m body contact boundary

            if is_online and not is_fighting:
                my_height = jump_offset_y
                my_weight = 1.0 + (1.2 if is_running else (0.6 if is_moving else 0.0))

                for pid, pdata in remote_players.items():
                    if pid not in remote_states:
                        continue
                    rs = remote_states[pid]
                    ox = rs.get("wx", 0.0)
                    oz = rs.get("wz", 0.0)
                    other_jump_y = rs.get("jump_offset_y", 0.0)
                    other_running = pdata.get("running", False)
                    other_walking = pdata.get("walking", False)
                    other_moving = other_running or other_walking

                    dx = cam_x - ox
                    dz = cam_z - oz
                    horiz_d = math.hypot(dx, dz)

                    # Check jumping onto and riding the other player:
                    other_top_y = other_jump_y + 1.15
                    # Allow riding range slightly wider than initial land range so motion doesn't slip off
                    is_currently_riding_this = (riding_player_id == pid)
                    ride_range = MIN_CHICK_DIST * 1.25 if is_currently_riding_this else MIN_CHICK_DIST * 0.92

                    if horiz_d < ride_range:
                        if my_height >= other_top_y - 0.32:
                            # Standing / riding on top of this chick!
                            if other_top_y > landing_support_y:
                                landing_support_y = other_top_y
                                found_carrier_id = pid
                            continue  # Stand on top, avoid pushing feet horizontally

                    # Ground-level body collision and dynamic pushing:
                    if horiz_d < MIN_CHICK_DIST and abs(my_height - other_jump_y) < 1.10:
                        overlap = MIN_CHICK_DIST - horiz_d
                        nx = dx / max(1e-4, horiz_d)
                        nz = dz / max(1e-4, horiz_d)

                        other_weight = 1.0 + (1.2 if other_running else (0.6 if other_moving else 0.0))

                        # Determine dynamic push ratios based on movement status:
                        if is_moving and not other_moving:
                            # Moving player pushes stationary player:
                            ratio_me = 0.20
                            ratio_other = 0.80
                        elif other_moving and not is_moving:
                            # Stationary player gets pushed by moving player:
                            ratio_me = 0.80
                            ratio_other = 0.20
                        elif is_moving and other_moving:
                            # Both moving/running into each other:
                            tot_w = my_weight + other_weight
                            ratio_me = other_weight / tot_w
                            ratio_other = my_weight / tot_w
                        else:
                            # Both stationary but touching:
                            ratio_me = 0.50
                            ratio_other = 0.50

                        # Displace local player:
                        cam_x += nx * (overlap * ratio_me)
                        cam_z += nz * (overlap * ratio_me)

                        # Displace remote player:
                        rs["wx"] = ox - nx * (overlap * ratio_other)
                        rs["wz"] = oz - nz * (overlap * ratio_other)

                # Smoothly ride along when on top of someone:
                # If local player is riding carrier, match carrier's horizontal delta!
                if found_carrier_id is not None and found_carrier_id in remote_states:
                    c_rs = remote_states[found_carrier_id]
                    c_pos = (c_rs["wx"], c_rs["wz"])
                    if riding_player_id == found_carrier_id and riding_prev_base_pos is not None:
                        # Carry player along with bottom player's movement!
                        delta_cx = c_pos[0] - riding_prev_base_pos[0]
                        delta_cz = c_pos[1] - riding_prev_base_pos[1]
                        cam_x += delta_cx
                        cam_z += delta_cz
                    riding_player_id = found_carrier_id
                    riding_prev_base_pos = c_pos
                else:
                    riding_player_id = None
                    riding_prev_base_pos = None

            # Kick animation progress (triggered with 'K')
            kick_amount = 0.0
            if is_kicking:
                kick_timer += dt
                if kick_timer >= kick_duration:
                    is_kicking = False
                    kick_timer = 0.0
                else:
                    kp = kick_timer / kick_duration
                    # Smooth attack and retract curve (peaks at kp=0.38)
                    if kp < 0.38:
                        kick_amount = math.sin((kp / 0.38) * (math.pi / 2))
                    else:
                        kick_amount = math.cos(((kp - 0.38) / 0.62) * (math.pi / 2))

                    # Check if kicking foot reached another chick during extension
                    if is_online and not is_fighting and kp <= 0.65 and kick_amount >= 0.45:
                        fwd_x = math.sin(cam_yaw)
                        fwd_z = math.cos(cam_yaw)
                        right_x = math.cos(cam_yaw)
                        right_z = -math.sin(cam_yaw)
                        foot_x = cam_x + fwd_x * (0.95 * kick_amount) + right_x * (kick_side * 0.16)
                        foot_z = cam_z + fwd_z * (0.95 * kick_amount) + right_z * (kick_side * 0.16)
                        foot_y = jump_offset_y + 0.35 * kick_amount
                        for pid, pdata in remote_players.items():
                            if pid in kick_hit_victims or pid not in remote_states:
                                continue
                            rs = remote_states[pid]
                            ox = rs.get("wx", 0.0)
                            oz = rs.get("wz", 0.0)
                            o_jump_y = rs.get("jump_offset_y", 0.0)
                            # Must be roughly in front of the kicker and within kicking foot reach
                            rel_fwd = (ox - cam_x) * fwd_x + (oz - cam_z) * fwd_z
                            if rel_fwd <= 0.10:
                                continue
                            dist_foot = math.hypot(ox - foot_x, oz - foot_z)
                            reach_rad = 1.15 if resolve_character_id(pdata) == "pangdun" else 1.05
                            if dist_foot <= reach_rad and abs(foot_y - (o_jump_y + 0.45)) < 1.15:
                                kick_hit_victims.add(pid)
                                push_dx = ox - cam_x
                                push_dz = oz - cam_z
                                plen = math.hypot(push_dx, push_dz)
                                if plen > 1e-4:
                                    push_dx /= plen
                                    push_dz /= plen
                                else:
                                    push_dx, push_dz = fwd_x, fwd_z
                                is_launch = (random.random() < 0.25)  # 75% push, 25% push + up accel + sideways land
                                net.send_kick_hit(pid, push_dx, push_dz, launch=is_launch, roll_dir=kick_side)

            # Punch animation progress (triggered with 'P')
            punch_amount = 0.0
            if is_punching:
                punch_timer += dt
                if punch_timer >= punch_duration:
                    is_punching = False
                    punch_timer = 0.0
                else:
                    pp = punch_timer / punch_duration
                    # Snappy boxing punch curve (fast jab forward at pp=0.32, smooth retract)
                    if pp < 0.32:
                        punch_amount = math.sin((pp / 0.32) * (math.pi / 2))
                    else:
                        punch_amount = math.cos(((pp - 0.32) / 0.68) * (math.pi / 2))

                    # Check if punching wing/fist reached another chicken during extension
                    if is_online and not is_fighting and pp <= 0.60 and punch_amount >= 0.45:
                        fwd_x = math.sin(cam_yaw)
                        fwd_z = math.cos(cam_yaw)
                        right_x = math.cos(cam_yaw)
                        right_z = -math.sin(cam_yaw)
                        fist_x = cam_x + fwd_x * (0.90 * punch_amount) + right_x * (punch_side * 0.22)
                        fist_z = cam_z + fwd_z * (0.90 * punch_amount) + right_z * (punch_side * 0.22)
                        fist_y = jump_offset_y + 0.98
                        for pid, pdata in remote_players.items():
                            if pid in punch_hit_victims or pid not in remote_states:
                                continue
                            rs = remote_states[pid]
                            ox = rs.get("wx", 0.0)
                            oz = rs.get("wz", 0.0)
                            o_jump_y = rs.get("jump_offset_y", 0.0)
                            rel_fwd = (ox - cam_x) * fwd_x + (oz - cam_z) * fwd_z
                            if rel_fwd <= 0.08:
                                continue
                            dist_fist = math.hypot(ox - fist_x, oz - fist_z)
                            reach_rad = 1.15 if resolve_character_id(pdata) == "pangdun" else 1.05
                            if dist_fist <= reach_rad and abs(fist_y - (o_jump_y + 0.95)) < 1.25:
                                punch_hit_victims.add(pid)
                                push_dx = ox - cam_x
                                push_dz = oz - cam_z
                                plen = math.hypot(push_dx, push_dz)
                                if plen > 1e-4:
                                    push_dx /= plen
                                    push_dz /= plen
                                else:
                                    push_dx, push_dz = fwd_x, fwd_z
                                is_headshot = (random.random() < 0.30)  # 70% pushed back, 30% headshot
                                net.send_punch_hit(pid, push_dx, push_dz, headshot=is_headshot, punch_side=punch_side)

            # Zombie tag arms animation progress (smoothly raises/lowers hands to neck level)
            # When holding or toggled on with 'T', arms raise up and stay steady at neck level
            keys_down = pygame.key.get_pressed()
            if is_kick_launched or side_lying_timer > 0.0 or local_ragdoll > 0.05 or local_headshot_phase != "none":
                is_kicking = False
                kick_timer = 0.0
                kick_amount = 0.0
                is_punching = False
                punch_timer = 0.0
                punch_amount = 0.0
                is_tagging = False
                tag_amount = 0.0
                if jump_state == "crouching":
                    jump_state = "idle"
                    crouch_timer = 0.0
                    jump_amount = 0.0
            is_tag_active = (not (is_kick_launched or side_lying_timer > 0.0 or local_ragdoll > 0.05 or local_headshot_phase != "none")) and (
                is_tagging or (keys_down[pygame.K_t] if not is_typing_chat else False)
            )
            if is_tag_active:
                tag_amount = min(1.0, tag_amount + 12.0 * dt)
            else:
                tag_amount = max(0.0, tag_amount - 10.0 * dt)

            # Crouch-then-Jump execution:
            # Step 1: Crouching down (bends legs, camera sinks down)
            # Step 2: Spring up into the air (un-crouches, launches high into the sky)
            crouch_eye_drop = 0.0
            if jump_state == "crouching":
                crouch_timer += dt
                cp = min(1.0, crouch_timer / crouch_duration)
                jump_amount = math.sin(cp * (math.pi / 2))
                crouch_eye_drop = -0.58 * jump_amount  # Camera drops down into crouch
                wing_flap_amount = 0.0
                if crouch_timer >= crouch_duration:
                    jump_state = "airborne"
                    jump_velocity_y = JUMP_IMPULSE
                    jump_offset_y = 0.08
                    jump_amount = 0.0  # Fully un-crouch and thrust upward!
            elif jump_state == "airborne":
                if launch_accel_timer > 0.0:
                    jump_velocity_y += 74.0 * dt
                    launch_accel_timer = max(0.0, launch_accel_timer - dt)
                jump_offset_y += jump_velocity_y * dt
                jump_velocity_y -= GRAVITY * dt
                jump_amount = 0.0      # Not crouching while jumping!
                wing_flap_amount = 1.0 # Wings flap while flying through the air
                if is_kick_launched:
                    # Ragdoll mode: tip into loose sprawl toward ±90 deg to land laying flat down on grass (NOT a backflip!)
                    local_ragdoll = 1.0
                    target_lay = kick_lay_dir * (math.pi * 0.5)
                    lay_step = math.radians(165.0) * dt * kick_lay_dir
                    if kick_lay_dir > 0:
                        local_lay_pitch = min(target_lay, local_lay_pitch + lay_step)
                    else:
                        local_lay_pitch = max(target_lay, local_lay_pitch + lay_step)
                    target_wobble = kick_roll_dir * math.radians(24.0)
                    local_rot_z += (target_wobble - local_rot_z) * min(1.0, 7.0 * dt)
                # Land on the ground (0.0) or atop another chick (landing_support_y):
                current_floor = max(0.0, landing_support_y)
                if jump_velocity_y <= 0.0 and jump_offset_y <= current_floor:
                    if is_kick_launched and not kick_bounced and jump_velocity_y < -4.2:
                        jump_offset_y = current_floor + 0.01
                        jump_velocity_y = min(2.1, -jump_velocity_y * 0.22)
                        kick_bounced = True
                    else:
                        jump_offset_y = current_floor
                        jump_velocity_y = 0.0
                        jump_state = "idle"   # Landed firmly on the ground or atop the player!
                        jump_amount = 0.0
                        wing_flap_amount = 0.0
                        if is_kick_launched:
                            is_kick_launched = False
                            local_lay_pitch = kick_lay_dir * (math.pi * 0.5)
                            local_rot_z = kick_roll_dir * math.radians(22.0)
                            local_ragdoll = 1.0
                            side_lying_timer = 1.0
            else:
                # Idle state: if standing on another chick, stay locked atop them as they move!
                current_floor = max(0.0, landing_support_y)
                if jump_offset_y > 0.0:
                    if landing_support_y > 0.0:
                        # Smoothly stick to their head/back
                        jump_offset_y = landing_support_y
                    elif jump_offset_y > 0.12:
                        jump_state = "airborne"
                        jump_velocity_y = 0.0
                    else:
                        jump_offset_y = 0.0
                jump_amount = 0.0
                wing_flap_amount = 0.0

            if is_fighting:
                eye_y = 1.65
            else:
                head_bob = math.sin(motion_cycle * 2.0 * math.pi) * (0.04 * run_weight + 0.02 * walk_weight)
                eye_y = head_bob + jump_offset_y + crouch_eye_drop

            # Sync position & posture with network only if online (mapped across the vast island)
            norm_x = max(0.05, min(0.95, (cam_x + ISLAND_RADIUS * 0.85) / (2.0 * ISLAND_RADIUS * 0.85) * 0.9 + 0.05))
            norm_y = max(0.05, min(0.95, (cam_z + ISLAND_RADIUS * 0.85) / (2.0 * ISLAND_RADIUS * 0.85) * 0.9 + 0.05))
            net.update_local_state(
                norm_x,
                norm_y,
                is_running,
                mouth_open,
                is_walking=is_walking,
                rot_y=cam_yaw,
                rot_z=local_rot_z,
                lay_pitch=local_lay_pitch,
                ragdoll=local_ragdoll,
                wx=cam_x,
                wz=cam_z,
                head_yaw=head_yaw,
                head_pitch=head_pitch,
                blink=is_blinking,
                kick_amount=kick_amount,
                kick_side=kick_side,
                punch_amount=punch_amount,
                punch_side=punch_side,
                jump_offset_y=jump_offset_y,
                jump_amount=jump_amount,
                tag_amount=tag_amount,
            )

        connected, is_host, my_id, my_color, remote_players = net.get_snapshot()

        # Fetch and dispatch incoming chats from remote chickens / players
        for chat_msg in net.fetch_new_chats():
            sender_id = int(chat_msg.get("id", -1))
            c_text = str(chat_msg.get("text", "")).strip()
            if not c_text:
                continue
            # Skip echo of local player's own chat messages (already added locally when sent)
            if my_id is not None and sender_id == my_id:
                continue
            if sender_id not in chat_bubbles:
                chat_bubbles[sender_id] = []
            chat_bubbles[sender_id].append({"text": c_text, "timer": 5.5, "duration": 5.5})
            chat_bubbles[sender_id] = chat_bubbles[sender_id][-4:]  # Limit to 4 stacked bubbles
            # Record in persistent chatbox
            rp_info = remote_players.get(sender_id, {})
            s_name = str(chat_msg.get("name") or rp_info.get("chick_name") or f"Player {sender_id}")
            chat_history.append({
                "sender": s_name,
                "text": c_text,
                "is_self": False,
                "sender_id": sender_id,
            })
            if len(chat_history) > 40:
                del chat_history[:-40]

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
            t_rot_z = float(pdata.get("rot_z", 0.0))
            t_lay_pitch = float(pdata.get("lay_pitch", 0.0))
            t_ragdoll = float(pdata.get("ragdoll", 0.0))
            t_head_yaw = pdata.get("head_yaw", 0.0)
            t_head_pitch = pdata.get("head_pitch", 0.0)
            t_run = 1.0 if pdata.get("running", False) else 0.0
            t_walk = 1.0 if pdata.get("walking", False) else 0.0
            t_blink = 1.0 if pdata.get("blink", False) else 0.0

            t_kick = float(pdata.get("kick_amount", 0.0))
            t_kick_side = float(pdata.get("kick_side", 1.0))
            t_punch = float(pdata.get("punch_amount", 0.0))
            t_punch_side = float(pdata.get("punch_side", 1.0))
            t_jump_y = float(pdata.get("jump_offset_y", 0.0))
            t_jump_amt = float(pdata.get("jump_amount", 0.0))

            if pid not in remote_states:
                remote_states[pid] = {
                    "wx": tw_x,
                    "wz": tw_z,
                    "rot_y": t_rot_y,
                    "rot_z": t_rot_z,
                    "lay_pitch": t_lay_pitch,
                    "ragdoll": t_ragdoll,
                    "head_yaw": t_head_yaw,
                    "head_pitch": t_head_pitch,
                    "run_weight": t_run,
                    "walk_weight": t_walk,
                    "blink_amount": t_blink,
                    "motion_cycle": 0.0,
                    "kick_amount": t_kick,
                    "kick_side": t_kick_side,
                    "punch_amount": t_punch,
                    "punch_side": t_punch_side,
                    "jump_offset_y": t_jump_y,
                    "jump_amount": t_jump_amt,
                    "tag_amount": float(pdata.get("tag_amount", 0.0)),
                }
            else:
                rs = remote_states[pid]
                rs["wx"] += (tw_x - rs["wx"]) * remote_alpha
                rs["wz"] += (tw_z - rs["wz"]) * remote_alpha
                rs["rot_y"] = wrap_angle(rs["rot_y"] + wrap_angle(t_rot_y - rs["rot_y"]) * remote_alpha)
                rs["rot_z"] = rs.get("rot_z", 0.0) + (t_rot_z - rs.get("rot_z", 0.0)) * min(1.0, 18.0 * dt)
                rs["lay_pitch"] = rs.get("lay_pitch", 0.0) + (t_lay_pitch - rs.get("lay_pitch", 0.0)) * min(1.0, 18.0 * dt)
                rs["ragdoll"] = rs.get("ragdoll", 0.0) + (t_ragdoll - rs.get("ragdoll", 0.0)) * min(1.0, 18.0 * dt)
                rs["head_yaw"] += (t_head_yaw - rs["head_yaw"]) * remote_alpha
                rs["head_pitch"] += (t_head_pitch - rs["head_pitch"]) * remote_alpha
                rs["run_weight"] += (t_run - rs["run_weight"]) * min(1.0, 8.0 * dt)
                rs["walk_weight"] += (t_walk - rs["walk_weight"]) * min(1.0, 8.0 * dt)
                if rs["blink_amount"] < t_blink:
                    rs["blink_amount"] = min(t_blink, rs["blink_amount"] + 18.0 * dt)
                elif rs["blink_amount"] > t_blink:
                    rs["blink_amount"] = max(t_blink, rs["blink_amount"] - 14.0 * dt)
                # Fast responsive interpolation for punches and kicks:
                rs["kick_amount"] += (t_kick - rs.get("kick_amount", 0.0)) * min(1.0, 24.0 * dt)
                rs["kick_side"] = t_kick_side
                rs["punch_amount"] += (t_punch - rs.get("punch_amount", 0.0)) * min(1.0, 24.0 * dt)
                rs["punch_side"] = t_punch_side
                rs["jump_offset_y"] += (t_jump_y - rs.get("jump_offset_y", 0.0)) * min(1.0, 24.0 * dt)
                rs["jump_amount"] += (t_jump_amt - rs.get("jump_amount", 0.0)) * min(1.0, 24.0 * dt)
                t_tag = float(pdata.get("tag_amount", 0.0))
                rs["tag_amount"] = rs.get("tag_amount", 0.0) + (t_tag - rs.get("tag_amount", 0.0)) * min(1.0, 18.0 * dt)
                loco = max(rs["run_weight"], rs["walk_weight"])
                if loco > 0.001:
                    stride_spd = (3.2 * rs["run_weight"]) + (1.8 * rs["walk_weight"] * (1.0 - rs["run_weight"]))
                    rs["motion_cycle"] += dt * max(0.4, stride_spd)

        # If local chick is ragdoll-laying down on grass, smoothly tilt pitch toward sky/grass and lower eye level
        if is_online and not is_fighting and abs(local_lay_pitch) > 1e-3:
            total_pitch = max(-1.25, min(1.25, total_pitch + (-local_lay_pitch * 0.65)))
            eye_y -= abs(math.sin(local_lay_pitch)) * 0.42

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

        # Eye height adjustments:
        # Carmen (younger sister): shorter eye level (eye height = 2.25 vs 3.0)
        # 小胖墩 (fat chicken): slightly taller/heavier stance (eye height = 3.30)
        is_playing_carmen = (is_online and selected_character == "carmen")
        is_playing_pangdun = (is_online and selected_character == "pangdun")
        is_playing_xiaoliuzi = (is_online and selected_character == "xiaoliuzi")
        if is_playing_carmen:
            current_ground_y = GROUND_Y * 0.75
        elif is_playing_pangdun:
            current_ground_y = GROUND_Y * 1.10
        elif is_playing_xiaoliuzi:
            current_ground_y = GROUND_Y * 1.08
        else:
            current_ground_y = GROUND_Y

        cam_roll = local_rot_z if (is_online and not is_fighting) else 0.0
        has_cam_roll = abs(cam_roll) > 1e-4
        cos_roll = math.cos(cam_roll)
        sin_roll = math.sin(cam_roll)

        def roll_cam_xy(rx: float, ry: float) -> tuple[float, float]:
            if has_cam_roll:
                return (rx * cos_roll + ry * sin_roll, -rx * sin_roll + ry * cos_roll)
            return (rx, ry)

        def to_cam(wx: float, wy: float, wz: float) -> tuple[float, float, float]:
            dx = wx - cam_x
            dy = wy - eye_y
            dz = wz - cam_z
            rx = dx * cos_yaw - dz * sin_yaw
            rz = dx * sin_yaw + dz * cos_yaw
            ry = dy * cos_pitch - rz * sin_pitch
            rz_p = dy * sin_pitch + rz * cos_pitch
            if has_cam_roll:
                rx, ry = roll_cam_xy(rx, ry)
            return (rx, ry, rz_p)

        # 1a. Horizon & ground / ocean rendering (supports sideways roll when kicked!):
        raw_horizon_y = hh + math.tan(total_pitch) * focal
        horizon_y = max(0, min(win_h, round(raw_horizon_y)))
        ground_col_fill = GRASS_GROUND_COLOR if is_online else OCEAN_WATER_COLOR
        if abs(local_rot_z) > 1e-3 and is_online:
            # Draw tilted grass ground polygon below rotated horizon line
            cos_r = math.cos(local_rot_z)
            sin_r = math.sin(local_rot_z)
            hy_rel = raw_horizon_y - hh
            big = max(win_w, win_h) * 2.5
            local_ground_pts = [(-big, hy_rel), (big, hy_rel), (big, hy_rel + big), (-big, hy_rel + big)]
            tilted_ground_pts = [
                (round(hw + px * cos_r - py * sin_r), round(hh + px * sin_r + py * cos_r))
                for px, py in local_ground_pts
            ]
            pygame.draw.polygon(screen, ground_col_fill, tilted_ground_pts)
        else:
            if horizon_y < win_h:
                screen.fill(ground_col_fill, pygame.Rect(0, horizon_y, win_w, win_h - horizon_y))

        # 1a-2. RENDER PUFFY STORYBOOK WHITE CLOUDS IN THE SKY:
        # Floating high across the sky dome, drifting gently with the breeze!
        sky_dome_r = 160.0
        for c_data in sky_clouds_data:
            c_az = c_data["az"] + anim_time * c_data["drift_spd"]
            c_el = c_data["el"]
            c_scale = c_data["scale"]

            # Vector in world sky relative to eye
            c_dx = sky_dome_r * math.cos(c_el) * math.sin(c_az)
            c_dz = sky_dome_r * math.cos(c_el) * math.cos(c_az)
            c_dy = sky_dome_r * math.sin(c_el)

            # Transform into camera coordinates
            rx = c_dx * cos_yaw - c_dz * sin_yaw
            rz_fwd = c_dx * sin_yaw + c_dz * cos_yaw
            c_cy = c_dy * cos_pitch - rz_fwd * sin_pitch
            c_cz = c_dy * sin_pitch + rz_fwd * cos_pitch

            if c_cz > 1.0:
                r_cx, r_cy = roll_cam_xy(rx, c_cy)
                csx = hw + (r_cx / c_cz) * focal
                csy = hh - (r_cy / c_cz) * focal
                base_r = (c_scale / c_cz) * focal

                # Only draw if within screen view
                if -base_r * 2 <= csx <= win_w + base_r * 2 and -base_r * 2 <= csy <= win_h + base_r * 2:
                    # Draw subtle cloud shadow base first, then bright fluffy white cloud puffs
                    for shadow_pass, col in ((True, SKY_CLOUD_SHADOW), (False, SKY_CLOUD_WHITE)):
                        y_off = (base_r * 0.12) if shadow_pass else 0.0
                        for px_rel, py_rel, pw_rel, ph_rel in cloud_puffs:
                            px = csx + px_rel * base_r
                            py = csy + py_rel * base_r + y_off
                            pw = max(4, round(base_r * pw_rel * 1.5))
                            ph = max(3, round(base_r * ph_rel * 1.2))
                            # Clip below horizon so clouds don't draw on the grass/ocean
                            p_rect = pygame.Rect(round(px - pw * 0.5), round(py - ph * 0.5), pw, ph)
                            if has_cam_roll or p_rect.bottom < horizon_y + 10 or not is_online:
                                pygame.draw.ellipse(screen, col, p_rect)

            # Render the Giant Island (Top lush plateau, Sandy beach edge, and 3D Rocky Cliffs)
            # Compute island outline vertices at top plateau (GROUND_Y) and water base (ISLAND_WATER_Y)
            top_rim_cam: list[tuple[float, float, float]] = []
            top_rim_scr: list[tuple[int, int] | None] = []
            bot_rim_cam: list[tuple[float, float, float]] = []
            bot_rim_scr: list[tuple[int, int] | None] = []

            for i in range(ISLAND_SEGMENTS):
                ang = (2.0 * math.pi * i) / ISLAND_SEGMENTS
                # Organic island shape with wavy shorelines
                r = ISLAND_RADIUS + 9.5 * math.sin(ang * 4.0) + 5.5 * math.cos(ang * 7.0)
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

        # When staring from overview, render grass patches near center; otherwise render player grass rings
        for step, min_d, max_d, tufts, b_scale, sway_amp in (
            ()
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

                    c_cam = to_cam(cx, current_ground_y, cz)
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

                        b_cam = to_cam(bx, current_ground_y, bz)
                        fov_lim = b_cam[2] * (half_fov_tan * (1.8 if has_cam_roll else 1.0)) + 0.5
                        if b_cam[2] > near_z and abs(b_cam[0]) <= fov_lim:
                            blades.append((b_cam[2], bx, bz, b_cam, th, b_scale, sway_amp))

        blades.sort(key=lambda item: item[0], reverse=True)
        for bz_cam, bx, bz, b_cam, th, b_scale, sway_amp in blades:
            height = (0.22 + ((th >> 4) & 7) * 0.02) * b_scale
            local_sway = (base_sway + math.sin(anim_time * 2.6 + bx * 0.9 + bz * 0.7) * 0.03) * sway_amp
            t_cam = to_cam(bx + local_sway, current_ground_y + height, bz)
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
        # Consistent true-perspective scaling:
        # Distance is based on horizontal ground distance (so chicks naturally grow larger as you walk toward them)
        # and remains stable when looking up or down.
        visible_remotes = []
        for pid, pdata in remote_players.items():
            if pid not in remote_states:
                continue
            rs = remote_states[pid]
            rwx, rwz = rs["wx"], rs["wz"]
            is_carmelito = pdata.get("is_carmelito", True)
            r_jump_y = rs.get("jump_offset_y", 0.0)
            rwy = (current_ground_y + r_jump_y) if is_carmelito else (0.0 + 0.12 * math.sin(anim_time * 2.8))

            # Horizontal relative position in camera coordinate system (independent of vertical pitch)
            dx = rwx - cam_x
            dz = rwz - cam_z
            rx_unpitched = dx * cos_yaw - dz * sin_yaw
            rz_forward = dx * sin_yaw + dz * cos_yaw
            horiz_dist = max(0.40, math.hypot(dx, dz))

            # Screen projection of the chick's feet
            dy_feet = rwy - eye_y
            ry_cam_feet = dy_feet * cos_pitch - rz_forward * sin_pitch
            rz_cam_feet = dy_feet * sin_pitch + rz_forward * cos_pitch

            # In front of player if either forward distance is positive or camera z is positive
            if rz_forward > 0.15 or rz_cam_feet > 0.15:
                visible_remotes.append((horiz_dist, pid, pdata, rs, rx_unpitched, ry_cam_feet, rz_forward))

        # PASS 1: Render ALL ground shadows first (so shadows never occlude any chick's feet or body)
        for horiz_dist, pid, pdata, rs, rx_unpitched, ry_cam_feet, rz_forward in visible_remotes:
            if is_fighting and pid == fight_opponent_pid:
                continue
            if pdata.get("is_carmelito", True):
                rwx, rwz = rs["wx"], rs["wz"]
                remote_char = resolve_character_id(pdata)
                char_scale = 0.82 if remote_char == "carmen" else (1.15 if remote_char in ("pangdun", "小胖墩", "belino", "coquenpate") else (1.08 if remote_char in ("xiaoliuzi", "小六子", "coqsix", "克西斯") else 1.0))
                
                # Ground shadow screen position
                dy_g = current_ground_y - eye_y
                g_ry_cam = dy_g * cos_pitch - rz_forward * sin_pitch
                g_rx_r, g_ry_r = roll_cam_xy(rx_unpitched, g_ry_cam)
                g_sx = hw + (g_rx_r / horiz_dist) * focal
                g_sy = hh - (g_ry_r / horiz_dist) * focal
                
                sh_w = max(8, round((1.18 * char_scale / horiz_dist) * focal))
                sh_h = max(3, round((0.38 * char_scale / horiz_dist) * focal))
                shadow_rect = pygame.Rect(round(g_sx - sh_w * 0.5), round(g_sy - sh_h * 0.4), sh_w, sh_h)
                pygame.draw.ellipse(screen, GRASS_SHADOW_COLOR, shadow_rect)

        # PASS 2: Render 3D chick models and nameplates sorted from furthest to nearest
        visible_remotes.sort(key=lambda item: item[0], reverse=True)
        for horiz_dist, pid, pdata, rs, rx_unpitched, ry_cam_feet, rz_forward in visible_remotes:
            if is_fighting and pid == fight_opponent_pid:
                continue  # Rendered in dedicated battle clash scene below!

            # Chick feet screen position on grass
            rem_rx_r, rem_ry_r = roll_cam_xy(rx_unpitched, ry_cam_feet)
            sx = hw + (rem_rx_r / horiz_dist) * focal
            sy = hh - (rem_ry_r / horiz_dist) * focal

            if pdata.get("is_carmelito", True):
                remote_char = resolve_character_id(pdata)
                if remote_char == "carmen":
                    rem_scale = CARMELITO_WORLD_SCALE * 0.82
                elif remote_char in ("pangdun", "小胖墩", "belino", "coquenpate"):
                    rem_scale = CARMELITO_WORLD_SCALE * 1.15
                elif remote_char in ("xiaoliuzi", "小六子", "coqsix", "克西斯"):
                    rem_scale = CARMELITO_WORLD_SCALE * 1.08
                else:
                    rem_scale = CARMELITO_WORLD_SCALE

                # As you get closer, the chick naturally gets bigger!
                model_scale = (rem_scale / horiz_dist) * focal
                rel_rot_y = math.pi - (rs["rot_y"] - total_yaw)
                rel_rot_x = max(-0.55, min(0.65, 0.04 - total_pitch))

                rem_rg_val = rs.get("ragdoll", 0.0)
                if rem_rg_val > 0.01:
                    if pid not in remote_ragdolls:
                        remote_ragdolls[pid] = ChickRagdollSim()
                    rem_rg_pose = remote_ragdolls[pid].step(
                        dt=dt,
                        wx=rs["wx"],
                        jump_y=rs.get("jump_offset_y", 0.0),
                        wz=rs["wz"],
                        world_rot_y=rs["rot_y"],
                        rot_z=rs.get("rot_z", 0.0),
                        lay_pitch=rs.get("lay_pitch", 0.0),
                        ragdoll=rem_rg_val,
                        scale=rem_scale,
                    )
                else:
                    if pid in remote_ragdolls:
                        remote_ragdolls[pid].reset()
                    rem_rg_pose = None

                model_3d.render(
                    surface=screen,
                    screen_pos=(sx, sy),
                    scale=model_scale,
                    rot_y=rel_rot_y,
                    rot_x=rel_rot_x,
                    rot_z=rs.get("rot_z", 0.0) - cam_roll,
                    lay_pitch=rs.get("lay_pitch", 0.0),
                    ragdoll=rem_rg_val,
                    ragdoll_seed=pid * 1.73,
                    ragdoll_pose=rem_rg_pose,
                    head_yaw=rs["head_yaw"],
                    head_pitch=rs["head_pitch"],
                    mouth_open=pdata.get("mouth", False),
                    run_cycle=rs["motion_cycle"],
                    is_running=pdata.get("running", False),
                    run_weight=rs["run_weight"],
                    is_walking=pdata.get("walking", False),
                    walk_weight=rs["walk_weight"],
                    blink=rs["blink_amount"],
                    character=remote_char,
                    kick_amount=rs.get("kick_amount", 0.0),
                    kick_side=rs.get("kick_side", 1.0),
                    punch_amount=rs.get("punch_amount", 0.0),
                    punch_side=rs.get("punch_side", 1.0),
                    jump_amount=rs.get("jump_amount", 0.0),
                    tag_amount=rs.get("tag_amount", 0.0),
                )

                # Floating nameplates above chicken's comb:
                # 1) Chicken's Chinese name (e.g. "小胖墩", "卡梅利多", "卡门")
                # 2) AI / player's name stacked right above it
                label_cam = to_cam(rs["wx"], current_ground_y + 2.38 * rem_scale, rs["wz"])
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

                # Chat bubbles for dot players as well
                if pid in chat_bubbles:
                    cur_bottom = round(sy) - radius - 10
                    bubble_font_size = max(14, min(24, round((0.42 / rz_p) * focal)))
                    for b in reversed(chat_bubbles[pid]):
                        progress = b["timer"] / b["duration"]
                        alpha = min(1.0, progress * 3.0)
                        b_h = draw_chat_bubble(
                            screen,
                            b["text"],
                            center_x=round(sx),
                            bottom_y=cur_bottom,
                            font_size=bubble_font_size,
                            alpha=alpha,
                            tail_direction="down",
                        )
                        cur_bottom -= b_h

        # 1d-battle. DEDICATED 3D BATTLE: PUSHING, KICKING & KNOCKING DOWN EACH OTHER
        if is_fighting:
            # Battle midpoint and separation direction
            dx_fight = fight_belino_x - fight_carmelito_x
            dz_fight = fight_belino_z - fight_carmelito_z
            fight_dist = max(0.8, math.hypot(dx_fight, dz_fight))
            dir_x = dx_fight / fight_dist
            dir_z = dz_fight / fight_dist
            mid_x = (fight_carmelito_x + fight_belino_x) * 0.5
            mid_z = (fight_carmelito_z + fight_belino_z) * 0.5

            # 11-second looping martial arts choreography
            cycle_time = 11.0
            phase = fight_timer % cycle_time

            carm_rot_x = 0.05
            bel_rot_x = 0.05
            carm_wy = current_ground_y
            bel_wy = current_ground_y
            carm_mouth = False
            bel_mouth = False
            carm_run_cycle = fight_timer * 4.0
            bel_run_cycle = fight_timer * 4.0
            carm_head_yaw = 0.0
            bel_head_yaw = 0.0
            action_banner_text = ""

            if phase < 2.8:
                # PHASE 1: CHEST PUSH & TACKLE CONTEST (Head-to-head wrestling and pushing!)
                push_wobble = math.sin(phase * 15.0) * 0.16
                carm_wx = mid_x - dir_x * (0.42 + push_wobble)
                carm_wz = mid_z - dir_z * (0.42 + push_wobble)
                bel_wx = mid_x + dir_x * (0.42 - push_wobble)
                bel_wz = mid_z + dir_z * (0.42 - push_wobble)
                carm_rot_x = 0.28   # Leaning forward pushing
                bel_rot_x = 0.34    # Heavy chest forward pushing
                carm_mouth = True
                bel_mouth = True
                carm_head_yaw = math.sin(phase * 16.0) * 0.18
                bel_head_yaw = -math.sin(phase * 16.0) * 0.18
                action_banner_text = "PUSH & SHOVE!"

            elif phase < 5.8:
                # PHASE 2: CARMELITO FLYING KICK & KNOCKS DOWN BELINO!
                p = (phase - 2.8) / 3.0
                if p < 0.32:
                    # Carmelito leaps into the air with legs forward
                    jump_p = p / 0.32
                    jump_arc = math.sin(jump_p * math.pi)
                    carm_wy = current_ground_y + jump_arc * 0.95
                    carm_wx = mid_x - dir_x * (0.85 - jump_p * 0.42)
                    carm_wz = mid_z - dir_z * (0.85 - jump_p * 0.42)
                    carm_rot_x = 0.50  # Kick forward posture!
                    carm_mouth = True
                    bel_wx = mid_x + dir_x * 0.55
                    bel_wz = mid_z + dir_z * 0.55
                    action_banner_text = "FLYING KICK!"
                elif p < 0.72:
                    # IMPACT: Kick hits! Belino is knocked down flat on his back!
                    fall_p = (p - 0.32) / 0.40
                    carm_wy = current_ground_y
                    carm_wx = mid_x - dir_x * 0.35
                    carm_wz = mid_z - dir_z * 0.35
                    carm_rot_x = 0.12
                    bel_wx = mid_x + dir_x * (0.60 + fall_p * 0.90)
                    bel_wz = mid_z + dir_z * (0.60 + fall_p * 0.90)
                    # Belino knocked down onto the grass on his back:
                    bel_rot_x = -1.30  # Knocked flat onto back!
                    bel_wy = current_ground_y - 0.24
                    bel_mouth = True
                    bel_run_cycle = fight_timer * 6.0  # Legs kicking comically in the air
                    bel_head_yaw = math.sin(fight_timer * 14.0) * 0.25
                    action_banner_text = "BELINO KNOCKED DOWN!"
                else:
                    # Belino rolls back up onto his feet
                    rec_p = (p - 0.72) / 0.28
                    carm_wx = mid_x - dir_x * 0.65
                    carm_wz = mid_z - dir_z * 0.65
                    bel_wx = mid_x + dir_x * 1.50
                    bel_wz = mid_z + dir_z * 1.50
                    bel_rot_x = -1.30 * (1.0 - rec_p) + 0.10 * rec_p
                    bel_wy = current_ground_y - 0.24 * (1.0 - rec_p)
                    action_banner_text = "RECOVERING..."

            elif phase < 8.8:
                # PHASE 3: BELINO CHARGES & KNOCKS DOWN CARMELITO!
                p = (phase - 5.8) / 3.0
                if p < 0.32:
                    # Belino charges forward with heavy push
                    charge_p = p / 0.32
                    bel_wx = mid_x + dir_x * (1.50 - charge_p * 1.15)
                    bel_wz = mid_z + dir_z * (1.50 - charge_p * 1.15)
                    bel_rot_x = 0.40  # Head-down charge
                    bel_mouth = True
                    carm_wx = mid_x - dir_x * 0.65
                    carm_wz = mid_z - dir_z * 0.65
                    action_banner_text = "HEAVY BELLY CHARGE!"
                elif p < 0.72:
                    # IMPACT: Belino knocks Carmelito down onto his back!
                    knock_p = (p - 0.32) / 0.40
                    bel_wx = mid_x + dir_x * 0.25
                    bel_wz = mid_z + dir_z * 0.25
                    bel_rot_x = 0.22
                    bel_mouth = True
                    carm_wx = mid_x - dir_x * (0.65 + knock_p * 0.90)
                    carm_wz = mid_z - dir_z * (0.65 + knock_p * 0.90)
                    # Carmelito knocked down onto the grass on his back:
                    carm_rot_x = -1.30  # Knocked flat onto back!
                    carm_wy = current_ground_y - 0.22
                    carm_mouth = True
                    carm_run_cycle = fight_timer * 6.0  # Legs kicking comically in air
                    carm_head_yaw = math.sin(fight_timer * 14.0) * 0.25
                    action_banner_text = "CARMELITO KNOCKED DOWN!"
                else:
                    # Carmelito springs back up onto his feet
                    rec_p = (p - 0.72) / 0.28
                    carm_wx = mid_x - dir_x * 1.55
                    carm_wz = mid_z - dir_z * 1.55
                    carm_rot_x = -1.30 * (1.0 - rec_p) + 0.06 * rec_p
                    carm_wy = current_ground_y - 0.22 * (1.0 - rec_p)
                    bel_wx = mid_x + dir_x * 0.55
                    bel_wz = mid_z + dir_z * 0.55
                    action_banner_text = "GETTING UP!"

            else:
                # PHASE 4: MID-AIR JUMP KICKS & HIGH CLASH!
                p = (phase - 8.8) / 2.2
                jump_arc = math.sin(p * math.pi)
                carm_wy = current_ground_y + jump_arc * 0.88
                bel_wy = current_ground_y + jump_arc * 0.82
                carm_wx = mid_x - dir_x * (0.80 - jump_arc * 0.35)
                carm_wz = mid_z - dir_z * (0.80 - jump_arc * 0.35)
                bel_wx = mid_x + dir_x * (0.80 - jump_arc * 0.35)
                bel_wz = mid_z + dir_z * (0.80 - jump_arc * 0.35)
                carm_rot_x = 0.42  # Flying rooster kick!
                bel_rot_x = 0.38   # Flying rooster kick!
                carm_mouth = True
                bel_mouth = True
                action_banner_text = "ROOSTER KICK CLASH!"

            # Sort Carmelito and Belino by camera depth
            carm_cam = to_cam(carm_wx, carm_wy, carm_wz)
            bel_cam = to_cam(bel_wx, bel_wy, bel_wz)

            combatants = [
                (carm_cam[2], "carmelito", carm_wx, carm_wy, carm_wz, carm_cam, math.atan2(dir_x, dir_z), carm_rot_x, carm_mouth, carm_run_cycle, carm_head_yaw, CARMELITO_WORLD_SCALE, CHICK_NAME),
                (bel_cam[2], "pangdun", bel_wx, bel_wy, bel_wz, bel_cam, math.atan2(-dir_x, -dir_z), bel_rot_x, bel_mouth, bel_run_cycle, bel_head_yaw, CARMELITO_WORLD_SCALE * 1.15, PANGDUN_NAME),
            ]
            combatants.sort(key=lambda item: item[0], reverse=True)

            for depth, c_char, c_wx, c_wy, c_wz, c_cam, face_ang, c_rot_x, c_mouth, c_rcycle, c_hyaw, c_scale, c_name in combatants:
                if c_cam[2] <= near_z:
                    continue
                csx = hw + (c_cam[0] / c_cam[2]) * focal
                csy = hh - (c_cam[1] / c_cam[2]) * focal

                # Shadow beneath chick (moves slightly if in mid-air jump)
                ground_cam = to_cam(c_wx, current_ground_y, c_wz)
                if ground_cam[2] > near_z:
                    gsx = hw + (ground_cam[0] / ground_cam[2]) * focal
                    gsy = hh - (ground_cam[1] / ground_cam[2]) * focal
                    c_sh_w = max(10, round((1.2 * (c_scale / CARMELITO_WORLD_SCALE) / ground_cam[2]) * focal))
                    c_sh_h = max(4, round((0.40 * (c_scale / CARMELITO_WORLD_SCALE) / ground_cam[2]) * focal))
                    pygame.draw.ellipse(screen, GRASS_SHADOW_COLOR, pygame.Rect(round(gsx - c_sh_w * 0.5), round(gsy - c_sh_h * 0.4), c_sh_w, c_sh_h))

                c_mscale = (c_scale / c_cam[2]) * focal
                rel_rot_y = math.pi - (face_ang - total_yaw)
                rel_rot_x = max(-1.45, min(0.95, c_rot_x - total_pitch))

                model_3d.render(
                    surface=screen,
                    screen_pos=(csx, csy),
                    scale=c_mscale,
                    rot_y=rel_rot_y,
                    rot_x=rel_rot_x,
                    head_yaw=c_hyaw,
                    head_pitch=-0.12 if c_rot_x < -0.5 else 0.10,
                    mouth_open=c_mouth,
                    run_cycle=c_rcycle,
                    is_running=True,
                    run_weight=1.0,
                    is_walking=False,
                    walk_weight=0.0,
                    blink=0.0,
                    character=c_char,
                )

                # Name badge floating above battling chick
                lbl_y = c_wy + (1.2 if c_rot_x < -0.5 else 2.38) * c_scale
                lbl_cam = to_cam(c_wx, lbl_y, c_wz)
                if lbl_cam[2] > near_z:
                    lsx = round(hw + (lbl_cam[0] / lbl_cam[2]) * focal)
                    lsy = round(hh - (lbl_cam[1] / lbl_cam[2]) * focal)
                    raw_px = max(14, min(32, round((0.48 / lbl_cam[2]) * focal)))
                    bucket_px = max(12, min(32, (raw_px // 2) * 2))
                    chick_badge = get_nameplate_surface(c_name, bucket_px)
                    screen.blit(chick_badge, (lsx - chick_badge.get_width() // 2, lsy - chick_badge.get_height() // 2))

        # 1e. RENDER OWN FEET ONLY WHEN ONLINE (visible when looking down, kicking with 'K', crouching or jumping with 'J'!)
        if is_online and not is_fighting and (head_pitch < -0.35 or kick_amount > 0.001 or jump_amount > 0.08 or jump_offset_y > 0.05):
            cos_body = math.cos(cam_yaw)
            sin_body = math.sin(cam_yaw)

            def body_to_cam(bx: float, by: float, bz: float) -> tuple[float, float, float]:
                wx = cam_x + bx * cos_body + bz * sin_body
                wz = cam_z - bx * sin_body + bz * cos_body
                return to_cam(wx, by, wz)

            feet_faces, foot_shadows = model_3d.build_first_person_feet_faces(
                ground_y=current_ground_y + jump_offset_y,
                run_cycle=motion_cycle,
                run_weight=run_weight,
                walk_weight=walk_weight,
                character=selected_character,
                kick_amount=kick_amount,
                kick_side=kick_side,
                jump_amount=jump_amount,
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

        # 1e. RENDER OWN TAG HANDS EXTENDED FORWARD IN FIRST PERSON (T KEY)
        if is_online and not is_fighting and tag_amount > 0.001 and punch_amount <= 0.001:
            cos_body = math.cos(cam_yaw)
            sin_body = math.sin(cam_yaw)

            def tag_to_cam(bx: float, by: float, bz: float) -> tuple[float, float, float]:
                # In body space, attached firmly at shoulder/neck level relative to eyes
                wx = cam_x + bx * cos_body + bz * sin_body
                wz = cam_z - bx * sin_body + bz * cos_body
                wy = eye_y + by
                return to_cam(wx, wy, wz)

            tag_hand_faces = model_3d.build_first_person_tag_hands(
                ground_y=current_ground_y + jump_offset_y,
                tag_amount=tag_amount,
                head_yaw=head_yaw,
                head_pitch=head_pitch,
                character=selected_character,
            )

            tag_projected: list[tuple[float, list[tuple[int, int]], tuple[int, int, int], bool]] = []
            for quad_verts, base_col, has_contour in tag_hand_faces:
                cam_verts = [tag_to_cam(*v) for v in quad_verts]
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
                tag_projected.append((avg_z, pts, face_col, has_contour and view_cos < 0.34))

            tag_projected.sort(key=lambda item: item[0], reverse=True)
            for _, pts, f_col, draw_ink in tag_projected:
                if len(pts) >= 3:
                    pygame.draw.polygon(screen, f_col, pts)
                    if draw_ink:
                        pygame.draw.polygon(screen, COLOR_INK_LINE, pts, 1)

        # 1f. RENDER OWN PUNCH / WING STRIKE IN FIRST PERSON (P KEY)
        if is_online and not is_fighting and punch_amount > 0.001:
            cos_body = math.cos(cam_yaw)
            sin_body = math.sin(cam_yaw)

            def punch_to_cam(bx: float, by: float, bz: float) -> tuple[float, float, float]:
                # In body space, attach at shoulder level relative to eye
                # bx: horizontal offset (right/left), by: vertical offset relative to eye, bz: forward offset
                wx = cam_x + bx * cos_body + bz * sin_body
                wz = cam_z - bx * sin_body + bz * cos_body
                wy = eye_y + by
                return to_cam(wx, wy, wz)

            punch_faces = model_3d.build_first_person_punch_faces(
                punch_amount=punch_amount,
                punch_side=punch_side,
                character=selected_character,
            )

            punch_projected: list[tuple[float, list[tuple[int, int]], tuple[int, int, int], bool]] = []
            for quad_verts, base_col, has_contour in punch_faces:
                cam_verts = [punch_to_cam(*v) for v in quad_verts]
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
                punch_projected.append((avg_z, pts, face_col, has_contour and view_cos < 0.34))

            punch_projected.sort(key=lambda item: item[0], reverse=True)
            for _, pts, f_col, draw_ink in punch_projected:
                if len(pts) >= 3:
                    pygame.draw.polygon(screen, f_col, pts)
                    if draw_ink:
                        pygame.draw.polygon(screen, COLOR_INK_LINE, pts, 1)

                # 1g. RENDER OWN WINGS FLAPPING IN FIRST PERSON (J KEY JUMP)
        if is_online and not is_fighting and wing_flap_amount > 0.001 and punch_amount <= 0.001:
            cos_body = math.cos(cam_yaw)
            sin_body = math.sin(cam_yaw)

            def wing_to_cam(bx: float, by: float, bz: float) -> tuple[float, float, float]:
                wx = cam_x + bx * cos_body + bz * sin_body
                wz = cam_z - bx * sin_body + bz * cos_body
                wy = eye_y + by
                return to_cam(wx, wy, wz)

            jump_wing_faces = model_3d.build_first_person_jump_wings(
                jump_amount=wing_flap_amount,
                character=selected_character,
                anim_time=anim_time,
            )

            wing_projected: list[tuple[float, list[tuple[int, int]], tuple[int, int, int], bool]] = []
            for quad_verts, base_col, has_contour in jump_wing_faces:
                cam_verts = [wing_to_cam(*v) for v in quad_verts]
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
                brightness = 0.78 + 0.22 * diffuse
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
                wing_projected.append((avg_z, pts, face_col, has_contour and view_cos < 0.38))

            wing_projected.sort(key=lambda item: item[0], reverse=True)
            for _, pts, f_col, draw_ink in wing_projected:
                if len(pts) >= 3:
                    pygame.draw.polygon(screen, f_col, pts)
                    if draw_ink:
                        pygame.draw.polygon(screen, COLOR_INK_LINE, pts, 1)

        # --- 2b. 3D CHAT BUBBLE ANCHORED DIRECTLY ABOVE LOCAL PLAYER (VISIBLE WHEN LOOKING UP) ---
        if is_online:
            # Carmelito's head/comb is above eye level. The chat bubble floats in 3D world space
            # directly above Carmelito (slightly in front of eyes so looking up brings it into full view).
            if -1 in chat_bubbles:
                cos_body = math.cos(cam_yaw)
                sin_body = math.sin(cam_yaw)
                # Anchor in front and directly above head
                local_bx = 0.0
                local_bz = 0.95
                local_wx = cam_x + local_bx * cos_body + local_bz * sin_body
                local_wz = cam_z - local_bx * sin_body + local_bz * cos_body
                local_wy = eye_y + (1.08 if is_playing_carmen else 1.35)  # Above head & comb

                bubble_cam = to_cam(local_wx, local_wy, local_wz)
                # Ensure safe distance in front of camera plane (0.35)
                if bubble_cam[2] > 0.35:
                    bx_scr = round(hw + (bubble_cam[0] / bubble_cam[2]) * focal)
                    by_scr = round(hh - (bubble_cam[1] / bubble_cam[2]) * focal)
                    cur_bottom = by_scr
                    local_font_size = max(18, min(32, round((0.46 / bubble_cam[2]) * focal)))
                    for b in reversed(chat_bubbles[-1]):
                        if cur_bottom < -60:
                            break  # Avoid rendering far beyond screen top
                        progress = b["timer"] / b["duration"]
                        alpha = min(1.0, progress * 3.0)
                        b_h = draw_chat_bubble(
                            screen,
                            b["text"],
                            center_x=bx_scr,
                            bottom_y=cur_bottom,
                            font_size=local_font_size,
                            alpha=alpha,
                            tail_direction="down",
                        )
                        cur_bottom -= b_h

            # --- 2c. INTERACTIVE FIGHT UI (CARMELITO VS BELINO / 小胖墩) ---
            if is_online:
                if is_fighting:
                    # During battle: FIGHT banner at bottom + LEAVE button directly above it
                    btn_px = max(22, min(40, ((round(win_h * 0.052)) // 2) * 2))
                    btn_outline = max(2, round(btn_px * 0.07))

                    # 1. Fight banner button at bottom center
                    banner_txt = action_banner_text if action_banner_text else "FIGHTING!"
                    f_surf = get_outlined_text_surface(banner_txt, btn_px, outline_px=btn_outline)
                    f_w = f_surf.get_width() + 40
                    f_h = f_surf.get_height() + 18
                    f_x = (win_w - f_w) // 2
                    f_y = win_h - f_h - 26

                    f_rect = pygame.Rect(f_x, f_y, f_w, f_h)
                    pygame.draw.rect(screen, (0, 0, 0, 80), pygame.Rect(f_x + 3, f_y + 3, f_w, f_h), border_radius=14)
                    pygame.draw.rect(screen, (46, 175, 78), f_rect, border_radius=14)  # Green fighting fill
                    pygame.draw.rect(screen, (0, 0, 0), f_rect, width=3, border_radius=14)
                    screen.blit(f_surf, (f_x + (f_w - f_surf.get_width()) // 2, f_y + (f_h - f_surf.get_height()) // 2))

                    # 2. LEAVE button spawned directly ABOVE the fight button
                    l_px = max(20, min(36, ((round(btn_px * 0.88)) // 2) * 2))
                    l_outline = max(2, round(l_px * 0.07))
                    l_surf = get_outlined_text_surface("LEAVE", l_px, outline_px=l_outline)
                    l_w = l_surf.get_width() + 36
                    l_h = l_surf.get_height() + 14
                    l_x = (win_w - l_w) // 2
                    l_y = f_y - l_h - 14

                    fight_leave_button_rect = pygame.Rect(l_x, l_y, l_w, l_h)
                    pygame.draw.rect(screen, (0, 0, 0, 80), pygame.Rect(l_x + 3, l_y + 3, l_w, l_h), border_radius=12)
                    pygame.draw.rect(screen, (226, 44, 44), fight_leave_button_rect, border_radius=12)  # Red leave button
                    pygame.draw.rect(screen, (0, 0, 0), fight_leave_button_rect, width=3, border_radius=12)
                    screen.blit(l_surf, (l_x + (l_w - l_surf.get_width()) // 2, l_y + (l_h - l_surf.get_height()) // 2))

                elif near_belino and selected_character == "carmelito":
                    # When close to Belino: both Carmelito and Belino have a button that says 'FIGHT'
                    fight_leave_button_rect = pygame.Rect(-100, -100, 0, 0)
                    btn_px = max(20, min(38, ((round(win_h * 0.048)) // 2) * 2))
                    btn_outline = max(2, round(btn_px * 0.07))
                    tag_px = max(14, min(24, ((round(btn_px * 0.65)) // 2) * 2))

                    card_gap = max(24, round(win_w * 0.05))
                    btn_w = max(140, round(win_w * 0.16))
                    btn_h = max(48, round(win_h * 0.065))
                    total_w = btn_w * 2 + card_gap
                    start_x = (win_w - total_w) // 2
                    btn_y = win_h - btn_h - 32

                    # 1. Carmelito's FIGHT button (left)
                    c_x = start_x
                    c_col = (46, 175, 78) if fight_player_pressed else (226, 44, 44)
                    c_rect = pygame.Rect(c_x, btn_y, btn_w, btn_h)
                    carmelito_fight_button_rect = c_rect

                    # Carmelito tag above button
                    c_tag = get_nameplate_surface(CHICK_NAME, tag_px)
                    screen.blit(c_tag, (c_x + (btn_w - c_tag.get_width()) // 2, btn_y - c_tag.get_height() - 6))

                    pygame.draw.rect(screen, (0, 0, 0, 80), pygame.Rect(c_x + 3, btn_y + 3, btn_w, btn_h), border_radius=14)
                    pygame.draw.rect(screen, c_col, c_rect, border_radius=14)
                    pygame.draw.rect(screen, (0, 0, 0), c_rect, width=3, border_radius=14)

                    c_txt_surf = get_outlined_text_surface("FIGHT", btn_px, outline_px=btn_outline)
                    screen.blit(c_txt_surf, (c_x + (btn_w - c_txt_surf.get_width()) // 2, btn_y + (btn_h - c_txt_surf.get_height()) // 2))

                    # 2. Belino's FIGHT button (right)
                    b_x = start_x + btn_w + card_gap
                    b_col = (46, 175, 78) if fight_belino_pressed else (226, 44, 44)
                    b_rect = pygame.Rect(b_x, btn_y, btn_w, btn_h)
                    belino_fight_button_rect = b_rect

                    # Belino tag above button
                    b_tag = get_nameplate_surface(PANGDUN_NAME, tag_px)
                    screen.blit(b_tag, (b_x + (btn_w - b_tag.get_width()) // 2, btn_y - b_tag.get_height() - 6))

                    pygame.draw.rect(screen, (0, 0, 0, 80), pygame.Rect(b_x + 3, btn_y + 3, btn_w, btn_h), border_radius=14)
                    pygame.draw.rect(screen, b_col, b_rect, border_radius=14)
                    pygame.draw.rect(screen, (0, 0, 0), b_rect, width=3, border_radius=14)

                    b_txt_surf = get_outlined_text_surface("FIGHT", btn_px, outline_px=btn_outline)
                    screen.blit(b_txt_surf, (b_x + (btn_w - b_txt_surf.get_width()) // 2, btn_y + (btn_h - b_txt_surf.get_height()) // 2))
                else:
                    carmelito_fight_button_rect = pygame.Rect(-100, -100, 0, 0)
                    belino_fight_button_rect = pygame.Rect(-100, -100, 0, 0)
                    fight_leave_button_rect = pygame.Rect(-100, -100, 0, 0)

        # Giant black eyelid rectangle covering the world view while holding 'B'
        if is_online and blink_cover_progress > 0.001:
            cover_h = max(1, min(win_h, round(win_h * blink_cover_progress)))
            pygame.draw.rect(screen, (0, 0, 0), pygame.Rect(0, 0, win_w, cover_h))

        # --- 2. TOP-LEFT CORNER PICTURE: ONLY VISIBLE WHEN ONLINE (EQUIPPED CARMELITO) ---
        if is_online:
            pic_rect = pygame.Rect(16, 16, 180, 200)
            shadow_rect = pygame.Rect(18, 18, 180, 200)
            pygame.draw.rect(screen, (232, 236, 242), shadow_rect, border_radius=16)
            pygame.draw.rect(screen, (255, 255, 255), pic_rect, border_radius=16)
            pygame.draw.rect(screen, (215, 224, 232), pic_rect, width=2, border_radius=16)

            corner_y = 185 - round(jump_offset_y * 22)
            model_3d.render(
                surface=screen,
                screen_pos=(106, corner_y),
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
                character=selected_character,
                jump_amount=jump_amount,
            )

            # --- 2d. TOP-RIGHT PERSISTENT CHATBOX (shows everyone's messages) ---
            if is_online:
                cb_w = min(350, max(240, round(win_w * 0.30)))
                cb_h = min(200, max(140, round(win_h * 0.26)))
                cb_x = win_w - cb_w - 16
                cb_y = 16
                chat_log_rect = pygame.Rect(cb_x, cb_y, cb_w, cb_h)

                cb_surf = pygame.Surface((cb_w, cb_h), pygame.SRCALPHA)
                pygame.draw.rect(cb_surf, (255, 255, 255, 212), cb_surf.get_rect(), border_radius=14)
                pygame.draw.rect(cb_surf, (195, 210, 224, 235), cb_surf.get_rect(), width=2, border_radius=14)

                # Header strip
                header_h = 28
                pygame.draw.rect(cb_surf, (238, 245, 252, 230), pygame.Rect(2, 2, cb_w - 4, header_h), border_top_left_radius=12, border_top_right_radius=12)
                pygame.draw.line(cb_surf, (215, 224, 234), (4, header_h + 1), (cb_w - 4, header_h + 1), 1)
                hdr_font = get_chinese_font(14)
                hdr_surf = hdr_font.render("聊天 Chat (Enter发言)", True, (65, 85, 110))
                cb_surf.blit(hdr_surf, (12, (header_h - hdr_surf.get_height()) // 2 + 2))

                msg_font = get_chinese_font(15)
                body_top = header_h + 6
                body_bottom = cb_h - 8
                inner_w = cb_w - 22

                if not chat_history:
                    empty_surf = msg_font.render("暂无消息，按 Enter 打字聊天~", True, (140, 152, 165))
                    cb_surf.blit(empty_surf, (11, body_top + 6))
                else:
                    # Build wrapped lines for recent messages
                    rendered_rows: list[tuple[str, str, tuple[int, int, int]]] = []
                    for entry in chat_history[-16:]:
                        s_lbl = entry["sender"]
                        prefix = f"{s_lbl}: "
                        prefix_w = msg_font.size(prefix)[0]
                        name_col = (210, 75, 115) if entry.get("is_self") else (38, 112, 195)
                        first_max_w = max(60, inner_w - prefix_w)
                        first_lines = wrap_text_lines(entry["text"], msg_font, first_max_w)
                        if first_lines:
                            rendered_rows.append((prefix, first_lines[0], name_col))
                            rem_text = "".join(first_lines[1:])
                            if rem_text:
                                for cont_line in wrap_text_lines(rem_text, msg_font, inner_w):
                                    rendered_rows.append(("", cont_line, name_col))

                    line_h = msg_font.get_linesize() + 2
                    max_lines = max(1, (body_bottom - body_top) // line_h)
                    visible_rows = rendered_rows[-max_lines:]
                    cur_y = body_top
                    for pfx, body_txt, n_col in visible_rows:
                        x_off = 11
                        if pfx:
                            p_surf = msg_font.render(pfx, True, n_col)
                            cb_surf.blit(p_surf, (x_off, cur_y))
                            x_off += p_surf.get_width()
                        if body_txt:
                            b_surf = msg_font.render(body_txt, True, (30, 38, 48))
                            cb_surf.blit(b_surf, (x_off, cur_y))
                        cur_y += line_h

                screen.blit(cb_surf, (cb_x, cb_y))
            else:
                chat_log_rect = pygame.Rect(-100, -100, 0, 0)

            # Typing input box at bottom center of screen (opened with Return/Enter)
            candidate_click_rects.clear()
            if is_typing_chat:
                box_w = min(640, win_w - 40)
                box_h = 46
                box_x = (win_w - box_w) // 2
                box_y = win_h - box_h - 24

                # Box background & outline
                box_rect = pygame.Rect(box_x, box_y, box_w, box_h)
                if hasattr(pygame.key, "set_text_input_rect"):
                    pygame.key.set_text_input_rect(box_rect)

                s_rect = pygame.Rect(box_x + 2, box_y + 2, box_w, box_h)
                pygame.draw.rect(screen, (0, 0, 0, 50), s_rect, border_radius=12)
                pygame.draw.rect(screen, (255, 255, 255, 245), box_rect, border_radius=12)
                pygame.draw.rect(screen, (70, 130, 210), box_rect, width=2, border_radius=12)

                # Right-side [拼音] / [En] toggle button (Tab key or click)
                tog_w = 88
                tog_h = 30
                tog_x = box_x + box_w - tog_w - 8
                tog_y = box_y + (box_h - tog_h) // 2
                pinyin_toggle_rect = pygame.Rect(tog_x, tog_y, tog_w, tog_h)
                tog_bg = (54, 145, 235) if builtin_pinyin_mode else (232, 238, 245)
                tog_fg = (255, 255, 255) if builtin_pinyin_mode else (70, 85, 105)
                pygame.draw.rect(screen, tog_bg, pinyin_toggle_rect, border_radius=8)
                tog_font = get_chinese_font(14)
                tog_label = "拼音 Tab" if builtin_pinyin_mode else "En/Tab"
                tog_surf = tog_font.render(tog_label, True, tog_fg)
                screen.blit(tog_surf, (tog_x + (tog_w - tog_surf.get_width()) // 2, tog_y + (tog_h - tog_surf.get_height()) // 2))

                # Text content + live IME composition or built-in Pinyin preedit
                cursor_visible = (int(anim_time * 2.5) % 2) == 0
                font_chat = get_chinese_font(20)
                active_preedit = pinyin_buffer if (builtin_pinyin_mode and pinyin_buffer) else ime_comp_text
                text_area_max_w = tog_x - (box_x + 14) - 10

                if not chat_input_text and not active_preedit:
                    hint = "输入拼音或中文... (Enter发送, Tab切换拼音)" if builtin_pinyin_mode else "说点什么... (Enter发送, Tab可切内置拼音)"
                    prompt_surf = font_chat.render(hint, True, (155, 165, 175))
                    screen.blit(prompt_surf, (box_x + 14, box_y + (box_h - prompt_surf.get_height()) // 2))
                else:
                    # Render committed text + highlighted preedit + cursor
                    draw_x = box_x + 14
                    text_y = box_y + (box_h - font_chat.get_height()) // 2
                    committed_surf = font_chat.render(chat_input_text, True, (25, 30, 40))
                    # Scroll left if committed text exceeds visible width
                    total_w = committed_surf.get_width() + (font_chat.size(active_preedit)[0] if active_preedit else 0) + 8
                    if total_w > text_area_max_w:
                        draw_x -= (total_w - text_area_max_w)

                    clip_prev = screen.get_clip()
                    screen.set_clip(pygame.Rect(box_x + 10, box_y + 2, text_area_max_w + 4, box_h - 4))
                    screen.blit(committed_surf, (draw_x, text_y))
                    cur_x = draw_x + committed_surf.get_width()
                    if active_preedit:
                        comp_surf = font_chat.render(active_preedit, True, (35, 115, 220))
                        screen.blit(comp_surf, (cur_x, text_y))
                        pygame.draw.line(screen, (35, 115, 220), (cur_x, text_y + comp_surf.get_height() - 1), (cur_x + comp_surf.get_width(), text_y + comp_surf.get_height() - 1), 2)
                        cur_x += comp_surf.get_width()
                    if cursor_visible:
                        pygame.draw.line(screen, (25, 30, 40), (cur_x + 1, text_y + 2), (cur_x + 1, text_y + font_chat.get_height() - 2), 2)
                    screen.set_clip(clip_prev)

                # Built-in Pinyin candidate bar directly above typing box
                if builtin_pinyin_mode and pinyin_buffer:
                    cands = lookup_pinyin(pinyin_buffer)
                    page_cands = cands[pinyin_page * 5 : (pinyin_page + 1) * 5]
                    cand_font = get_chinese_font(18)
                    bar_h = 38
                    bar_y = box_y - bar_h - 8

                    # Build candidate items
                    items_surfs: list[tuple[str, pygame.Surface]] = []
                    for idx, ch_str in enumerate(page_cands):
                        lbl = f"{idx + 1}.{ch_str}"
                        items_surfs.append((ch_str, cand_font.render(lbl, True, (30, 40, 55))))

                    py_badge = cand_font.render(f"拼音: {pinyin_buffer}", True, (45, 115, 210))
                    page_hint_txt = f"  (-/= {pinyin_page + 1}/{(len(cands) + 4) // 5})" if len(cands) > 5 else ""
                    page_surf = get_chinese_font(14).render(page_hint_txt, True, (120, 132, 145)) if page_hint_txt else None
                    no_match_surf = cand_font.render("(空格/Enter上屏)", True, (140, 150, 165)) if not items_surfs else None

                    content_w = py_badge.get_width() + 18 + sum(sf.get_width() + 16 for _, sf in items_surfs)
                    if no_match_surf:
                        content_w += no_match_surf.get_width() + 12
                    if page_surf:
                        content_w += page_surf.get_width() + 6
                    bar_w = max(220, min(box_w, content_w + 20))
                    bar_x = box_x

                    bar_rect = pygame.Rect(bar_x, bar_y, bar_w, bar_h)
                    pygame.draw.rect(screen, (255, 255, 255, 248), bar_rect, border_radius=10)
                    pygame.draw.rect(screen, (95, 150, 225), bar_rect, width=2, border_radius=10)

                    cx_bar = bar_x + 12
                    screen.blit(py_badge, (cx_bar, bar_y + (bar_h - py_badge.get_height()) // 2))
                    cx_bar += py_badge.get_width() + 14
                    if no_match_surf:
                        screen.blit(no_match_surf, (cx_bar, bar_y + (bar_h - no_match_surf.get_height()) // 2))
                    else:
                        for idx, (ch_str, sf) in enumerate(items_surfs):
                            pill_w = sf.get_width() + 10
                            pill_rect = pygame.Rect(cx_bar - 4, bar_y + 5, pill_w, bar_h - 10)
                            if idx == 0:
                                pygame.draw.rect(screen, (226, 240, 255), pill_rect, border_radius=6)
                            screen.blit(sf, (cx_bar + 1, bar_y + (bar_h - sf.get_height()) // 2))
                            candidate_click_rects.append((pill_rect, ch_str))
                            cx_bar += pill_w + 6
                        if page_surf:
                            screen.blit(page_surf, (cx_bar, bar_y + (bar_h - page_surf.get_height()) // 2))
            else:
                pinyin_toggle_rect = pygame.Rect(-100, -100, 0, 0)

        # --- 3. TITLE SCREEN UI OVERLAYS (ONLY VISIBLE WHEN OFFLINE, DISAPPEARS ON JOIN) ---
        if not is_online and not has_entered_game:
            # 3a. Game title at top center: white text with black outline
            title_px = max(32, min(76, ((round(win_h * 0.075)) // 2) * 2))
            title_outline_px = max(2, round(title_px * 0.065))
            title_surf = get_outlined_text_surface(WINDOW_TITLE, title_px, outline_px=title_outline_px)
            title_x = (win_w - title_surf.get_width()) // 2
            title_y = max(12, round(win_h * 0.025))
            screen.blit(title_surf, (title_x, title_y))

            if menu_state == "title":
                # Initial PLAY button: white text with black outline below title
                play_px = max(24, min(48, ((round(title_px * 0.54)) // 2) * 2))
                play_outline_px = max(2, round(play_px * 0.07))
                play_surf = get_outlined_text_surface("PLAY", play_px, outline_px=play_outline_px)
                play_x = (win_w - play_surf.get_width()) // 2
                play_gap = max(24, round(win_h * 0.05))
                play_y = title_y + title_surf.get_height() + play_gap

                play_button_rect = pygame.Rect(
                    play_x - 12,
                    play_y - 6,
                    play_surf.get_width() + 24,
                    play_surf.get_height() + 12,
                )
                use_button_rect = pygame.Rect(-100, -100, 0, 0)
                screen.blit(play_surf, (play_x, play_y))

            elif menu_state in ("character_select", "character_used"):
                # Single character card in the center with a Right Arrow button to switch chicks!
                play_button_rect = pygame.Rect(-100, -100, 0, 0)

                card_w = min(170, round(win_h * 0.22))
                card_h = min(186, round(win_h * 0.24))
                cx = (win_w - card_w) // 2
                card_y = title_y + title_surf.get_height() + max(10, round(win_h * 0.018))

                char_id, char_name = available_characters[carousel_index]

                spin_yaw = anim_time * 1.6
                name_px = max(20, min(36, ((round(title_px * 0.48)) // 2) * 2))
                name_outline_px = max(2, round(name_px * 0.07))
                use_px = max(18, min(32, ((round(title_px * 0.42)) // 2) * 2))
                use_outline_px = max(2, round(use_px * 0.07))

                # Draw picture card centered in the game
                c_shadow = pygame.Rect(cx + 4, card_y + 4, card_w, card_h)
                c_rect = pygame.Rect(cx, card_y, card_w, card_h)
                pygame.draw.rect(screen, (190, 205, 220), c_shadow, border_radius=16)
                pygame.draw.rect(screen, (255, 255, 255), c_rect, border_radius=16)
                pygame.draw.rect(screen, (215, 225, 235), c_rect, width=2, border_radius=16)

                # Render 3D chick spinning inside card
                model_3d.render(
                    surface=screen,
                    screen_pos=(cx + card_w // 2, card_y + card_h - 16),
                    scale=round(card_h * 0.44),
                    rot_y=spin_yaw,
                    rot_x=0.08,
                    head_yaw=0.0,
                    head_pitch=0.0,
                    mouth_open=False,
                    run_cycle=0.0,
                    is_running=False,
                    run_weight=0.0,
                    is_walking=False,
                    walk_weight=0.0,
                    blink=0.0,
                    character=char_id,
                )

                # Right Arrow button on the right of the character card
                arrow_btn_size = max(42, min(56, round(card_h * 0.32)))
                arrow_r_x = cx + card_w + max(14, round(win_w * 0.02))
                arrow_r_y = card_y + (card_h - arrow_btn_size) // 2
                arrow_right_rect = pygame.Rect(arrow_r_x, arrow_r_y, arrow_btn_size, arrow_btn_size)

                # Left Arrow button on the left of the character card
                arrow_l_x = cx - max(14, round(win_w * 0.02)) - arrow_btn_size
                arrow_l_y = arrow_r_y
                arrow_left_rect = pygame.Rect(arrow_l_x, arrow_l_y, arrow_btn_size, arrow_btn_size)

                # Draw Right Arrow button (circular button with crisp right-pointing triangle)
                pygame.draw.circle(screen, (190, 205, 220), (arrow_r_x + arrow_btn_size // 2 + 2, arrow_r_y + arrow_btn_size // 2 + 2), arrow_btn_size // 2)
                pygame.draw.circle(screen, (255, 255, 255), (arrow_r_x + arrow_btn_size // 2, arrow_r_y + arrow_btn_size // 2), arrow_btn_size // 2)
                pygame.draw.circle(screen, (70, 90, 115), (arrow_r_x + arrow_btn_size // 2, arrow_r_y + arrow_btn_size // 2), arrow_btn_size // 2, 2)
                # Right arrow triangle:
                r_tri_tip = (arrow_r_x + round(arrow_btn_size * 0.68), arrow_r_y + arrow_btn_size // 2)
                r_tri_top = (arrow_r_x + round(arrow_btn_size * 0.36), arrow_r_y + round(arrow_btn_size * 0.28))
                r_tri_bot = (arrow_r_x + round(arrow_btn_size * 0.36), arrow_r_y + round(arrow_btn_size * 0.72))
                pygame.draw.polygon(screen, (70, 90, 115), [r_tri_tip, r_tri_top, r_tri_bot])

                # Draw Left Arrow button
                pygame.draw.circle(screen, (190, 205, 220), (arrow_l_x + arrow_btn_size // 2 + 2, arrow_l_y + arrow_btn_size // 2 + 2), arrow_btn_size // 2)
                pygame.draw.circle(screen, (255, 255, 255), (arrow_l_x + arrow_btn_size // 2, arrow_l_y + arrow_btn_size // 2), arrow_btn_size // 2)
                pygame.draw.circle(screen, (70, 90, 115), (arrow_l_x + arrow_btn_size // 2, arrow_l_y + arrow_btn_size // 2), arrow_btn_size // 2, 2)
                # Left arrow triangle:
                l_tri_tip = (arrow_l_x + round(arrow_btn_size * 0.32), arrow_l_y + arrow_btn_size // 2)
                l_tri_top = (arrow_l_x + round(arrow_btn_size * 0.64), arrow_l_y + round(arrow_btn_size * 0.28))
                l_tri_bot = (arrow_l_x + round(arrow_btn_size * 0.64), arrow_l_y + round(arrow_btn_size * 0.72))
                pygame.draw.polygon(screen, (70, 90, 115), [l_tri_tip, l_tri_top, l_tri_bot])

                # Character name below picture (updates dynamically when arrow is clicked!)
                n_surf = get_outlined_text_surface(char_name, name_px, outline_px=name_outline_px)
                nx = cx + (card_w - n_surf.get_width()) // 2
                ny = card_y + card_h + max(8, round(win_h * 0.014))
                screen.blit(n_surf, (nx, ny))

                # USE button below name: green if equipped, red if unequipped
                is_equipped = (has_selected_character and selected_character == char_id)
                u_fill = (68, 204, 88) if is_equipped else (235, 52, 52)
                u_surf = get_outlined_text_surface(
                    "USE",
                    use_px,
                    outline_px=use_outline_px,
                    fill_color=u_fill,
                    outline_color=(0, 0, 0),
                )
                ux = cx + (card_w - u_surf.get_width()) // 2
                uy = ny + n_surf.get_height() + max(8, round(win_h * 0.014))
                use_button_rect = pygame.Rect(
                    ux - 14,
                    uy - 6,
                    u_surf.get_width() + 28,
                    u_surf.get_height() + 12,
                )
                screen.blit(u_surf, (ux, uy))

                bottom_use_y = uy + u_surf.get_height()

                # When a character is equipped, spawn the PLAY button centered below the cards
                if menu_state == "character_used":
                    play_px = max(24, min(44, ((round(title_px * 0.54)) // 2) * 2))
                    play_outline_px = max(2, round(play_px * 0.07))
                    play_surf = get_outlined_text_surface("PLAY", play_px, outline_px=play_outline_px)
                    play_x = (win_w - play_surf.get_width()) // 2
                    play_y = bottom_use_y + max(10, round(win_h * 0.018))
                    play_button_rect = pygame.Rect(
                        play_x - 14,
                        play_y - 6,
                        play_surf.get_width() + 28,
                        play_surf.get_height() + 12,
                    )
                    screen.blit(play_surf, (play_x, play_y))

        pygame.display.flip()

    net.stop()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
