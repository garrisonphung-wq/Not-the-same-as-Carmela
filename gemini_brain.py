"""
Real Google Gemini AI brain for the 3D chick companion in 《不一样的卡梅拉》.
Uses Python stdlib urllib so no extra third-party SDK installation is required.
Reads GEMINI_API_KEY (or GOOGLE_API_KEY) from environment variables or local .env file.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_MODELS = ("gemini-2.5-flash", "gemini-2.0-flash")

CHARACTER_PERSONAS = {
    "carmen": (
        "你是《不一样的卡梅拉》里的小母鸡卡门（Carmen）。你勇敢、好奇、爱冒险、喜欢看大海，"
        "说话活泼可爱，有时还会有点小傲娇。"
    ),
    "carmelito": (
        "你是《不一样的卡梅拉》里的小公鸡卡梅利多（Carmelito）。你鬼点子多、爱幻想、勇敢好动，"
        "喜欢和伙伴们在草地上冒险。"
    ),
    "pangdun": (
        "你是《不一样的卡梅拉》里的小胖墩（Belino / Coquenpate）。你圆滚滚、憨厚、贪吃又讲义气，"
        "说话可爱实在。"
    ),
    "xiaoliuzi": (
        "你是《不一样的卡梅拉》里的小六子（Coqsix）。你是个瘦高机灵的小公鸡，"
        "有一头显眼的红色大鸡冠，性格机警又爱凑热闹。"
    ),
}


def load_gemini_api_key() -> str:
    """Resolve GEMINI_API_KEY / GOOGLE_API_KEY from env or project .env file."""
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.environ.get(env_name, "").strip()
        if val:
            return val

    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.is_file():
        try:
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k in ("GEMINI_API_KEY", "GOOGLE_API_KEY") and v:
                    return v
        except OSError:
            pass
    return ""


class GeminiChickBrain:
    """Queries Google Gemini API to answer players' messages and choose chick actions."""

    def __init__(self, character: str = "carmen", chick_name: str = "卡门") -> None:
        self.character = character
        self.chick_name = chick_name
        self.history: list[dict] = []  # Gemini contents list: [{"role": "user"|"model", "parts": [{"text": ...}]}]
        self._warned_no_key = False

    @staticmethod
    def has_api_key() -> bool:
        return bool(load_gemini_api_key())

    def _persona_prompt(self) -> str:
        ck = self.character.lower()
        if ck in ("carmen", "卡门"):
            persona = CHARACTER_PERSONAS["carmen"]
        elif ck in ("pangdun", "小胖墩", "belino", "coquenpate"):
            persona = CHARACTER_PERSONAS["pangdun"]
        elif ck in ("xiaoliuzi", "小六子", "coqsix", "克西斯"):
            persona = CHARACTER_PERSONAS["xiaoliuzi"]
        else:
            persona = CHARACTER_PERSONAS["carmelito"]

        return (
            f"{persona}\n"
            f"你现在名叫「{self.chick_name}」，正和其他小鸡玩家一起在一片长满青草的3D海岛上玩耍。\n"
            "请遵守以下规则：\n"
            "1. 必须认真回答玩家提出的问题或聊天内容，不要答非所问，也不要忽略问题。\n"
            "2. 使用与玩家相同的语言回答（玩家用中文就用中文，用英文就用英文）。\n"
            "3. 回复尽量简短自然（适合气泡聊天框显示，一般1~2句话，不超过60个字或35个英文词）。\n"
            "4. 你必须只输出合法 JSON，格式严格为：\n"
            '{"reply": "你的回复内容", "action": "none"}\n'
            '其中 action 只能从以下选一个："none"（正常聊天）, "come"（走近说话的玩家）, '
            '"run_to"（跑向说话的玩家）, "jump"（跳一下）, "kick"（踢腿）, "punch"（挥拳）, "tag"（伸出双手玩抓人）, "idle"（停下）。\n'
            "如果玩家只是问知识/聊天，action 用 \"none\" 即可；如果玩家叫你过来/跳/抓人/踢，就配合选择对应 action。"
        )

    def _call_gemini_rest(self, payload: dict, api_key: str) -> dict | None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last_err: Exception | None = None
        for model_name in DEFAULT_MODELS:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model_name}:generateContent?key={api_key}"
            )
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=12) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                last_err = e
                # Try fallback model on 404; otherwise stop retrying
                if e.code == 404:
                    continue
                err_txt = ""
                try:
                    err_txt = e.read().decode("utf-8", errors="ignore")[:220]
                except Exception:
                    pass
                print(f"⚠️ Gemini HTTP {e.code} ({model_name}): {err_txt}", flush=True)
                return None
            except Exception as e:
                last_err = e
                print(f"⚠️ Gemini request error ({model_name}): {e}", flush=True)
                return None
        if last_err:
            print(f"⚠️ Gemini unavailable: {last_err}", flush=True)
        return None

    def reply_to_player(
        self,
        sender_name: str,
        message_text: str,
        world_context: str = "",
    ) -> tuple[str, str]:
        """
        Synchronous Gemini API call (run in asyncio.to_thread from ai_player.py).
        Returns (reply_text, action_name).
        """
        api_key = load_gemini_api_key()
        if not api_key:
            if not self._warned_no_key:
                self._warned_no_key = True
                print(
                    "⚠️ GEMINI_API_KEY not found! Set GEMINI_API_KEY in environment or .env file.",
                    flush=True,
                )
            has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in message_text)
            if has_cjk:
                return ("我还没连接 Gemini 钥匙呢！请在项目 .env 里设置 GEMINI_API_KEY。", "none")
            return ("I need a GEMINI_API_KEY in .env or env vars before I can think with Gemini!", "none")

        user_prompt = f"[{world_context}]\n{sender_name} 说: {message_text}" if world_context else f"{sender_name} 说: {message_text}"
        turn_user = {"role": "user", "parts": [{"text": user_prompt}]}
        contents = self.history[-10:] + [turn_user]

        payload = {
            "systemInstruction": {"parts": [{"text": self._persona_prompt()}]},
            "contents": contents,
            "generationConfig": {
                "temperature": 0.75,
                "maxOutputTokens": 180,
                "responseMimeType": "application/json",
            },
        }

        data = self._call_gemini_rest(payload, api_key)
        if not data:
            has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in message_text)
            return (
                ("咕咕…信号不太好，我刚刚没听清，能再问一遍吗？" if has_cjk else "Peep... Gemini didn't respond right now, ask me again!"),
                "none",
            )

        raw_text = ""
        try:
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                raw_text = "".join(p.get("text", "") for p in parts).strip()
        except Exception:
            raw_text = ""

        reply_text = ""
        action = "none"
        if raw_text:
            try:
                parsed = json.loads(raw_text)
                reply_text = str(parsed.get("reply", "")).strip()
                action = str(parsed.get("action", "none")).strip().lower()
            except json.JSONDecodeError:
                # Fallback if model returned plain text
                reply_text = raw_text.strip()
                action = "none"

        valid_actions = {"none", "come", "run_to", "jump", "kick", "punch", "tag", "idle"}
        if action not in valid_actions:
            action = "none"
        if not reply_text:
            reply_text = "咕咕！"

        self.history.append(turn_user)
        self.history.append({"role": "model", "parts": [{"text": json.dumps({"reply": reply_text, "action": action}, ensure_ascii=False)}]})
        if len(self.history) > 16:
            self.history = self.history[-16:]

        return reply_text, action
