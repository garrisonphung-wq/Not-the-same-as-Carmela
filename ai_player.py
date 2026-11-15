import argparse
import asyncio
import json
import math
import os
import random
import sys
import threading
from urllib.parse import urlparse

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

import server as game_server


def is_local_server_url(server_url: str) -> tuple[bool, int]:
    parsed = urlparse(server_url)
    host = (parsed.hostname or "").lower()
    port = parsed.port or (443 if parsed.scheme == "wss" else 8765)
    return host in {"127.0.0.1", "localhost", "::1", "0.0.0.0"}, port


class AICodeCompanion:
    def __init__(
        self,
        server_url: str = "ws://127.0.0.1:8765",
        name: str = "Antigravity (AI)",
        auto_host: bool = True,
    ) -> None:
        self.server_url = server_url
        self.name = name
        self.auto_host = auto_host

        self.my_id: int | None = None
        self.my_color: list[int] = [120, 195, 255]
        self.target_id: int | None = None
        self.target_pos = [0.5, 0.65]
        self.pos = [0.38, 0.65]

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

    async def run(self) -> None:
        print(f"🤖 {self.name} connecting to {self.server_url}...", flush=True)
        is_local, port = is_local_server_url(self.server_url)

        first_retry = True
        while True:
            try:
                async with connect(self.server_url, ping_interval=15, ping_timeout=15) as ws:
                    print(f"🤖 {self.name} connected!", flush=True)
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
                print(f"🤖 {self.name} joined as Player {self.my_id}", flush=True)
                for pid_str, pdata in players.items():
                    pid = int(pid_str)
                    if pid != self.my_id:
                        self.target_id = pid
                        self.target_pos = [float(pdata["x"]), float(pdata["y"])]
                        break

            elif mtype == "join":
                pid = int(msg["id"])
                if pid != self.my_id and self.target_id is None:
                    self.target_id = pid
                    self.target_pos = [float(msg.get("x", 0.5)), float(msg.get("y", 0.65))]

            elif mtype == "pos":
                pid = int(msg["id"])
                if pid == self.target_id:
                    self.target_pos = [float(msg["x"]), float(msg["y"])]

            elif mtype == "leave":
                pid = int(msg["id"])
                if pid == self.target_id:
                    self.target_id = None

    async def _motion_loop(self, ws) -> None:
        tick_rate = 60.0
        dt = 1.0 / tick_rate
        t = 0.0

        while True:
            t += dt

            if self.target_id is not None:
                tx, ty = self.target_pos
                # Keep a playful distance from player
                angle = t * 2.2
                dest_x = max(0.08, min(0.92, tx + 0.12 * math.cos(angle)))
                dest_y = max(0.15, min(0.88, ty + 0.08 * math.sin(angle)))

                self.pos[0] += (dest_x - self.pos[0]) * 0.14
                self.pos[1] += (dest_y - self.pos[1]) * 0.14
            else:
                pass

            self.pos[0] = max(0.08, min(0.92, self.pos[0]))
            self.pos[1] = max(0.15, min(0.88, self.pos[1]))

            payload = json.dumps(
                {
                    "type": "pos",
                    "x": round(self.pos[0], 5),
                    "y": round(self.pos[1], 5),
                    "is_carmelito": False,
                    "name": self.name,
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
    parser.add_argument("--name", default="Antigravity (AI)")
    parser.add_argument("--no-auto-host", action="store_true")
    args = parser.parse_args()

    bot = AICodeCompanion(
        server_url=args.server,
        name=args.name,
        auto_host=not args.no_auto_host,
    )
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n🤖 AI left the game.")


if __name__ == "__main__":
    main()
