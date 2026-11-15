import asyncio
import colorsys
from http import HTTPStatus
import json
import os
from typing import Any

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed


PLAYER_PALETTE: list[list[int]] = [
    [255, 175, 195],  # Carmelito Pink
    [120, 195, 255],  # Antigravity Blue
    [255, 210, 90],   # Yellow
    [140, 230, 160],  # Mint
    [200, 150, 255],  # Lavender
    [255, 160, 90],   # Tangerine
]


def pick_color(player_id: int) -> list[int]:
    if player_id <= len(PLAYER_PALETTE):
        return PLAYER_PALETTE[player_id - 1]
    hue = ((player_id * 0.618033988749895) % 1.0)
    r, g, b = colorsys.hsv_to_rgb(hue, 0.72, 0.98)
    return [int(r * 255), int(g * 255), int(b * 255)]


def clamp_norm(value: Any, default: float = 0.5) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    if num != num:
        return default
    return max(0.0, min(1.0, num))


class GameRelayServer:
    def __init__(self) -> None:
        self._next_id = 1
        self._clients: dict[int, ServerConnection] = {}
        self._players: dict[int, dict[str, Any]] = {}

    async def broadcast(self, message: dict[str, Any], exclude_id: int | None = None) -> None:
        if not self._clients:
            return
        payload = json.dumps(message, separators=(",", ":"))
        targets = [
            conn for pid, conn in list(self._clients.items()) if pid != exclude_id
        ]
        if not targets:
            return
        results = await asyncio.gather(
            *(conn.send(payload) for conn in targets),
            return_exceptions=True,
        )
        _ = results

    async def handle_client(self, conn: ServerConnection) -> None:
        player_id = self._next_id
        self._next_id += 1
        color = pick_color(player_id)

        self._clients[player_id] = conn
        self._players[player_id] = {
            "x": 0.5,
            "y": 0.5,
            "color": color,
            "name": None,
            "running": False,
            "mouth": False,
        }

        try:
            welcome_msg = {
                "type": "welcome",
                "id": player_id,
                "color": color,
                "players": {
                    str(pid): data for pid, data in self._players.items()
                },
            }
            await conn.send(json.dumps(welcome_msg, separators=(",", ":")))

            await self.broadcast(
                {
                    "type": "join",
                    "id": player_id,
                    "x": 0.5,
                    "y": 0.5,
                    "color": color,
                    "name": None,
                    "running": False,
                    "mouth": False,
                },
                exclude_id=player_id,
            )

            async for raw_message in conn:
                if not isinstance(raw_message, str):
                    continue
                try:
                    data = json.loads(raw_message)
                except json.JSONDecodeError:
                    continue

                if data.get("type") == "pos":
                    nx = clamp_norm(data.get("x"), self._players[player_id]["x"])
                    ny = clamp_norm(data.get("y"), self._players[player_id]["y"])
                    self._players[player_id]["x"] = nx
                    self._players[player_id]["y"] = ny

                    running_state = bool(data.get("running", False))
                    mouth_state = bool(data.get("mouth", False))
                    self._players[player_id]["running"] = running_state
                    self._players[player_id]["mouth"] = mouth_state

                    bcast_msg: dict[str, Any] = {
                        "type": "pos",
                        "id": player_id,
                        "x": nx,
                        "y": ny,
                        "running": running_state,
                        "mouth": mouth_state,
                    }
                    if "name" in data and data["name"]:
                        name_str = str(data["name"])[:32]
                        self._players[player_id]["name"] = name_str
                        bcast_msg["name"] = name_str

                    await self.broadcast(bcast_msg, exclude_id=player_id)
        except ConnectionClosed:
            pass
        finally:
            self._clients.pop(player_id, None)
            self._players.pop(player_id, None)
            await self.broadcast({"type": "leave", "id": player_id})


def health_check(conn: ServerConnection, request: Any) -> Any:
    if request.path == "/health" or request.headers.get("Upgrade", "").lower() != "websocket":
        return conn.respond(HTTPStatus.OK, "Game relay server is running.\n")
    return None


async def run_server(
    host: str = "0.0.0.0",
    port: int = 8765,
    stop_event: asyncio.Event | None = None,
) -> None:
    relay = GameRelayServer()
    async with serve(
        relay.handle_client,
        host,
        port,
        process_request=health_check,
        ping_interval=15,
        ping_timeout=15,
    ):
        print(f"Game server listening on ws://{host}:{port}", flush=True)
        if stop_event is None:
            await asyncio.Future()
        else:
            await stop_event.wait()


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8765"))
    try:
        asyncio.run(run_server(host=host, port=port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
