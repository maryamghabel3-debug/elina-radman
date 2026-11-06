#!/usr/bin/env python3
"""نمونه‌ی بازسازی استایل: صحنه‌ی «ترس از هوش مصنوعی».

سه صحنه از الگوی مشاهده‌شده در example.mp4 بازسازی می‌شود:
  ۱) چشم/ساعت با تیک  +  آدمک
  ۲) برچسب‌های پیرامون با خط راهنما
  ۳) زیرنویس کرااوکه (نوع‌نویسی با رنگ روشن)

اجرا:  python scripts/demo_kino_scene.py
خروجی: out/kino-demo/kino-demo.mp4
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from motion.kino_engine import (  # noqa: E402
    Circle, KinoScene, Label, Line, Person, Polyline, Ticks, eye_clock,
)

DUR = 12.0


def build() -> KinoScene:
    scene = KinoScene(duration=DUR, chapter="ترس اصلی")

    # ---- ۱) چشم/ساعت مرکزی -------------------------------------------
    scene.extend(eye_clock((360, 400), radius=92, at=0.0))

    # ---- ۲) آدمک زیر آن ----------------------------------------------
    scene.add(Person(center=(360, 830), scale=1.5, at=1.6, dur=1.0))

    # ---- ۳) برچسب‌های پیرامون با خط راهنما (RTL) ----------------------
    scene.add(Label(pos=(500, 250), text="باورهایت", size=22,
                    leader_to=(432, 350), at=3.0, dur=0.9))
    scene.add(Label(pos=(250, 330), text="ترس از ناشناخته", size=22,
                    leader_to=(300, 392), at=3.6, dur=0.9))

    # ---- ۴) قوس‌های تزئینی -------------------------------------------
    scene.add(Circle(center=(360, 400), radius=150, at=4.4, dur=1.6, color=(70, 70, 70)))

    # ---- ۵) خط بستن پایین --------------------------------------------
    scene.add(Line(p0=(180, 940), p1=(540, 940), at=5.4, dur=0.8, color=(70, 70, 70)))

    # ---- ۶) زیرنویس کرااوکه ------------------------------------------
    scene.set_captions([
        (0.4, 4.2, "یه ترس اصلی تون اینه که از ما باهوش‌تر"),
        (4.4, 8.2, "می‌شه و به ما دستور می‌ده"),
    ])

    return scene


if __name__ == "__main__":
    out = ROOT / "out" / "kino-demo"
    scene = build()
    mp4 = scene.render(out)
    size = mp4.stat().st_size
    print(f"✓ {mp4.relative_to(ROOT)}  ({size/1024:.0f} KB)")
