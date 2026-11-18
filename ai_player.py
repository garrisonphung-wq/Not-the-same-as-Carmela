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

import server as game_server
from carmelito_ai_brain import CarmelitoBrain, PangdunBrain, CarmenBrain

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
    ) -> None:
        self.server_url = server_url
        self.name = name
        self.auto_host = auto_host
        self.character = character
        self.chick_name = chick_name

        self.my_id: int | None = None
        self.my_color: list[int] = [120, 195, 255]
        self.other_players: dict[int, tuple[float, float]] = {}
        self.other_player_labels: dict[int, str] = {}

        # Autonomous 3D world position & posture (starts visible in the grass field)
        self.wx = 2.2
        self.wz = 4.5
        self.rot_y = math.pi * 0.85  # Initially facing somewhat toward center/player
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

        self.action_cooldown = random.uniform(3.0, 7.0)

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
        char_key = character.lower()
        if char_key in ("pangdun", "小胖墩", "belino", "coquenpate"):
            self.brain = PangdunBrain()
        elif char_key in ("carmen", "卡门"):
            self.brain = CarmenBrain()
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

    def _choose_next_action(self) -> None:
        """
        AI freely chooses what to do next:
        - Mostly wanders or sprints to random places anywhere across the grass field.
        - Often pauses to look around curiously or chirp.
        - Only rarely (by its own whim) decides to wander near another player.
        """
        roll = random.random()

        # If far from center, gently bias back into the open meadow
        dist_from_origin = math.hypot(self.wx, self.wz)
        if dist_from_origin > self.WORLD_LIMIT * 0.85:
            angle = math.atan2(-self.wx, -self.wz) + random.uniform(-0.7, 0.7)
            dist = random.uniform(8.0, 22.0)
            self.dest_x = max(-self.WORLD_LIMIT, min(self.WORLD_LIMIT, self.wx + math.sin(angle) * dist))
            self.dest_z = max(-self.WORLD_LIMIT, min(self.WORLD_LIMIT, self.wz + math.cos(angle) * dist))
            self.mode = "run" if random.random() < 0.35 else "walk"
            self.mode_timer = random.uniform(3.5, 7.0)
            return

        if roll < 0.25:
            # Stop, rest, and look around on the grass
            self.mode = "idle"
            self.mode_timer = random.uniform(1.4, 4.0)
            self.is_walking = False
            self.is_running = False
            self.target_head_yaw = random.uniform(-0.9, 0.9)
            self.target_head_pitch = random.uniform(-0.25, 0.45)
        elif roll < 0.65:
            # Stroll playfully in a local radius around their sector
            angle = random.uniform(0.0, 2.0 * math.pi)
            dist = random.uniform(6.0, 24.0)
            self.dest_x = max(-self.WORLD_LIMIT, min(self.WORLD_LIMIT, self.wx + math.sin(angle) * dist))
            self.dest_z = max(-self.WORLD_LIMIT, min(self.WORLD_LIMIT, self.wz + math.cos(angle) * dist))
            self.mode = "walk"
            self.mode_timer = random.uniform(3.0, 7.5)
        elif roll < 0.90:
            # Run excitedly across the grass
            angle = random.uniform(0.0, 2.0 * math.pi)
            dist = random.uniform(12.0, 38.0)
            self.dest_x = max(-self.WORLD_LIMIT, min(self.WORLD_LIMIT, self.wx + math.sin(angle) * dist))
            self.dest_z = max(-self.WORLD_LIMIT, min(self.WORLD_LIMIT, self.wz + math.cos(angle) * dist))
            self.mode = "run"
            self.mode_timer = random.uniform(2.5, 5.5)
        else:
            # Curious exploration hop
            angle = random.uniform(0.0, 2.0 * math.pi)
            dist = random.uniform(8.0, 28.0)
            self.dest_x = max(-self.WORLD_LIMIT, min(self.WORLD_LIMIT, self.wx + math.sin(angle) * dist))
            self.dest_z = max(-self.WORLD_LIMIT, min(self.WORLD_LIMIT, self.wz + math.cos(angle) * dist))
            self.mode = "walk" if random.random() < 0.65 else "run"
            self.mode_timer = random.uniform(2.5, 6.0)

    def step_ai(self, dt: float) -> None:
        self.mode_timer -= dt
        self.head_timer -= dt
        self.mouth_timer -= dt
        self.blink_timer -= dt

        if self.mode_timer <= 0.0:
            self._choose_next_action()

        if self.blink_timer <= 0.0:
            if self.is_blinking:
                self.is_blinking = False
                self.blink_timer = random.uniform(0.16, 0.24) if random.random() < 0.18 else random.uniform(2.6, 5.0)
            else:
                self.is_blinking = True
                self.blink_timer = 0.16

        self.chat_timer -= dt
        if self.chat_timer <= 0.0:
            self.chat_timer = random.uniform(9.0, 18.0)
            phrases = [
                "咕咕！天气真好！",
                "看我的，跑得飞快！",
                "我想去看海！",
                "卡梅利多最勇敢啦！",
                "草地真舒服！",
                "来抓我呀！",
                "今天也是元气满满的一天！",
                "呼呼，跑累了歇会儿~",
            ]
            self._pending_chats.append((time.time() + 0.2, random.choice(phrases)))

        if self.mouth_timer <= 0.0:
            if self.mouth_open:
                self.mouth_open = False
                self.mouth_timer = random.uniform(2.2, 6.0)
            elif random.random() < 0.35:
                self.mouth_open = True
                self.mouth_timer = random.uniform(0.45, 1.2)
            else:
                self.mouth_timer = random.uniform(1.8, 4.0)

        if self.mode in ("walk", "run"):
            dx = self.dest_x - self.wx
            dz = self.dest_z - self.wz
            dist = math.hypot(dx, dz)

            if dist < 0.6:
                self._choose_next_action()
            else:
                desired_yaw = math.atan2(dx, dz)
                diff = wrap_angle(desired_yaw - self.rot_y)
                max_turn = self.TURN_SPEED * dt
                if abs(diff) <= max_turn:
                    self.rot_y = desired_yaw
                else:
                    self.rot_y = wrap_angle(self.rot_y + math.copysign(max_turn, diff))

                speed = self.RUN_SPEED if self.mode == "run" else self.WALK_SPEED
                # Slow forward movement while turning sharply
                align_factor = max(0.25, math.cos(min(math.pi * 0.5, abs(diff))))
                step_dist = speed * align_factor * dt
                self.wx += math.sin(self.rot_y) * step_dist
                self.wz += math.cos(self.rot_y) * step_dist
                self.wx = max(-self.WORLD_LIMIT, min(self.WORLD_LIMIT, self.wx))
                self.wz = max(-self.WORLD_LIMIT, min(self.WORLD_LIMIT, self.wz))

                self.is_running = (self.mode == "run")
                self.is_walking = (self.mode == "walk")

                if self.head_timer <= 0.0:
                    self.target_head_yaw = max(-0.6, min(0.6, diff * 0.8 + random.uniform(-0.25, 0.25)))
                    self.target_head_pitch = random.uniform(-0.12, 0.22)
                    self.head_timer = random.uniform(1.0, 2.4)
        else:
            self.is_walking = False
            self.is_running = False
            if self.head_timer <= 0.0:
                self.target_head_yaw = random.uniform(-0.95, 0.95)
                self.target_head_pitch = random.uniform(-0.25, 0.45)
                self.head_timer = random.uniform(0.9, 2.2)

        # Smooth natural neck interpolation
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

        # Jump physics
        if self.jump_state == "crouching":
            self.crouch_timer += dt
            cp = min(1.0, self.crouch_timer / self.crouch_duration)
            self.jump_amount = math.sin(cp * (math.pi / 2))
            if self.crouch_timer >= self.crouch_duration:
                self.jump_state = "airborne"
                self.jump_velocity_y = self.JUMP_IMPULSE
                self.jump_offset_y = 0.08
                self.jump_amount = 0.0
        elif self.jump_state == "airborne":
            self.jump_offset_y += self.jump_velocity_y * dt
            self.jump_velocity_y -= self.GRAVITY * dt
            self.jump_amount = 0.0
            if self.jump_offset_y <= 0.0:
                self.jump_offset_y = 0.0
                self.jump_velocity_y = 0.0
                self.jump_state = "idle"
                self.jump_amount = 0.0
        else:
            self.jump_amount = 0.0

        # Occasional playful kicks / punches / jumps while roaming
        self.action_cooldown -= dt
        if self.action_cooldown <= 0.0 and not self.is_kicking and not self.is_punching and self.jump_state == "idle":
            self.action_cooldown = random.uniform(3.5, 7.5)
            roll = random.random()
            if roll < 0.28:
                # Playful jump hop!
                self.jump_state = "crouching"
                self.crouch_timer = 0.0
                self.jump_amount = 0.0
            elif roll < 0.52:
                self.is_kicking = True
                self.kick_timer = 0.0
                self.kick_side = -self.kick_side
            elif roll < 0.76:
                self.is_punching = True
                self.punch_timer = 0.0
                self.punch_side = -self.punch_side
            else:
                # Playful tag reach (raise hands forward like zombie to play tag!)
                self.is_tagging = True
                self.tag_timer = 0.0
                self.tag_duration = random.uniform(1.8, 3.2)

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
                        self.other_players[pid] = (wx, wz)
                        self._update_observed_label(pid, pdata)

            elif mtype == "join":
                pid = int(msg["id"])
                if pid != self.my_id:
                    wx = float(msg.get("wx", (float(msg.get("x", 0.5)) - 0.1) / 0.8 * 24.0 - 12.0))
                    wz = float(msg.get("wz", (float(msg.get("y", 0.5)) - 0.1) / 0.8 * 24.0 - 12.0))
                    self.other_players[pid] = (wx, wz)
                    self._update_observed_label(pid, msg)

            elif mtype == "pos":
                pid = int(msg["id"])
                if pid != self.my_id:
                    wx = float(msg.get("wx", (float(msg["x"]) - 0.1) / 0.8 * 24.0 - 12.0))
                    wz = float(msg.get("wz", (float(msg["y"]) - 0.1) / 0.8 * 24.0 - 12.0))
                    self.other_players[pid] = (wx, wz)
                    self._update_observed_label(pid, msg)

            elif mtype == "leave":
                pid = int(msg["id"])
                self.other_players.pop(pid, None)
                self.other_player_labels.pop(pid, None)

            elif mtype == "chat":
                sender_id = int(msg.get("id", -1))
                chat_text = str(msg.get("text", "")).strip()
                if sender_id != self.my_id and chat_text:
                    # Look up player name or label if available
                    player_name = str(msg.get("name") or self.other_player_labels.get(sender_id, "Friend"))
                    # Generate bilingual in-character response using CarmelitoBrain
                    reply = self.brain.generate_reply(chat_text, player_name=player_name)
                    # Natural typing delay between 0.6 and 1.4 seconds
                    delay_send = time.time() + random.uniform(0.6, 1.4)
                    self._pending_chats.append((delay_send, reply))
                    print(f"🤖 Carmelito replying to player {sender_id} ({player_name}) with: '{reply}'", flush=True)

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
                    "tag_amount": round(self.tag_amount, 3),
                },
                separators=(",", ":"),
            )
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
