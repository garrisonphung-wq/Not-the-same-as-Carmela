import asyncio
import colorsys
from http import HTTPStatus
import json
import math
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
    if not math.isfinite(num):
        return default
    return max(0.0, min(1.0, num))


def safe_float(value: Any, default: float = 0.0, limit: float = 10000.0) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(num):
        return default
    return max(-limit, min(limit, num))


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
            "in_game": False,
            "x": 0.5,
            "y": 0.5,
            "wx": 0.0,
            "wz": 0.0,
            "color": color,
            "name": None,
            "chick_name": "卡梅利多",
            "running": False,
            "walking": False,
            "mouth": False,
            "blink": False,
            "rot_y": 0.0,
            "rot_z": 0.0,
            "lay_pitch": 0.0,
            "ragdoll": 0.0,
            "head_yaw": 0.0,
            "head_pitch": 0.0,
            "is_carmelito": True,
            "character": "carmelito",
            "kick_amount": 0.0,
            "kick_side": 1.0,
            "punch_amount": 0.0,
            "punch_side": 1.0,
            "jump_offset_y": 0.0,
            "jump_amount": 0.0,
            "tag_amount": 0.0,
        }

        try:
            welcome_msg = {
                "type": "welcome",
                "id": player_id,
                "color": color,
                "players": {
                    str(pid): data for pid, data in self._players.items()
                    if data.get("in_game", False)
                },
            }
            await conn.send(json.dumps(welcome_msg, separators=(",", ":")))

            async for raw_message in conn:
                if not isinstance(raw_message, str):
                    continue
                try:
                    data = json.loads(raw_message)
                except json.JSONDecodeError:
                    continue

                if data.get("type") == "pos":
                    p = self._players[player_id]
                    nx = clamp_norm(data.get("x"), p["x"])
                    ny = clamp_norm(data.get("y"), p["y"])
                    p["x"] = nx
                    p["y"] = ny

                    if "wx" in data:
                        p["wx"] = safe_float(data.get("wx"), p["wx"])
                    if "wz" in data:
                        p["wz"] = safe_float(data.get("wz"), p["wz"])

                    p["running"] = bool(data.get("running", False))
                    p["walking"] = bool(data.get("walking", False))
                    p["mouth"] = bool(data.get("mouth", False))
                    p["blink"] = bool(data.get("blink", False))
                    p["rot_y"] = safe_float(data.get("rot_y", p["rot_y"]), p["rot_y"], limit=100.0)
                    if "rot_z" in data:
                        p["rot_z"] = safe_float(data.get("rot_z", 0.0), 0.0, limit=10.0)
                    if "lay_pitch" in data:
                        p["lay_pitch"] = safe_float(data.get("lay_pitch", 0.0), 0.0, limit=10.0)
                    if "ragdoll" in data:
                        p["ragdoll"] = safe_float(data.get("ragdoll", 0.0), 0.0, limit=2.0)
                    p["head_yaw"] = safe_float(data.get("head_yaw", p["head_yaw"]), p["head_yaw"], limit=10.0)
                    p["head_pitch"] = safe_float(data.get("head_pitch", p["head_pitch"]), p["head_pitch"], limit=10.0)
                    if "kick_amount" in data:
                        p["kick_amount"] = safe_float(data.get("kick_amount", 0.0), 0.0, limit=2.0)
                    if "kick_side" in data:
                        p["kick_side"] = safe_float(data.get("kick_side", 1.0), 1.0, limit=2.0)
                    if "punch_amount" in data:
                        p["punch_amount"] = safe_float(data.get("punch_amount", 0.0), 0.0, limit=2.0)
                    if "punch_side" in data:
                        p["punch_side"] = safe_float(data.get("punch_side", 1.0), 1.0, limit=2.0)
                    if "jump_offset_y" in data:
                        p["jump_offset_y"] = safe_float(data.get("jump_offset_y", 0.0), 0.0, limit=100000.0)
                    if "jump_amount" in data:
                        p["jump_amount"] = safe_float(data.get("jump_amount", 0.0), 0.0, limit=2.0)
                    if "tag_amount" in data:
                        p["tag_amount"] = safe_float(data.get("tag_amount", 0.0), 0.0, limit=2.0)
                    if "character" in data and data["character"]:
                        p["character"] = str(data["character"])[:32]
                    if "is_carmelito" in data:
                        p["is_carmelito"] = bool(data["is_carmelito"])
                    if "chick_name" in data and data["chick_name"]:
                        p["chick_name"] = str(data["chick_name"])[:32]
                    elif p["is_carmelito"] and not p["chick_name"]:
                        p["chick_name"] = "卡梅利多"

                    bcast_msg: dict[str, Any] = {
                        "type": "pos",
                        "id": player_id,
                        "x": nx,
                        "y": ny,
                        "wx": p["wx"],
                        "wz": p["wz"],
                        "running": p["running"],
                        "walking": p["walking"],
                        "mouth": p["mouth"],
                        "blink": p["blink"],
                        "rot_y": p["rot_y"],
                        "rot_z": p.get("rot_z", 0.0),
                        "lay_pitch": p.get("lay_pitch", 0.0),
                        "ragdoll": p.get("ragdoll", 0.0),
                        "head_yaw": p["head_yaw"],
                        "head_pitch": p["head_pitch"],
                        "is_carmelito": p["is_carmelito"],
                        "character": p.get("character", "carmelito"),
                        "kick_amount": p.get("kick_amount", 0.0),
                        "kick_side": p.get("kick_side", 1.0),
                        "punch_amount": p.get("punch_amount", 0.0),
                        "punch_side": p.get("punch_side", 1.0),
                        "jump_offset_y": p.get("jump_offset_y", 0.0),
                        "jump_amount": p.get("jump_amount", 0.0),
                        "tag_amount": p.get("tag_amount", 0.0),
                        "on_fire": p.get("on_fire", False),
                    }
                    if p["chick_name"]:
                        bcast_msg["chick_name"] = p["chick_name"]
                    if "name" in data:
                        name_str = str(data["name"] or "").strip()[:32]
                        p["name"] = name_str if name_str else None
                    if p.get("name"):
                        bcast_msg["name"] = p["name"]

                    if not p.get("in_game", False):
                        p["in_game"] = True
                        join_msg = dict(bcast_msg)
                        join_msg["type"] = "join"
                        join_msg["color"] = p["color"]
                        await self.broadcast(join_msg, exclude_id=player_id)
                    else:
                        await self.broadcast(bcast_msg, exclude_id=player_id)
                elif data.get("type") == "kick_hit":
                    try:
                        target_id = int(data.get("target_id", -1))
                    except (TypeError, ValueError):
                        target_id = -1
                    if target_id in self._clients and target_id != player_id:
                        hit_msg = {
                            "type": "kick_hit",
                            "from_id": player_id,
                            "target_id": target_id,
                            "dir_x": safe_float(data.get("dir_x", 0.0), 0.0, limit=2.0),
                            "dir_z": safe_float(data.get("dir_z", 1.0), 1.0, limit=2.0),
                            "launch": bool(data.get("launch", False)),
                            "roll_dir": 1.0 if safe_float(data.get("roll_dir", 1.0), 1.0, limit=2.0) >= 0.0 else -1.0,
                        }
                        try:
                            await self._clients[target_id].send(json.dumps(hit_msg, separators=(",", ":")))
                        except Exception:
                            pass
                elif data.get("type") == "punch_hit":
                    try:
                        target_id = int(data.get("target_id", -1))
                    except (TypeError, ValueError):
                        target_id = -1
                    if target_id in self._clients and target_id != player_id:
                        punch_msg = {
                            "type": "punch_hit",
                            "from_id": player_id,
                            "target_id": target_id,
                            "dir_x": safe_float(data.get("dir_x", 0.0), 0.0, limit=2.0),
                            "dir_z": safe_float(data.get("dir_z", 1.0), 1.0, limit=2.0),
                            "headshot": bool(data.get("headshot", False)),
                            "punch_side": 1.0 if safe_float(data.get("punch_side", 1.0), 1.0, limit=2.0) >= 0.0 else -1.0,
                        }
                        try:
                            await self._clients[target_id].send(json.dumps(punch_msg, separators=(",", ":")))
                        except Exception:
                            pass
                elif data.get("type") == "chat":
                    text = str(data.get("text", "")).strip()[:280]
                    if text:
                        p = self._players.get(player_id, {})
                        sender_name = str(data.get("name") or p.get("name") or p.get("chick_name") or "卡梅利多")[:32]
                        chat_msg = {
                            "type": "chat",
                            "id": player_id,
                            "name": sender_name,
                            "text": text,
                        }
                        await self.broadcast(chat_msg)
        except ConnectionClosed:
            pass
        finally:
            self._clients.pop(player_id, None)
            gone = self._players.pop(player_id, None)
            if gone and gone.get("in_game", False):
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
        print(f"Game relay server listening on ws://{host}:{port}", flush=True)
        if stop_event is not None:
            await stop_event.wait()
        else:
            await asyncio.Future()


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8765"))
    try:
        asyncio.run(run_server(host=host, port=port))
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
