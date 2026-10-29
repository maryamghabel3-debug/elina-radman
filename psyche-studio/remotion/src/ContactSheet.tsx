import { ComponentType } from "react"
import { Freeze } from "remotion"
import { Scene } from "./BasheV3"

export const W = 1080
export const H = 1920
export const FPS = 30

// Frames spread across the 1200-frame (40s) timeline for the contact sheet
const FRAMES = [40, 140, 240, 340, 440, 540, 660, 800, 1000]

const CELL_W = 360
const CELL_H = 640
const SCALE = 1 / 3 // 360/1080

export const ContactSheet: ComponentType = () => (
  <div
    style={{
      width: W,
      height: H,
      display: "grid",
      gridTemplateColumns: `repeat(3, ${CELL_W}px)`,
      gridTemplateRows: `repeat(3, ${CELL_H}px)`,
      gap: 0,
      background: "#000000",
    }}
  >
    {FRAMES.map((frame, i) => (
      <div
        key={i}
        style={{
          overflow: "hidden",
          width: CELL_W,
          height: CELL_H,
          background: "#050508",
        }}
      >
        <Freeze frame={frame}>
          <div
            style={{
              width: 1080,
              height: 1920,
              transform: `scale(${SCALE})`,
              transformOrigin: "top left",
            }}
          >
            <Scene />
          </div>
        </Freeze>
      </div>
    ))}
  </div>
)
