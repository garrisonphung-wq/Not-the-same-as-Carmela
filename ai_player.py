import argparse
import asyncio
import json
import math
import random
import threading
import time
from urllib.parse import urlparse

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed
import farm_world

import server as game_server
from carmelito_ai_brain import CarmelitoBrain, PangdunBrain, CarmenBrain, XiaoliuziBrain
from gemini_brain import GeminiChickBrain

CHICK_NAME = "卡梅利多"


def is_local_server_url(server_url: str) -> tuple[bool, int]:
    parsed = urlparse(server_url)
    host = (parsed.hostname or "").lower()
    port = parsed.port or (443 if parsed.scheme == "wss" else 8765)
    return host in {"127.0.0.1", "localhost", "::1", "0.0.0.0"}, port


def wrap_angle(angle: float) -> float:
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


class AICodeCompanion:
    WORLD_LIMIT = 280000.0  # Full Colorado island scale!
    CLOUD_SPAWN_WX = 0.0
    CLOUD_SPAWN_WZ = 14.0
    CLOUD_SPAWN_Y = 2475.0
    CLOUD_PLATFORM_RADIUS = 22.0
    WALK_SPEED = 3.2
    RUN_SPEED = 6.8
    TURN_SPEED = 3.2

    def __init__(
        self,
        server_url: str = "ws://127.0.0.1:8765",
        name: str = "小胖墩 (AI)",
        auto_host: bool = True,
        character: str = "pangdun",
        chick_name: str = "小胖墩",
        ai_role: str = "climber",
        climb_target_name: str | None = "小胖墩 (AI)",
        allow_chat_reply: bool = True,
    ) -> None:
        self.server_url = server_url
        self.name = name
        self.auto_host = auto_host
        self.character = character
        self.chick_name = chick_name
        self.ai_role = ai_role
        self.climb_target_name = climb_target_name
        self.allow_chat_reply = allow_chat_reply
        self.riding_pid: int | None = None
        self.riding_prev_pos: tuple[float, float] | None = None
        self.climb_jump_cooldown = random.uniform(0.3, 1.1)
        self.climb_impulse = 8.5

        self.my_id: int | None = None
        self.my_color: list[int] = [120, 195, 255]
        self.other_players: dict[int, tuple[float, float]] = {}
        self.other_player_labels: dict[int, str] = {}

        # Autonomous 3D world position & posture (starts visible in the grass field)
        self.wx = 2.2
        self.wz = 4.5
        self.rot_y = math.pi * 0.85  # Initially facing somewhat toward center/player
        self.rot_z = 0.0             # Subtle ragdoll tilt wobble
        self.lay_pitch = 0.0         # Local lay-down pitch (0 = standing, ±pi/2 = laying flat on grass)
        self.ragdoll = 0.0           # 0..1 floppy ragdoll limbs & head
        self.knock_vx = 0.0
        self.knock_vz = 0.0
        self.launch_accel_timer = 0.0
        self.is_kick_launched = False
        self.kick_roll_dir = 1.0
        self.kick_lay_dir = -1.0
        self.kick_bounced = False
        self.side_lying_timer = 0.0
        self.headshot_phase = "none"  # "none" | "head_up" | "fall_back"
        self.headshot_timer = 0.0
        self.headshot_face_yaw = self.rot_y
        self.head_yaw = 0.0
        self.head_pitch = 0.0
        self.target_head_yaw = 0.0
        self.target_head_pitch = 0.0

        self.is_walking = False
        self.is_running = False
        self.mouth_open = False
        self.is_blinking = False

        # Martial arts punch & kick actions
        self.is_kicking = False
        self.kick_timer = 0.0
        self.kick_duration = 0.48
        self.kick_side = 1.0
        self.kick_amount = 0.0

        self.is_punching = False
        self.punch_timer = 0.0
        self.punch_duration = 0.38
        self.punch_side = 1.0
        self.punch_amount = 0.0

        # Jump action
        self.jump_offset_y = 0.0
        self.jump_velocity_y = 0.0
        self.jump_state = "idle"
        self.crouch_timer = 0.0
        self.crouch_duration = 0.14
        self.jump_amount = 0.0
        self.JUMP_IMPULSE = 8.5
        self.GRAVITY = 22.0

        # Tag hands reach (for playing tag / hide-and-seek tag)
        self.is_tagging = False
        self.tag_timer = 0.0
        self.tag_duration = 2.2
        self.tag_amount = 0.0

        self.action_cooldown = random.uniform(2.5, 5.5)

        # Rocket Chicken + new playful state flags
        self.arms_down_amount = 0.0
        self.on_fire = False
        self.airborne_timer = 0.0
        self.is_j_air_spinning = False
        self.rocket_charge_dur = 0.0
        self.rocket_impulse = 75.0
        self.is_rocket_charging = False
        self.is_lying_down = False
        self.lie_down_timer = 0.0
        self.is_manual_ragdoll = False
        self.manual_ragdoll_timer = 0.0
        self.is_buried_in_crater = False
        self.buried_timer = 0.0
        self._pending_craters: list[tuple[float, float, float]] = []

        # Independent AI decision state machine
        self.mode = "idle"
        self.mode_timer = 1.2
        self.dest_x = self.wx
        self.dest_z = self.wz
        self.head_timer = 1.0
        self.mouth_timer = 2.5
        self.blink_timer = random.uniform(2.0, 4.5)
        self.chat_timer = random.uniform(6.0, 14.0)
        self._pending_chats: list[tuple[float, str]] = []  # (send_time, chat_text)
        self.gemini = GeminiChickBrain(character=character, chick_name=chick_name)
        self._reply_lock: asyncio.Lock | None = None
        char_key = character.lower()
        if char_key in ("pangdun", "小胖墩", "belino", "coquenpate"):
            self.brain = PangdunBrain()
        elif char_key in ("carmen", "卡门"):
            self.brain = CarmenBrain()
        elif char_key in ("xiaoliuzi", "小六子", "coqsix", "克西斯"):
            self.brain = XiaoliuziBrain()
        else:
            self.brain = CarmelitoBrain()

        self._host_started = False

    def _start_embedded_server(self, port: int) -> None:
        if self._host_started:
            return
        self._host_started = True

        def server_runner() -> None:
            try:
                asyncio.run(game_server.run_server(host="0.0.0.0", port=port))
            except OSError:
                pass

        threading.Thread(target=server_runner, daemon=True).start()

    def _get_world_scale(self) -> float:
        cl = self.character.lower()
        if cl in ("carmen", "卡门"):
            return 1.65 * 0.82
        if cl in ("pangdun", "小胖墩", "belino", "coquenpate"):
            return 1.65 * 1.15
        if cl in ("xiaoliuzi", "小六子", "coqsix", "克西斯"):
            return 1.65 * 1.08
        return 1.65

    def start_rocket_chicken(self, mega_fire: bool | None = None) -> None:
        if self.jump_state != "idle" or self.is_buried_in_crater:
            return
        self.is_walking = False
        self.is_running = False
        self.is_lying_down = False
        self.is_manual_ragdoll = False
        self.is_tagging = False
        self.is_rocket_charging = True
        self.target_head_yaw = 0.0
        self.target_head_pitch = 0.88
        self.head_pitch = max(self.head_pitch, 0.35)
        self.jump_state = "crouching"
        self.crouch_timer = 0.0
        self.jump_amount = 0.0
        if mega_fire is None:
            mega_fire = (random.random() < 0.25)
        if mega_fire:
            self.rocket_charge_dur = random.uniform(2.0, 2.8)
            self.rocket_impulse = random.uniform(90.0, 145.0)   # ~8-13s airtime -> catches fire at 5s!
        else:
            self.rocket_charge_dur = random.uniform(1.4, 2.2)
            self.rocket_impulse = random.uniform(64.0, 95.0)    # ~5.8-8.6s airtime -> catches fire at 5s + crater dive!

    def _choose_next_action(self) -> None:
        if self.ai_role in ("still", "jump_only"):
            self.dest_x = self.wx
            self.dest_z = self.wz
            self.mode = "idle"
            self.mode_timer = random.uniform(1.6, 3.8)
            self.is_walking = False
            self.is_running = False
            return

        if self.is_buried_in_crater or self.is_rocket_charging or self.jump_state != "idle":
            self.mode_timer = 0.8
            return

        roll = random.random()
        if roll < 0.34:
            on_cloud_now = (
                self.jump_offset_y >= self.CLOUD_SPAWN_Y - 1.0
                and math.hypot(self.wx - self.CLOUD_SPAWN_WX, self.wz - self.CLOUD_SPAWN_WZ) <= self.CLOUD_PLATFORM_RADIUS
            )
            if on_cloud_now:
                cloud_peers = [
                    p for p in self.other_players.values()
                    if p.get("jump_y", 0.0) >= self.CLOUD_SPAWN_Y - 2.0
                    and math.hypot(p["wx"] - self.CLOUD_SPAWN_WX, p["wz"] - self.CLOUD_SPAWN_WZ) <= self.CLOUD_PLATFORM_RADIUS
                ]
                if cloud_peers and random.random() < 0.45:
                    _t = random.choice(cloud_peers)
                    ang = random.uniform(0.0, 2.0 * math.pi)
                    tx = _t["wx"] + math.cos(ang) * random.uniform(1.8, 4.5)
                    tz = _t["wz"] + math.sin(ang) * random.uniform(1.8, 4.5)
                    d_c = math.hypot(tx - self.CLOUD_SPAWN_WX, tz - self.CLOUD_SPAWN_WZ)
                    if d_c > self.CLOUD_PLATFORM_RADIUS - 2.5:
                        s = (self.CLOUD_PLATFORM_RADIUS - 2.5) / d_c
                        tx = self.CLOUD_SPAWN_WX + (tx - self.CLOUD_SPAWN_WX) * s
                        tz = self.CLOUD_SPAWN_WZ + (tz - self.CLOUD_SPAWN_WZ) * s
                    self.dest_x = tx
                    self.dest_z = tz
                elif random.random() < 0.14:
                    ang = random.uniform(0.0, 2.0 * math.pi)
                    self.dest_x = self.CLOUD_SPAWN_WX + math.cos(ang) * (self.CLOUD_PLATFORM_RADIUS + 4.0)
                    self.dest_z = self.CLOUD_SPAWN_WZ + math.sin(ang) * (self.CLOUD_PLATFORM_RADIUS + 4.0)
                else:
                    ang = random.uniform(0.0, 2.0 * math.pi)
                    rad = random.uniform(2.0, self.CLOUD_PLATFORM_RADIUS - 3.0)
                    self.dest_x = self.CLOUD_SPAWN_WX + math.cos(ang) * rad
                    self.dest_z = self.CLOUD_SPAWN_WZ + math.sin(ang) * rad
            else:
                ground_peers = [p for p in self.other_players.values() if p.get("jump_y", 0.0) < 8.0]
                if ground_peers and random.random() < 0.45:
                    _t = random.choice(ground_peers)
                    ang = random.uniform(0.0, 2.0 * math.pi)
                    self.dest_x = max(-24.0, min(24.0, _t["wx"] + math.cos(ang) * random.uniform(2.0, 5.5)))
                    self.dest_z = max(-24.0, min(24.0, _t["wz"] + math.sin(ang) * random.uniform(2.0, 5.5)))
                else:
                    ang = random.uniform(0.0, 2.0 * math.pi)
                    rad = random.uniform(3.0, 22.0)
                    self.dest_x = math.cos(ang) * rad
                    self.dest_z = math.sin(ang) * rad
            self.mode = "run" if random.random() < 0.45 else "walk"
            self.target_head_yaw = random.uniform(-0.25, 0.25)
            self.target_head_pitch = random.uniform(-0.08, 0.15)
            self.mode_timer = random.uniform(2.0, 4.8)
        elif roll < 0.50:
            # Idle & look around
            self.mode = "idle"
            self.is_walking = False
            self.is_running = False
            self.target_head_yaw = random.uniform(-0.7, 0.7)
            self.target_head_pitch = random.uniform(-0.25, 0.45)
            self.mode_timer = random.uniform(1.2, 2.6)
        elif roll < 0.62:
            # Normal playful jump
            self.mode = "idle"
            self.is_walking = False
            self.is_running = False
            self.jump_state = "crouching"
            self.crouch_timer = 0.0
            self.jump_amount = 0.0
            self.mode_timer = random.uniform(1.5, 2.8)
        elif roll < 0.78:
            # ROCKET CHICKEN! (look up, crouch + arms down, spin launch into sky, dive into crater!)
            self.mode = "rocket"
            self.start_rocket_chicken()
            self.mode_timer = 4.0
        elif roll < 0.87:
            # Punch, kick, or zombie tag arms
            self.mode = "idle"
            self.is_walking = False
            self.is_running = False
            sub = random.random()
            if sub < 0.35:
                self.is_punching = True
                self.punch_timer = 0.0
                self.punch_side = -self.punch_side
            elif sub < 0.70:
                self.is_kicking = True
                self.kick_timer = 0.0
                self.kick_side = -self.kick_side
            else:
                self.is_tagging = True
                self.tag_timer = 0.0
                self.tag_duration = random.uniform(1.8, 3.2)
            self.mode_timer = random.uniform(1.2, 2.5)
        elif roll < 0.94:
            # Lie down on the grass!
            self.mode = "lie_down"
            self.is_walking = False
            self.is_running = False
            self.is_lying_down = True
            self.lie_down_timer = random.uniform(2.5, 4.2)
            self.mode_timer = self.lie_down_timer + 0.4
        else:
            # Manual ragdoll mode!
            self.mode = "ragdoll"
            self.is_walking = False
            self.is_running = False
            self.is_manual_ragdoll = True
            self.manual_ragdoll_timer = random.uniform(2.0, 3.4)
            self.mode_timer = self.manual_ragdoll_timer + 0.4

    def apply_punch_hit(self, dir_x: float, dir_z: float, headshot: bool, punch_side: float = 1.0) -> None:
        if self.is_buried_in_crater:
            return
        self.is_rocket_charging = False
        self.arms_down_amount = 0.0
        dlen = math.hypot(dir_x, dir_z)
        nx = dir_x / dlen if dlen > 1e-4 else 0.0
        nz = dir_z / dlen if dlen > 1e-4 else 1.0
        if headshot:
            # 30% outcome: face attacker, tilt head up to sky, fall down backward facing attacker, lay on grass 1 sec!
            self.knock_vx = nx * 5.2
            self.knock_vz = nz * 5.2
            self.headshot_face_yaw = math.atan2(-nx, -nz)
            self.headshot_phase = "head_up"
            self.headshot_timer = 0.0
            self.kick_lay_dir = -1.0  # Fall backward onto back
            self.kick_roll_dir = 0.0
            self.is_kick_launched = False
            self.side_lying_timer = 0.0
            self.ragdoll = 0.0
            self.is_walking = False
            self.is_running = False
            self.is_kicking = False
            self.kick_timer = 0.0
            self.kick_amount = 0.0
            self.is_punching = False
            self.punch_timer = 0.0
            self.punch_amount = 0.0
            self.is_tagging = False
            self.tag_amount = 0.0
            self.jump_amount = 0.0
        else:
            # 70% outcome: just get pushed back horizontally
            self.knock_vx = nx * 8.2
            self.knock_vz = nz * 8.2

    def apply_kick_hit(self, dir_x: float, dir_z: float, launch: bool, roll_dir: float) -> None:
        if self.is_buried_in_crater:
            return
        self.is_rocket_charging = False
        self.arms_down_amount = 0.0
        dlen = math.hypot(dir_x, dir_z)
        nx = dir_x / dlen if dlen > 1e-4 else 0.0
        nz = dir_z / dlen if dlen > 1e-4 else 1.0
        if launch:
            # 25% outcome: pushed + accelerate up + ragdoll mode + land laying down on grass for 1 sec!
            self.knock_vx = nx * 11.5
            self.knock_vz = nz * 11.5
            self.is_kick_launched = True
            self.launch_accel_timer = 0.18
            self.jump_state = "airborne"
            self.jump_velocity_y = 0.6
            self.jump_offset_y = max(self.jump_offset_y, 0.08)
            self.kick_roll_dir = 1.0 if roll_dir >= 0.0 else -1.0
            # Fall onto back (-1) if hit from front, or onto belly (+1) if hit from behind
            fwd_dot = nx * math.sin(self.rot_y) + nz * math.cos(self.rot_y)
            self.kick_lay_dir = 1.0 if fwd_dot > 0.0 else -1.0
            self.ragdoll = 1.0
            self.kick_bounced = False
            self.side_lying_timer = 0.0
            self.is_kicking = False
            self.kick_timer = 0.0
            self.kick_amount = 0.0
            self.is_punching = False
            self.punch_timer = 0.0
            self.punch_amount = 0.0
            self.is_tagging = False
            self.tag_amount = 0.0
            self.jump_amount = 0.0
        else:
            # 75% outcome: just get pushed horizontally
            self.knock_vx = nx * 9.5
            self.knock_vz = nz * 9.5

    def step_ai(self, dt: float) -> None:
        # Apply horizontal knockback / push velocity
        if abs(self.knock_vx) > 0.01 or abs(self.knock_vz) > 0.01:
            self.wx += self.knock_vx * dt
            self.wz += self.knock_vz * dt
            drag = 1.1 if self.jump_state == "airborne" else 5.5
            decay = max(0.0, 1.0 - drag * dt)
            self.knock_vx *= decay
            self.knock_vz *= decay
            # Keep inside island boundary
            r_cur = math.hypot(self.wx, self.wz)
            if r_cur > self.WORLD_LIMIT:
                self.wx = self.wx / r_cur * self.WORLD_LIMIT
                self.wz = self.wz / r_cur * self.WORLD_LIMIT

        # Pause normal wandering while laying down on the grass for 1 sec in ragdoll mode
        if self.side_lying_timer > 0.0:
            self.side_lying_timer = max(0.0, self.side_lying_timer - dt)
            self.is_walking = False
            self.is_running = False
            self.lay_pitch = self.kick_lay_dir * (math.pi * 0.5)
            self.ragdoll = 1.0
        elif self.headshot_phase == "head_up":
            self.headshot_timer += dt
            self.is_walking = False
            self.is_running = False
            # Turn to face the attacker
            diff_y = wrap_angle(self.headshot_face_yaw - self.rot_y)
            turn_step = 16.0 * dt
            if abs(diff_y) <= turn_step:
                self.rot_y = self.headshot_face_yaw
            else:
                self.rot_y = wrap_angle(self.rot_y + math.copysign(turn_step, diff_y))
            # Tilt head straight UP (pi/2)
            self.target_head_yaw = 0.0
            self.head_yaw += (0.0 - self.head_yaw) * min(1.0, 14.0 * dt)
            self.head_pitch = min(math.pi * 0.5, self.head_pitch + 7.0 * dt)
            self.target_head_pitch = self.head_pitch
            if self.headshot_timer >= 0.28 and self.head_pitch >= math.pi * 0.46:
                self.headshot_phase = "fall_back"
                self.headshot_timer = 0.0
                self.rot_y = self.headshot_face_yaw
        elif self.headshot_phase == "fall_back":
            self.headshot_timer += dt
            self.is_walking = False
            self.is_running = False
            self.rot_y = self.headshot_face_yaw
            # Fall backward onto back (-pi/2) while keeping face toward sky
            fall_speed = math.radians(260.0 + 180.0 * min(1.0, self.headshot_timer * 2.5))
            self.lay_pitch = max(-math.pi * 0.5, self.lay_pitch - fall_speed * dt)
            progress = min(1.0, abs(self.lay_pitch) / (math.pi * 0.5))
            self.head_pitch = (math.pi * 0.5) * (1.0 - progress) + 0.12 * progress
            self.target_head_pitch = self.head_pitch
            if self.lay_pitch <= -math.pi * 0.5 + 1e-4:
                self.lay_pitch = -math.pi * 0.5
                self.rot_z = 0.0
                self.ragdoll = 1.0
                self.headshot_phase = "none"
                self.side_lying_timer = 1.0
        elif self.is_buried_in_crater:
            # Stuck upside-down 50% under the grass -> wiggle 10s then stand back up!
            self.is_walking = False
            self.is_running = False
            self.buried_timer += dt
            self.lay_pitch = -math.pi
            self.rot_z = math.sin(self.buried_timer * 24.0) * 0.06
            self.jump_offset_y = -0.58 * self._get_world_scale()
            self.ragdoll = 0.0
            if self.buried_timer >= 10.0:
                self.is_buried_in_crater = False
                self.buried_timer = 0.0
                self.lay_pitch = 0.0
                self.rot_z = 0.0
                self.jump_offset_y = 0.0
                self.target_head_pitch = 0.0
        elif self.is_lying_down:
            self.is_walking = False
            self.is_running = False
            self.lie_down_timer -= dt
            self.lay_pitch = max(-math.pi * 0.5, self.lay_pitch - math.radians(320.0) * dt)
            self.ragdoll = 0.0
            if self.lie_down_timer <= 0.0:
                self.is_lying_down = False
        elif self.is_manual_ragdoll:
            self.is_walking = False
            self.is_running = False
            self.manual_ragdoll_timer -= dt
            self.ragdoll = 1.0
            self.lay_pitch = max(-math.pi * 0.5, self.lay_pitch - math.radians(260.0) * dt)
            self.rot_z += (0.28 - self.rot_z) * min(1.0, 8.0 * dt)
            if self.manual_ragdoll_timer <= 0.0:
                self.is_manual_ragdoll = False
        elif not self.is_kick_launched and not self.is_j_air_spinning and (abs(self.lay_pitch) > 1e-3 or abs(self.rot_z) > 1e-3 or self.ragdoll > 1e-3):
            # Smoothly recover upright from ragdoll lay-down
            rec_step = math.radians(280.0) * dt
            if abs(self.lay_pitch) <= rec_step:
                self.lay_pitch = 0.0
            else:
                self.lay_pitch -= math.copysign(rec_step, self.lay_pitch)
            if abs(self.rot_z) <= rec_step:
                self.rot_z = 0.0
            else:
                self.rot_z -= math.copysign(rec_step, self.rot_z)
            self.ragdoll = max(0.0, self.ragdoll - 3.5 * dt)

        self.mode_timer -= dt
        self.head_timer -= dt
        self.mouth_timer -= dt
        self.blink_timer -= dt
        self.climb_jump_cooldown = max(0.0, self.climb_jump_cooldown - dt)

        ai_ragdoll_locked = (self.is_kick_launched or self.side_lying_timer > 0.0 or self.ragdoll > 0.05 or self.headshot_phase != "none" or self.is_buried_in_crater or self.is_lying_down or self.is_manual_ragdoll)
        if ai_ragdoll_locked:
            self.is_kicking = False
            self.kick_timer = 0.0
            self.kick_amount = 0.0
            self.is_punching = False
            self.punch_timer = 0.0
            self.punch_amount = 0.0
            self.is_tagging = False
            self.tag_amount = 0.0
            self.target_head_yaw = 0.0
            self.target_head_pitch = 0.0
            if self.jump_state == "crouching":
                self.jump_state = "idle"
                self.crouch_timer = 0.0
                self.jump_amount = 0.0
        elif self.mode_timer <= 0.0:
            self._choose_next_action()

        if self.blink_timer <= 0.0:
            if self.is_blinking:
                self.is_blinking = False
                self.blink_timer = random.uniform(0.16, 0.24) if random.random() < 0.18 else random.uniform(2.6, 5.0)
            else:
                self.is_blinking = True
                self.blink_timer = 0.16

        if self.mouth_timer <= 0.0:
            if self.mouth_open:
                self.mouth_open = False
                self.mouth_timer = random.uniform(2.2, 6.0)
            elif random.random() < 0.35:
                self.mouth_open = True
                self.mouth_timer = random.uniform(0.45, 1.2)
            else:
                self.mouth_timer = random.uniform(1.8, 4.0)

        # Find target still chick if this AI is a climber
        climb_tx, climb_tz, climb_ty = 0.0, 7.2, 0.0
        target_found = False
        if self.climb_target_name:
            for _pid, _info in self.other_players.items():
                if _info.get("name") == self.climb_target_name:
                    climb_tx = _info["wx"]
                    climb_tz = _info["wz"]
                    climb_ty = _info["jump_y"]
                    target_found = True
                    break

        if ai_ragdoll_locked or self.ai_role in ("still", "jump_only"):
            self.is_walking = False
            self.is_running = False
            if self.headshot_phase == "none":
                # Look toward nearby players (and look UP if a player is standing on the cloud!)
                best_info = None
                best_score = 1e9
                for _opid, _oinfo in self.other_players.items():
                    _d = math.hypot(_oinfo["wx"] - self.wx, _oinfo["wz"] - self.wz)
                    # Prioritize players on the cloud or closest nearby
                    _score = _d - (8.0 if _oinfo.get("jump_y", 0.0) >= 8.0 else 0.0)
                    if _d < 45.0 and _score < best_score:
                        best_score = _score
                        best_info = _oinfo
                if best_info is not None:
                    _dx = best_info["wx"] - self.wx
                    _dz = best_info["wz"] - self.wz
                    _dy = best_info.get("jump_y", 0.0) - self.jump_offset_y
                    _hd = max(0.5, math.hypot(_dx, _dz))
                    _desired_yaw = math.atan2(_dx, _dz)
                    _rel_yaw = wrap_angle(_desired_yaw - self.rot_y)
                    if abs(_rel_yaw) > 0.75:
                        _turn_step = 3.2 * dt
                        self.rot_y = wrap_angle(self.rot_y + math.copysign(min(abs(_rel_yaw), _turn_step), _rel_yaw))
                        _rel_yaw = wrap_angle(_desired_yaw - self.rot_y)
                    self.target_head_yaw = max(-0.85, min(0.85, _rel_yaw))
                    self.target_head_pitch = max(-0.55, min(0.98, math.atan2(_dy, _hd)))
                else:
                    self.target_head_yaw = 0.0
                    self.target_head_pitch = 0.0
            if (not ai_ragdoll_locked) and self.ai_role == "jump_only":
                self.action_cooldown -= dt
                if self.action_cooldown <= 0.0 and self.jump_state == "idle":
                    self.action_cooldown = random.uniform(2.2, 4.8)
                    self.climb_impulse = self.JUMP_IMPULSE
                    self.jump_state = "crouching"
                    self.crouch_timer = 0.0
                    self.jump_amount = 0.0
        elif self.ai_role == "free":
            # Free AI: walk or run around the island freely, jump, look at sky-cloud players, or rocket-launch!
            if self.is_rocket_charging or self.jump_state == "crouching":
                self.is_walking = False
                self.is_running = False
            elif self.mode in ("walk", "run"):
                dx_d = self.dest_x - self.wx
                dz_d = self.dest_z - self.wz
                dist_d = math.hypot(dx_d, dz_d)
                if dist_d > 0.45:
                    desired_yaw = math.atan2(dx_d, dz_d)
                    diff = wrap_angle(desired_yaw - self.rot_y)
                    max_turn = self.TURN_SPEED * 1.4 * dt
                    if abs(diff) <= max_turn:
                        self.rot_y = desired_yaw
                    else:
                        self.rot_y = wrap_angle(self.rot_y + math.copysign(max_turn, diff))
                    self.is_running = (self.mode == "run" and dist_d > 1.8)
                    self.is_walking = not self.is_running
                    move_spd = self.RUN_SPEED if self.is_running else self.WALK_SPEED
                    step = min(dist_d, move_spd * dt)
                    self.wx += (dx_d / dist_d) * step
                    self.wz += (dz_d / dist_d) * step
                    # Keep within island
                    r_w = math.hypot(self.wx, self.wz)
                    if r_w > self.WORLD_LIMIT:
                        self.wx = self.wx / r_w * self.WORLD_LIMIT
                        self.wz = self.wz / r_w * self.WORLD_LIMIT
                else:
                    self.is_walking = False
                    self.is_running = False
                    self.mode = "idle"
                    self.mode_timer = min(self.mode_timer, 0.8)
            else:
                self.is_walking = False
                self.is_running = False
                # While idle, occasionally look up at a player on the sky cloud!
                if not self.is_rocket_charging and self.jump_state == "idle":
                    for _opid, _oinfo in self.other_players.items():
                        if _oinfo.get("jump_y", 0.0) >= 8.0 and math.hypot(_oinfo["wx"] - self.wx, _oinfo["wz"] - self.wz) < 45.0:
                            _desired_yaw = math.atan2(_oinfo["wx"] - self.wx, _oinfo["wz"] - self.wz)
                            _rel_yaw = wrap_angle(_desired_yaw - self.rot_y)
                            self.target_head_yaw = max(-0.85, min(0.85, _rel_yaw))
                            self.target_head_pitch = 0.92
                            break
        else:
            # Climber AI: if already standing on top of a chick, perch smoothly; otherwise move toward the still chick & leap on!
            is_perched = (self.riding_pid is not None and self.jump_offset_y >= 0.85)
            if is_perched:
                self.is_walking = False
                self.is_running = False
                if self.headshot_phase == "none":
                    self.target_head_yaw = 0.0
                    self.target_head_pitch = 0.0
            else:
                dx_t = climb_tx - self.wx
                dz_t = climb_tz - self.wz
                dist_t = math.hypot(dx_t, dz_t)
                if dist_t > 0.05:
                    desired_yaw = math.atan2(dx_t, dz_t)
                    diff = wrap_angle(desired_yaw - self.rot_y)
                    max_turn = self.TURN_SPEED * 1.8 * dt
                    if abs(diff) <= max_turn:
                        self.rot_y = desired_yaw
                    else:
                        self.rot_y = wrap_angle(self.rot_y + math.copysign(max_turn, diff))

                if self.jump_state == "airborne":
                    # Steer smoothly inward over the target chick while jumping up onto it!
                    self.is_walking = False
                    self.is_running = False
                    if dist_t > 0.15:
                        air_speed = min(self.RUN_SPEED, max(2.2, dist_t * 3.8))
                        self.wx += (dx_t / dist_t) * air_speed * dt
                        self.wz += (dz_t / dist_t) * air_speed * dt
                elif self.jump_state == "crouching":
                    self.is_walking = False
                    self.is_running = False
                elif dist_t > 1.38:
                    # Run/walk up to the still chick
                    self.is_running = dist_t > 2.4
                    self.is_walking = not self.is_running
                    move_spd = self.RUN_SPEED if self.is_running else self.WALK_SPEED
                    step = min(dist_t - 1.15, move_spd * dt)
                    if step > 0.0:
                        self.wx += (dx_t / dist_t) * step
                        self.wz += (dz_t / dist_t) * step
                else:
                    # Close enough to jump onto the still chick (or stack on top of other chicks!)
                    self.is_walking = False
                    self.is_running = False
                    if self.climb_jump_cooldown <= 0.0:
                        # Jump slightly higher if other chicks are already stacked near the still chick
                        stack_height = climb_ty
                        for _pid, _info in self.other_players.items():
                            if math.hypot(_info["wx"] - climb_tx, _info["wz"] - climb_tz) < 1.55:
                                stack_height = max(stack_height, _info["jump_y"])
                        needed_h = max(1.6, stack_height + 1.55)
                        self.climb_impulse = math.sqrt(2.0 * self.GRAVITY * needed_h)
                        self.jump_state = "crouching"
                        self.crouch_timer = 0.0
                        self.jump_amount = 0.0
                        self.climb_jump_cooldown = random.uniform(0.35, 0.80)

        # --- CHICK-TO-CHICK COLLISION & DYNAMIC PUSHING FOR AI ---
        if self.riding_pid is not None and self.riding_pid in self.other_players and self.jump_state != "airborne":
            c_info = self.other_players[self.riding_pid]
            if self.riding_prev_pos is not None:
                self.wx += c_info["wx"] - self.riding_prev_pos[0]
                self.wz += c_info["wz"] - self.riding_prev_pos[1]
            self.riding_prev_pos = (c_info["wx"], c_info["wz"])

        ai_landing_support_y = 0.0
        found_ai_carrier: int | None = None
        MIN_CHICK_DIST = 1.16
        my_moving = self.is_running or self.is_walking
        my_weight = 1.0 + (1.2 if self.is_running else (0.6 if my_moving else 0.0))

        for op_id, op_info in list(self.other_players.items()):
            ox = op_info["wx"]
            oz = op_info["wz"]
            o_jump_y = op_info["jump_y"]
            o_running = op_info["running"]
            o_walking = op_info["walking"]
            o_moving = o_running or o_walking

            dx = self.wx - ox
            dz = self.wz - oz
            horiz_d = math.hypot(dx, dz)

            other_top_y = o_jump_y + 1.15
            is_riding_this = (self.riding_pid == op_id)
            ride_range = MIN_CHICK_DIST * 1.25 if is_riding_this else MIN_CHICK_DIST * 0.95
            if horiz_d < ride_range:
                if (is_riding_this and self.jump_state != "airborne") or (self.jump_offset_y >= other_top_y - 0.30):
                    if other_top_y > ai_landing_support_y:
                        ai_landing_support_y = other_top_y
                        found_ai_carrier = op_id
                    continue

            # Skip horizontal push while leaping over another chick to climb on top!
            if self.jump_state == "airborne" and self.jump_offset_y > o_jump_y + 0.32:
                continue

            if horiz_d < MIN_CHICK_DIST and abs(self.jump_offset_y - o_jump_y) < 1.10:
                overlap = MIN_CHICK_DIST - horiz_d
                nx = dx / max(1e-4, horiz_d)
                nz = dz / max(1e-4, horiz_d)

                other_weight = 1.0 + (1.2 if o_running else (0.6 if o_moving else 0.0))

                if my_moving and not o_moving:
                    ratio_me = 0.20
                    ratio_other = 0.80
                elif o_moving and not my_moving:
                    ratio_me = 0.80
                    ratio_other = 0.20
                elif my_moving and o_moving:
                    tot_w = my_weight + other_weight
                    ratio_me = other_weight / tot_w
                    ratio_other = my_weight / tot_w
                else:
                    ratio_me = 0.50
                    ratio_other = 0.50

                if self.ai_role != "still" and not self.is_buried_in_crater:
                    self.wx += nx * (overlap * ratio_me)
                    self.wz += nz * (overlap * ratio_me)

        # Farm buildings & props collision + hay/roof support for AI chick
        if not self.is_buried_in_crater:
            self.wx, self.wz, prop_support_y = farm_world.resolve_world_props_collision(
                self.wx, self.wz, self.jump_offset_y, chick_radius=0.48
            )
            if prop_support_y > ai_landing_support_y:
                ai_landing_support_y = prop_support_y

        # Cloud platform support (keeps AI chick standing/walking cleanly on the 2475m cloud)
        if (
            self.jump_offset_y >= self.CLOUD_SPAWN_Y - 0.85
            and math.hypot(self.wx - self.CLOUD_SPAWN_WX, self.wz - self.CLOUD_SPAWN_WZ) <= self.CLOUD_PLATFORM_RADIUS
        ):
            if self.CLOUD_SPAWN_Y > ai_landing_support_y:
                ai_landing_support_y = self.CLOUD_SPAWN_Y

        if found_ai_carrier is not None and found_ai_carrier in self.other_players:
            c_info = self.other_players[found_ai_carrier]
            self.riding_pid = found_ai_carrier
            self.riding_prev_pos = (c_info["wx"], c_info["wz"])
        else:
            self.riding_pid = None
            self.riding_prev_pos = None

        # Smooth natural neck interpolation (skip overwrite during headshot sequence)
        if self.headshot_phase == "none":
            head_alpha = 1.0 - math.exp(-6.0 * dt)
            self.head_yaw += (self.target_head_yaw - self.head_yaw) * head_alpha
            self.head_pitch += (self.target_head_pitch - self.head_pitch) * head_alpha

        # Update kick animation
        if self.is_kicking:
            self.kick_timer += dt
            if self.kick_timer >= self.kick_duration:
                self.is_kicking = False
                self.kick_timer = 0.0
                self.kick_amount = 0.0
            else:
                kp = self.kick_timer / self.kick_duration
                self.kick_amount = math.sin((kp / 0.38) * (math.pi / 2)) if kp < 0.38 else math.cos(((kp - 0.38) / 0.62) * (math.pi / 2))

        # Update punch animation
        if self.is_punching:
            self.punch_timer += dt
            if self.punch_timer >= self.punch_duration:
                self.is_punching = False
                self.punch_timer = 0.0
                self.punch_amount = 0.0
            else:
                pp = self.punch_timer / self.punch_duration
                self.punch_amount = math.sin((pp / 0.32) * (math.pi / 2)) if pp < 0.32 else math.cos(((pp - 0.32) / 0.68) * (math.pi / 2))

        # Tag hands reach animation
        if self.is_tagging:
            self.tag_timer += dt
            if self.tag_timer >= self.tag_duration:
                self.is_tagging = False
                self.tag_timer = 0.0
                self.tag_amount = 0.0
            else:
                self.tag_amount = min(1.0, self.tag_amount + 12.0 * dt)
        else:
            self.tag_amount = max(0.0, self.tag_amount - 10.0 * dt)

        # Jump & Rocket Chicken physics
        if self.jump_state == "crouching":
            if ai_landing_support_y > 0.0:
                self.jump_offset_y = ai_landing_support_y
            self.crouch_timer += dt
            target_crouch_dur = self.rocket_charge_dur if self.is_rocket_charging else self.crouch_duration
            cp = min(1.0, self.crouch_timer / max(0.05, target_crouch_dur))
            self.jump_amount = math.sin(cp * (math.pi / 2))
            if self.is_rocket_charging:
                self.target_head_pitch = 0.88
                if self.head_pitch > math.radians(15.0):
                    self.arms_down_amount = min(1.0, self.arms_down_amount + 8.0 * dt)
            if self.crouch_timer >= target_crouch_dur:
                self.jump_state = "airborne"
                if self.is_rocket_charging:
                    self.jump_velocity_y = self.rocket_impulse
                    self.is_j_air_spinning = True
                    self.is_rocket_charging = False
                elif self.ai_role == "climber":
                    self.jump_velocity_y = self.climb_impulse
                    self.is_j_air_spinning = False
                else:
                    self.jump_velocity_y = self.JUMP_IMPULSE
                    self.is_j_air_spinning = False
                self.jump_offset_y = max(self.jump_offset_y, ai_landing_support_y) + 0.08
                self.jump_amount = 0.0
                self.arms_down_amount = 0.0
                self.airborne_timer = 0.0
                self.on_fire = False
                self.riding_pid = None
                self.riding_prev_pos = None
        elif self.jump_state == "airborne":
            if self.launch_accel_timer > 0.0:
                self.jump_velocity_y += 74.0 * dt
                self.launch_accel_timer = max(0.0, self.launch_accel_timer - dt)
            self.jump_offset_y += self.jump_velocity_y * dt
            self.jump_velocity_y -= self.GRAVITY * dt
            self.jump_amount = 0.0
            self.arms_down_amount = 0.0
            if not self.is_kick_launched:
                self.airborne_timer += dt
                if self.is_j_air_spinning:
                    self.rot_y = (self.rot_y + dt * 14.0) % (2.0 * math.pi)
                    if self.jump_velocity_y < 0.0 and self.lay_pitch > -math.pi:
                        fall_dist = max(0.05, self.jump_offset_y - max(0.0, ai_landing_support_y))
                        t_rem = max(0.10, (self.jump_velocity_y + math.sqrt(self.jump_velocity_y * self.jump_velocity_y + 2.0 * self.GRAVITY * fall_dist)) / self.GRAVITY)
                        turn_rate = max(math.radians(150.0), min(math.radians(720.0), abs(-math.pi - self.lay_pitch) / t_rem))
                        self.lay_pitch = max(-math.pi, self.lay_pitch - turn_rate * dt)
                if self.is_j_air_spinning and self.airborne_timer >= 5.0:
                    self.on_fire = True
            if self.is_kick_launched:
                # Ragdoll mode: tip into loose sprawl toward ±90 deg to land laying flat down on grass (NOT a backflip!)
                self.ragdoll = 1.0
                target_lay = self.kick_lay_dir * (math.pi * 0.5)
                lay_step = math.radians(165.0) * dt * self.kick_lay_dir
                if self.kick_lay_dir > 0:
                    self.lay_pitch = min(target_lay, self.lay_pitch + lay_step)
                else:
                    self.lay_pitch = max(target_lay, self.lay_pitch + lay_step)
                target_wobble = self.kick_roll_dir * math.radians(24.0)
                self.rot_z += (target_wobble - self.rot_z) * min(1.0, 7.0 * dt)
            cur_floor = max(0.0, ai_landing_support_y)
            if self.jump_velocity_y <= 0.0 and self.jump_offset_y <= cur_floor:
                if self.is_kick_launched and not self.kick_bounced and self.jump_velocity_y < -4.2:
                    self.jump_offset_y = cur_floor + 0.01
                    self.jump_velocity_y = min(2.1, -self.jump_velocity_y * 0.22)
                    self.kick_bounced = True
                else:
                    landed_upside_down = (not self.is_kick_launched) and self.is_j_air_spinning and (abs(self.lay_pitch) >= math.pi * 0.72) and (cur_floor <= 0.05)
                    self.jump_velocity_y = 0.0
                    self.jump_state = "idle"
                    self.jump_amount = 0.0
                    self.is_j_air_spinning = False
                    self.on_fire = False
                    self.airborne_timer = 0.0
                    if landed_upside_down:
                        self.jump_offset_y = -0.58 * self._get_world_scale()
                        self.lay_pitch = -math.pi
                        self.rot_z = 0.0
                        self.ragdoll = 0.0
                        self.is_buried_in_crater = True
                        self.buried_timer = 0.0
                        self._pending_craters.append((self.wx, self.wz, 1.38))
                    else:
                        self.jump_offset_y = cur_floor
                    if self.is_kick_launched:
                        self.is_kick_launched = False
                        self.lay_pitch = self.kick_lay_dir * (math.pi * 0.5)
                        self.rot_z = self.kick_roll_dir * math.radians(22.0)
                        self.ragdoll = 1.0
                        self.side_lying_timer = 1.0
        else:
            self.arms_down_amount = max(0.0, self.arms_down_amount - 10.0 * dt)
            cur_floor = max(0.0, ai_landing_support_y)
            if not self.is_buried_in_crater:
                if self.jump_offset_y > 0.0:
                    if cur_floor > 0.0:
                        self.jump_offset_y = cur_floor
                    elif self.jump_offset_y > 0.12:
                        self.jump_state = "airborne"
                        self.jump_velocity_y = 0.0
                    else:
                        self.jump_offset_y = 0.0
            self.jump_amount = 0.0


    def _build_world_context(self, speaker_id: int, speaker_name: str) -> str:
        cloud_watchers = [
            f"{info.get('name', '玩家')}(在云朵上!)"
            for info in self.other_players.values()
            if info.get("jump_y", 0.0) >= 8.0
        ]
        cloud_note = ("；看到" + "、".join(cloud_watchers)) if cloud_watchers else ""
        place_word = "高空云朵上" if self.jump_offset_y >= 8.0 else "草地上"
        state_str = f"摔倒躺在{place_word}(ragdoll)" if (self.is_kick_launched or self.side_lying_timer > 0.0 or self.ragdoll > 0.05) else (
            f"在{place_word}跑" if self.is_running else (f"在{place_word}走" if self.is_walking else f"在{place_word}站着")
        )
        sp = self.other_players.get(speaker_id)
        if sp is not None:
            dist = math.hypot(sp["wx"] - self.wx, sp["wz"] - self.wz)
            dist_str = f"{speaker_name}距离你约{dist:.1f}米"
        else:
            dist_str = f"{speaker_name}在草地上"
        return f"你当前状态:{state_str}{cloud_note}；{dist_str}；当前共有{len(self.other_players) + 1}只小鸡在岛上。"

    def _apply_gemini_action(self, action: str, speaker_id: int) -> None:
        # AI cannot move except jump (and cannot jump while ragdolled)
        if self.is_kick_launched or self.side_lying_timer > 0.0 or self.ragdoll > 0.05 or self.headshot_phase != "none":
            return
        if self.is_buried_in_crater or self.is_kick_launched or self.side_lying_timer > 0.0 or self.ragdoll > 0.05:
            return
        if action == "rocket" and self.jump_state == "idle":
            self.start_rocket_chicken()
        elif action == "jump" and self.jump_state == "idle":
            self.jump_state = "crouching"
            self.crouch_timer = 0.0
            self.jump_amount = 0.0

    async def _handle_chat_with_gemini(self, sender_id: int, sender_name: str, chat_text: str) -> None:
        if self._reply_lock is None:
            self._reply_lock = asyncio.Lock()
        async with self._reply_lock:
            ctx = self._build_world_context(sender_id, sender_name)
            reply_text, action = await asyncio.to_thread(
                self.gemini.reply_to_player,
                sender_name,
                chat_text,
                ctx,
            )
            reply_text = reply_text.strip()[:260]
            if reply_text:
                self._pending_chats.append((time.time(), reply_text))
                self.mouth_open = True
                self.mouth_timer = min(2.0, max(0.65, len(reply_text) * 0.045))
            self._apply_gemini_action(action, sender_id)

    async def run(self) -> None:
        print(f"🤖 {self.name} ({self.chick_name}) connecting to {self.server_url}...", flush=True)
        is_local, port = is_local_server_url(self.server_url)

        first_retry = True
        while True:
            try:
                async with connect(self.server_url, ping_interval=15, ping_timeout=15) as ws:
                    print(f"🤖 {self.name} ({self.chick_name}) connected!", flush=True)
                    first_retry = True
                    send_task = asyncio.create_task(self._motion_loop(ws))
                    recv_task = asyncio.create_task(self._listen_loop(ws))
                    done, pending = await asyncio.wait(
                        {send_task, recv_task},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for t in pending:
                        t.cancel()
                    for t in done:
                        if not t.cancelled():
                            exc = t.exception()
                            if exc and not isinstance(exc, ConnectionClosed):
                                print(f"🤖 Loop exception: {exc}", flush=True)
            except (ConnectionRefusedError, OSError):
                if is_local and self.auto_host and not self._host_started:
                    print("🤖 No server detected. Auto-starting local game server...", flush=True)
                    self._start_embedded_server(port)
                    await asyncio.sleep(0.3)
                    continue

                if first_retry:
                    print("🤖 Waiting for game server to start...", flush=True)
                    first_retry = False
                await asyncio.sleep(2.0)
            except Exception as e:
                print(f"🤖 Reconnecting after error: {e}", flush=True)
                await asyncio.sleep(2.0)

    def _update_observed_label(self, pid: int, pdata: dict) -> None:
        label = pdata.get("chick_name") or (CHICK_NAME if pdata.get("is_carmelito") else pdata.get("name"))
        if label:
            prev = self.other_player_labels.get(pid)
            self.other_player_labels[pid] = str(label)
            if prev != label:
                print(f"🤖 AI sees player {pid} labeled '{label}'", flush=True)

    async def _listen_loop(self, ws) -> None:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            mtype = msg.get("type")
            if mtype == "welcome":
                self.my_id = int(msg["id"])
                self.my_color = msg.get("color", self.my_color)
                players = msg.get("players", {})
                print(f"🤖 {self.name} joined as Player {self.my_id} ({CHICK_NAME})", flush=True)
                self.other_players.clear()
                self.other_player_labels.clear()
                for pid_str, pdata in players.items():
                    pid = int(pid_str)
                    if pid != self.my_id:
                        wx = float(pdata.get("wx", (float(pdata["x"]) - 0.1) / 0.8 * 24.0 - 12.0))
                        wz = float(pdata.get("wz", (float(pdata["y"]) - 0.1) / 0.8 * 24.0 - 12.0))
                        jump_y = float(pdata.get("jump_offset_y", 0.0))
                        is_r = bool(pdata.get("running", False))
                        is_w = bool(pdata.get("walking", False))
                        self.other_players[pid] = {"wx": wx, "wz": wz, "jump_y": jump_y, "running": is_r, "walking": is_w, "name": pdata.get("name")}
                        self._update_observed_label(pid, pdata)

            elif mtype == "join":
                pid = int(msg["id"])
                if pid != self.my_id:
                    wx = float(msg.get("wx", (float(msg.get("x", 0.5)) - 0.1) / 0.8 * 24.0 - 12.0))
                    wz = float(msg.get("wz", (float(msg.get("y", 0.5)) - 0.1) / 0.8 * 24.0 - 12.0))
                    jump_y = float(msg.get("jump_offset_y", 0.0))
                    is_r = bool(msg.get("running", False))
                    is_w = bool(msg.get("walking", False))
                    self.other_players[pid] = {"wx": wx, "wz": wz, "jump_y": jump_y, "running": is_r, "walking": is_w, "name": msg.get("name")}
                    self._update_observed_label(pid, msg)

            elif mtype == "pos":
                pid = int(msg["id"])
                if pid != self.my_id:
                    wx = float(msg.get("wx", (float(msg["x"]) - 0.1) / 0.8 * 24.0 - 12.0))
                    wz = float(msg.get("wz", (float(msg["y"]) - 0.1) / 0.8 * 24.0 - 12.0))
                    jump_y = float(msg.get("jump_offset_y", 0.0))
                    is_r = bool(msg.get("running", False))
                    is_w = bool(msg.get("walking", False))
                    prev_name = self.other_players.get(pid, {}).get("name")
                    self.other_players[pid] = {"wx": wx, "wz": wz, "jump_y": jump_y, "running": is_r, "walking": is_w, "name": msg.get("name") or prev_name}
                    self._update_observed_label(pid, msg)

            elif mtype == "leave":
                pid = int(msg["id"])
                self.other_players.pop(pid, None)
                self.other_player_labels.pop(pid, None)

            elif mtype == "chat":
                sender_id = int(msg.get("id", -1))
                chat_text = str(msg.get("text", "")).strip()
                if sender_id != self.my_id and chat_text:
                    sender_name = str(msg.get("name") or self.other_player_labels.get(sender_id) or f"Player {sender_id}")
                    # Never reply to other AI chicks; reply if designated responder or explicitly named!
                    if "(AI)" not in sender_name and (self.allow_chat_reply or (self.chick_name in chat_text)):
                        asyncio.create_task(self._handle_chat_with_gemini(sender_id, sender_name, chat_text))

            elif mtype == "punch_hit":
                target_id = msg.get("target_id")
                if target_id is None or int(target_id) == self.my_id:
                    self.apply_punch_hit(
                        float(msg.get("dir_x", 0.0)),
                        float(msg.get("dir_z", 1.0)),
                        bool(msg.get("headshot", False)),
                        float(msg.get("punch_side", 1.0)),
                    )

            elif mtype == "kick_hit":
                target_id = msg.get("target_id")
                if target_id is None or int(target_id) == self.my_id:
                    self.apply_kick_hit(
                        float(msg.get("dir_x", 0.0)),
                        float(msg.get("dir_z", 1.0)),
                        bool(msg.get("launch", False)),
                        float(msg.get("roll_dir", 1.0)),
                    )



    async def _motion_loop(self, ws) -> None:
        tick_rate = 30.0
        dt = 1.0 / tick_rate

        while True:
            self.step_ai(dt)

            norm_x = max(0.05, min(0.95, (self.wx + self.WORLD_LIMIT) / (2.0 * self.WORLD_LIMIT) * 0.9 + 0.05))
            norm_y = max(0.05, min(0.95, (self.wz + self.WORLD_LIMIT) / (2.0 * self.WORLD_LIMIT) * 0.9 + 0.05))

            now = time.time()
            ready_chats = [item for item in self._pending_chats if now >= item[0]]
            for item in ready_chats:
                self._pending_chats.remove(item)
                try:
                    await ws.send(json.dumps({"type": "chat", "text": item[1], "name": self.name}))
                except Exception:
                    pass

            payload = json.dumps(
                {
                    "type": "pos",
                    "x": round(norm_x, 5),
                    "y": round(norm_y, 5),
                    "wx": round(self.wx, 4),
                    "wz": round(self.wz, 4),
                    "running": self.is_running,
                    "walking": self.is_walking,
                    "mouth": self.mouth_open,
                    "blink": self.is_blinking,
                    "rot_y": round(self.rot_y, 4),
                    "rot_z": round(self.rot_z, 4),
                    "lay_pitch": round(self.lay_pitch, 4),
                    "ragdoll": round(self.ragdoll, 3),
                    "head_yaw": round(self.head_yaw, 4),
                    "head_pitch": round(self.head_pitch, 4),
                    "is_carmelito": True,
                    "chick_name": self.chick_name,
                    "character": self.character,
                    "name": self.name,
                    "kick_amount": round(self.kick_amount, 3),
                    "kick_side": round(self.kick_side, 1),
                    "punch_amount": round(self.punch_amount, 3),
                    "punch_side": round(self.punch_side, 1),
                    "jump_offset_y": round(self.jump_offset_y, 3),
                    "jump_amount": round(self.jump_amount, 3),
                    "arms_down_amount": round(self.arms_down_amount, 3),
                    "on_fire": bool(self.on_fire),
                    "tag_amount": round(self.tag_amount, 3),
                },
                separators=(",", ":"),
            )
            while self._pending_craters:
                c_wx, c_wz, c_r = self._pending_craters.pop(0)
                try:
                    await ws.send(json.dumps({"type": "crater", "wx": round(c_wx, 3), "wz": round(c_wz, 3), "radius": round(c_r, 3)}, separators=(",", ":")))
                except Exception:
                    pass
            try:
                await ws.send(payload)
            except ConnectionClosed:
                break

            await asyncio.sleep(dt)


def main() -> None:
    parser = argparse.ArgumentParser(description="Antigravity AI companion")
    parser.add_argument("--server", default="ws://127.0.0.1:8765")
    parser.add_argument("--name", default="小胖墩 (AI)")
    parser.add_argument("--character", default="pangdun")
    parser.add_argument("--chick", default="小胖墩")
    parser.add_argument("--no-auto-host", action="store_true")
    args = parser.parse_args()

    bot = AICodeCompanion(
        server_url=args.server,
        name=args.name,
        auto_host=not args.no_auto_host,
        character=args.character,
        chick_name=args.chick,
    )
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n🤖 AI left the game.")


if __name__ == "__main__":
    main()
