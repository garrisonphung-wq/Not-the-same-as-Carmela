import os
import pygame


class SpriteManager:
    def __init__(self, base_dir: str = "assets/aligned_sprites") -> None:
        self.base_dir = base_dir
        self.still_closed: pygame.Surface | None = None
        self.still_open: pygame.Surface | None = None
        self.run_closed: list[pygame.Surface] = []
        self.run_open: list[pygame.Surface] = []
        self._scaled_cache: dict[tuple[int, int], pygame.Surface] = {}
        self.load_all()

    def load_all(self) -> None:
        p_still_closed = os.path.join(self.base_dir, "carmelito_still_closed.png")
        p_still_open = os.path.join(self.base_dir, "carmelito_still_open.png")

        if os.path.exists(p_still_closed):
            self.still_closed = pygame.image.load(p_still_closed).convert_alpha()
        if os.path.exists(p_still_open):
            self.still_open = pygame.image.load(p_still_open).convert_alpha()

        self.run_closed.clear()
        for i in range(8):
            p = os.path.join(self.base_dir, f"run_closed_{i}.png")
            if os.path.exists(p):
                self.run_closed.append(pygame.image.load(p).convert_alpha())

        self.run_open.clear()
        for i in range(8):
            p = os.path.join(self.base_dir, f"run_open_{i}.png")
            if os.path.exists(p):
                self.run_open.append(pygame.image.load(p).convert_alpha())

    def get_frame(
        self,
        is_running: bool,
        mouth_open: bool,
        anim_time: float,
        target_height: int = 140,
    ) -> pygame.Surface | None:
        target_height = max(30, min(600, int(target_height)))

        if not is_running:
            raw = self.still_open if mouth_open else self.still_closed
            key_id = 100 if mouth_open else 101
        else:
            frames = self.run_open if mouth_open else self.run_closed
            if not frames:
                raw = self.still_open if mouth_open else self.still_closed
                key_id = 100 if mouth_open else 101
            else:
                idx = int(anim_time * 10.0) % len(frames)
                raw = frames[idx]
                key_id = (200 if mouth_open else 300) + idx

        if raw is None:
            return None

        cache_key = (key_id, target_height)
        cached = self._scaled_cache.get(cache_key)
        if cached is not None:
            return cached

        orig_w, orig_h = raw.get_size()
        scale = target_height / max(1, orig_h)
        target_w = max(1, int(orig_w * scale))

        scaled = pygame.transform.smoothscale(raw, (target_w, target_height))
        self._scaled_cache[cache_key] = scaled
        return scaled
