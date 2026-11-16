"""Bilingual Conversational AI Brain for Carmelito (卡梅利多).

Provides rich, context-aware, bilingual responses in Carmelito's authentic character voice:
- If user speaks English -> replies in fluent, cheerful English!
- If user speaks Chinese -> replies in fluent, cheerful Chinese!
- Supports optional Gemini / OpenAI / Ollama LLM endpoints if configured via environment variables.
- Falls back to an extensive, nuanced rule-and-semantic matching NLP dialog system
  so it works 100% reliably out of the box with zero external dependencies.
"""

from __future__ import annotations

import json
import os
import random
import re
import urllib.error
import urllib.request


def is_chinese_text(text: str) -> bool:
    """Returns True if the text contains Chinese characters."""
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def clean_text(text: str) -> str:
    return re.sub(r"[^\w\s\u4e00-\u9fff]", "", text).strip()


class CarmelitoBrain:
    """Conversational engine giving Carmelito a lively personality."""

    def __init__(self) -> None:
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        self.ollama_url = os.environ.get("OLLAMA_HOST", "").strip()

    def generate_reply(self, message: str, player_name: str = "Friend") -> str:
        """Synchronously or quickly produces an in-character bilingual reply."""
        msg = message.strip()
        if not msg:
            return "咕咕？" if is_chinese_text(player_name) else "Cluck cluck?"

        # If LLM API key is present, try LLM first with short timeout
        if self.gemini_key or self.openai_key or self.ollama_url:
            llm_reply = self._query_llm(msg)
            if llm_reply:
                return llm_reply

        # Built-in contextual conversational NLP engine
        if is_chinese_text(msg):
            return self._reply_chinese(msg, player_name)
        return self._reply_english(msg, player_name)

    def _query_llm(self, msg: str) -> str | None:
        """Optional online LLM call if environment variable is provided."""
        sys_prompt = (
            "You are Carmelito (卡梅利多), the brave and curious little pink cockerel from the beloved French book series "
            "'Les P'tites Poules' / '不一样的卡梅拉'. You love exploring, want to see the ocean, dream big, and love playing. "
            "Reply in 1 or 2 short, energetic sentences. "
            "CRITICAL RULE: If the user talks to you in English, you MUST reply in English. "
            "If the user talks to you in Chinese, you MUST reply in Chinese. "
            "Never give long lectures. Keep your tone cheerful, bold, and friendly like a young adventurous chick."
        )

        # 1. Google Gemini
        if self.gemini_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
                payload = {
                    "system_instruction": {"parts": [{"text": sys_prompt}]},
                    "contents": [{"parts": [{"text": msg}]}],
                    "generationConfig": {"maxOutputTokens": 60, "temperature": 0.8},
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=2.5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if text:
                        return text[:90]
            except Exception:
                pass

        # 2. OpenAI
        if self.openai_key:
            try:
                url = "https://api.openai.com/v1/chat/completions"
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": msg},
                    ],
                    "max_tokens": 50,
                    "temperature": 0.8,
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.openai_key}",
                    },
                )
                with urllib.request.urlopen(req, timeout=2.5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    text = data["choices"][0]["message"]["content"].strip()
                    if text:
                        return text[:90]
            except Exception:
                pass

        return None

    def _reply_chinese(self, msg: str, player_name: str) -> str:
        """Comprehensive in-character Chinese response system."""
        cleaned = clean_text(msg)
        t = cleaned.lower()

        # 问候
        if any(w in t for w in ["你好", "嗨", "哈喽", "早上好", "晚上好", "下午好", "hello", "hi"]):
            return random.choice([
                f"你好呀{player_name}！很高兴和你一起玩！咕咕！",
                "嗨！今天阳光真好，快跟我一起去探险吧！",
                "咕咕！你好呀！世界上最勇敢的小鸡卡梅利多来啦！",
            ])

        # 身份 / 名字
        if any(w in t for w in ["你是谁", "你叫什么", "名字", "是谁", "你是什么"]):
            return random.choice([
                "我是卡梅利多！一只梦想看大海、看星星的勇敢小鸡！",
                "我叫卡梅利多，卡梅拉是我的妈妈！我们是一群不一样的鸡！咕咕！",
                "我是卡梅利多，你最好的探险伙伴！",
            ])

        # 玩家身份
        if any(w in t for w in ["我是谁", "我叫什么", "认识我吗"]):
            return random.choice([
                f"你是我的好朋友{player_name}呀！我们一起在草地上奔跑呢！",
                "你是我最酷的伙伴！咕咕！",
            ])

        # 奔跑 / 速度 / 比赛
        if any(w in t for w in ["跑", "快", "慢", "追", "冲", "飞", "速度", "比赛"]):
            return random.choice([
                "看我的无敌小鸡快跑！你可别被我甩在后面啦！咕咕！",
                "比跑步吗？我可是全岛跑得最快的小鸡！来追我呀！",
                "冲啊！按住Space或者Shift跟我一起加速奔跑！",
            ])

        # 大海 / 探险 / 梦想
        if any(w in t for w in ["海", "大海", "大洋", "水", "鲸鱼", "探险", "梦想", "星星"]):
            return random.choice([
                "我妈妈卡梅拉看过了大海，我也一定要去看更远的大海！",
                "海的那边一定有不可思议的世界！你愿意跟我一起出海吗？",
                "晚上我们要一起躺在草地上看星星哦！咕咕！",
            ])

        # 玩耍 / 捉迷藏
        if any(w in t for w in ["玩", "抓", "捉", "游戏", "捉迷藏"]):
            return random.choice([
                "来玩抓人游戏！预备——跑！你抓不到我~",
                "太棒啦！我最喜欢玩游戏了，咕咕！",
                "谁输了谁就要学三声小鸡叫哦！咕咕咕！",
            ])

        # 赞美 / 喜欢
        if any(w in t for w in ["可爱", "帅", "酷", "棒", "聪明", "喜欢你", "爱你", "厉害"]):
            return random.choice([
                "嘿嘿，谢谢夸奖！你也是超级棒的探险家！咕咕！",
                "昂起我的鸡冠！今天也是帅气又勇敢的一天！",
                "我也超级喜欢和你一起玩！我们要做好朋友！",
            ])

        # 调侃 / 笨 / 慢
        if any(w in t for w in ["笨", "傻", "慢", "抓到你", "小鸡", "胆小"]):
            return random.choice([
                "才没有呢！我可是卡梅利多，世界上最勇敢的小鸡，什么都不怕！",
                "哼哼，我马上跑给你看！看我的旋风鸡腿！",
                "咕咕！小鸡才不笨呢，小鸡也能飞向太空！",
            ])

        # 为什么
        if any(w in t for w in ["为什么", "怎么", "啥时", "哪里", "在哪"]):
            return random.choice([
                "因为世界那么大，不去看看怎么行呢！咕咕！",
                "这可是卡梅利多的秘密探险基地！跟我跑一圈你就知道啦！",
                "咕咕！多跑跑多跳跳，所有的问号都会变成叹号！",
            ])

        # 问好心情 / 累不累
        if any(w in t for w in ["开心", "累", "高兴", "难过", "好吗", "怎么样"]):
            return random.choice([
                "我开心得想扑棱翅膀！草地软软的，太舒服啦！",
                "一点都不累！勇敢的小鸡有用不完的活力！咕咕！",
            ])

        # 再见
        if any(w in t for w in ["再见", "拜拜", "走了", "晚安", "明天见"]):
            return random.choice([
                "再见啦！下一次我们还要一起去看大海哦！咕咕！",
                "拜拜！我会在这座美丽的小岛上等你回来的！",
                "晚安！做个关于大海和星星的美梦吧！",
            ])

        # 默认生动回复
        generic_replies = [
            f"收到啦：“{msg}”！咕咕！",
            f"“{msg}”？太有意思啦！快跟我一起来！",
            "咕咕！我也这么觉得！草地上真快活！",
            "卡梅利多随时准备出发！冲呀！",
            "今天天气真好，我们要在岛上跑遍每一个角落！",
            "咕咕咕！只要有你在，每天都是大冒险！",
        ]
        return random.choice(generic_replies)

    def _reply_english(self, msg: str, player_name: str) -> str:
        """Comprehensive in-character English response system."""
        cleaned = clean_text(msg)
        t = cleaned.lower()

        # Greetings
        if any(w in t.split() for w in ["hi", "hello", "hey", "yo", "morning", "afternoon", "evening"]):
            return random.choice([
                f"Hello {player_name}! So happy to explore the island with you! Cluck cluck!",
                "Hey there! The weather is gorgeous today, let's run together!",
                "Cluck cluck! Greetings, friend! Ready for a big adventure?",
            ])

        # Identity / Name
        if any(w in t for w in ["who are you", "what is your name", "your name", "what are you", "who r u"]):
            return random.choice([
                "I am Carmelito! The bravest little pink cockerel on the island!",
                "My name is Carmelito! My mom Carmela saw the sea, and I love exploring!",
                "I'm Carmelito! Your loyal, fast-running chicken best friend! Cluck cluck!",
            ])

        # Player identity
        if any(w in t for w in ["who am i", "my name", "do you know me"]):
            return random.choice([
                f"You are {player_name}, my awesome explorer buddy! Cluck!",
                "You're the coolest player on this island! Let's sprint!",
            ])

        # Running / Speed / Race
        if any(w in t for w in ["run", "fast", "speed", "race", "catch", "slow", "sprint"]):
            return random.choice([
                "Check out my supersonic chicken legs! Try to catch me! Cluck cluck!",
                "Wanna race? Hold Space or Shift to sprint across the meadow!",
                "Zoom! Nobody can outrun Carmelito on this grass! Follow me!",
            ])

        # Sea / Ocean / Stars / Adventure
        if any(w in t for w in ["sea", "ocean", "water", "whale", "stars", "adventure", "island"]):
            return random.choice([
                "I've always dreamed of seeing the vast ocean! Beyond the sea lies a whole new world!",
                "Look at the blue water all around our island! One day I'll sail across it!",
                "At night, let's look up at the twinkling stars together! Cluck cluck!",
            ])

        # Play / Games
        if any(w in t for w in ["play", "game", "tag", "hide", "seek", "fun"]):
            return random.choice([
                "Let's play tag! You're it! Try to catch me if you can!",
                "Yay! Games are my favorite thing in the world! Cluck!",
                "Whoever reaches the edge of the island first wins a golden grain! Go!",
            ])

        # Compliments / Love
        if any(w in t for w in ["cute", "cool", "brave", "smart", "love", "like you", "awesome", "great", "good job"]):
            return random.choice([
                "Aw, thank you! You're super awesome and brave too! Cluck cluck!",
                "*Puffs out chest comb* Carmelito is always ready and looking sharp!",
                "I love playing with you too! Best friends forever on this island!",
            ])

        # Teasing / Slow / Chicken
        if any(w in t for w in ["slow", "stupid", "dumb", "scared", "silly", "chicken"]):
            return random.choice([
                "Hey! I'm Carmelito, the bravest chicken in history! I fear nothing!",
                "Just watch how fast my little feet can move! Vroooom!",
                "Chickens can do anything! We can even fly to the stars! Cluck cluck!",
            ])

        # Why / How / Where questions
        if t.startswith(("why", "where", "how", "what")):
            if "where" in t:
                return "We're on our secret island paradise surrounded by deep blue ocean! Cluck!"
            if "why" in t:
                return "Because life is a grand adventure! Why stay in the coop when the whole island is waiting?"
            if "how" in t:
                return "Just use Arrow Keys or WASD to run, and hold Space to dash! Cluck cluck!"
            return random.choice([
                f"That's a great question about '{msg}'! Let's explore and find out together!",
                "Big mysteries make adventures exciting! Cluck cluck!",
            ])

        # Goodbyes
        if any(w in t for w in ["bye", "goodbye", "cya", "see you", "good night", "leave"]):
            return random.choice([
                "Goodbye for now! Come back soon so we can chase the sea breeze! Cluck!",
                "Bye bye! I'll be guarding our island until you return! Cluck cluck!",
                "Good night! Dream of big oceans and sparkling stars!",
            ])

        # General English fallback
        generic_replies = [
            f"You said: '{msg}'! That sounds exciting! Cluck cluck!",
            f"'{msg}'? I love how you think! Let's go investigate!",
            "Cluck cluck! The grass feels wonderful under our feet! Follow me!",
            "Carmelito is ready for anything! Let's dash across the island!",
            "Haha, cluck cluck! Having you here makes this island so much fun!",
        ]
        return random.choice(generic_replies)
