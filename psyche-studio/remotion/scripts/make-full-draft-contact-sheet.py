#!/usr/bin/env python3
"""Extract twelve labelled narrative frames from the full draft MP4."""
import json
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PSYCHE = Path(__file__).resolve().parents[2]
OUT = PSYCHE / "output" / "eli_elina_full_draft_v1"
VIDEO = OUT / "eli_elina_full_draft_v1.mp4"
CUES = OUT / "full_cues.json"
SHEET = OUT / "CONTACT_SHEET.png"
WORK = PSYCHE / ".draft_tools" / "contact_frames"

STORY = [
    (1, "Phone ping / opening", 0.42),
    (4, "The short reply", 0.44),
    (7, "Thought storm", 0.42),
    (13, "Block-stamp impulse", 0.40),
    (14, "Stop / freeze", 0.30),
    (16, "Rewind the moment", 0.42),
    (20, "Text has no tone", 0.50),
    (22, "Mind-reading impact", 0.20),
    (25, "Fact vs. story split", 0.50),
    (28, "Check-in message", 0.48),
    (30, "Clarifying reply", 0.48),
    (35, "Final gag / CTA space", 0.50),
]


def ffmpeg_path() -> str:
    if os.environ.get("FFMPEG"):
        return os.environ["FFMPEG"]
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def main():
    data=json.loads(CUES.read_text(encoding="utf-8"))
    by_turn={c["turn"]:c for c in data["lines"]}
    frames=[]
    for turn,label,offset in STORY:
        c=by_turn[turn]
        frame=min(data["durationInFrames"]-1, c["startFrame"]+round(offset*data["fps"]))
        frames.append((frame,label,frame/data["fps"]))
    WORK.mkdir(parents=True,exist_ok=True)
    expr="+".join(f"eq(n\\,{f})" for f,_,_ in frames)
    pattern=WORK/"frame-%02d.png"
    cmd=[ffmpeg_path(),"-hide_banner","-v","error","-y","-i",str(VIDEO),"-vf",f"select='{expr}'","-fps_mode","passthrough","-start_number","1",str(pattern)]
    subprocess.run(cmd,check=True)
    try:
        font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",19)
    except OSError:
        font=ImageFont.load_default()
    cell_w,frame_h,label_h=360,640,42
    cols,rows=3,4
    sheet=Image.new("RGB",(cols*cell_w,rows*(frame_h+label_h)),"#f6f4ef")
    draw=ImageDraw.Draw(sheet)
    for i,(_,label,seconds) in enumerate(frames,1):
        p=WORK/f"frame-{i:02d}.png"
        with Image.open(p) as source:
            thumb=source.convert("RGB").resize((cell_w,frame_h),Image.Resampling.LANCZOS)
        col=(i-1)%cols; row=(i-1)//cols
        x=col*cell_w; y=row*(frame_h+label_h)
        sheet.paste(thumb,(x,y+label_h))
        draw.rectangle((x,y,x+cell_w-1,y+label_h-1),fill="#1f3237")
        title=f"{i:02d}  {label}  |  {seconds:05.1f}s"
        draw.text((x+12,y+11),title,font=font,fill="#ffffff")
        draw.rectangle((x,y,x+cell_w-1,y+frame_h+label_h-1),outline="#b7c1bd",width=2)
    sheet.save(SHEET,optimize=True)
    print(f"Wrote {SHEET}")
    for i,(frame,label,sec) in enumerate(frames,1):
        print(f"{i:02d} frame={frame} t={sec:.2f}s {label}")

if __name__=="__main__": main()
