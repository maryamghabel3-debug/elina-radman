import { AbsoluteFill, useCurrentFrame, staticFile } from "remotion"
import { useEffect, useState } from "react"
import { EliPalette } from "./palette"
import { EliV2Pose, projectToFrame } from "./pose2"
import { CAMERA2 } from "./Room2"
import { easeOutBack, easeInOut, mix, clamp01 } from "../timeline"

/**
 * DOM overlay layer for V2.
 *
 * Two things are *not* 3D on purpose:
 *
 *  1. The Persian notification text «باشه» on the phone screen. Rendering it as
 *     an HTML overlay gives real browser RTL shaping with the bundled Vazirmatn
 *     font — 3D text geometry would need a font atlas and would not shape
 *     Arabic script correctly. The overlay is positioned by projecting the 3D
 *     screen plane through the actual camera, so it tracks the phone exactly.
 *
 *  2. The thought shapes: بزرگ «؟» marks and icon bubbles. These are big,
 *     readable, in a contrasting colour, and they pop out of Eli's head.
 *     Doing them in DOM keeps the glyphs crisp at any scale.
 *
 * Everything here is driven by the frame number, like the 3D scene.
 */

export const W2 = 1080
export const H2 = 1920

const FONT = "Vazirmatn, system-ui, sans-serif"

/* --------------------------------------------------------- font loading */

const useVazirmatn = () => {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    const url = staticFile("fonts/Vazirmatn-Bold.ttf")
    const face = new FontFace("Vazirmatn", `url(${url})`, { weight: "700" })
    face
      .load()
      .then((loaded) => {
        document.fonts.add(loaded)
        setReady(true)
      })
      .catch(() => setReady(true)) // fall back silently, layout still correct
  }, [])
  return ready
}

/* ------------------------------------------------------------ notification */

const PhoneBubble: React.FC<{ pal: EliPalette; pose: EliV2Pose; camera: [number, number, number] }> = ({
  pal,
  pose,
  camera,
}) => {
  const frame = useCurrentFrame()
  const t = frame / 30

  // centre of the phone screen in world space (table at 1.45/-0.38 rot, phone
  // group at y 0.675 local). Projected through the real camera.
  const screenCenter: [number, number, number] = [-1.12 + 0.02, -0.18, 0.82]
  const proj = projectToFrame(screenCenter, { position: camera, pitch: CAMERA2.pitch, fov: CAMERA2.fov }, W2, H2)

  const appear = clamp01(mix(frame, [2.45 * 30, 2.95 * 30], [0, 1], easeOutBack))
  if (appear <= 0.01) return null

  const phoneW = proj.scale * 0.44
  const phoneH = proj.scale * 0.86

  return (
    <div
      style={{
        position: "absolute",
        left: proj.x - phoneW / 2,
        top: proj.y - phoneH / 2,
        width: phoneW,
        height: phoneH,
        opacity: appear,
        transform: `scale(${0.92 + appear * 0.08})`,
        transformOrigin: "center",
        pointerEvents: "none",
      }}
    >
      {/* the chat bubble sits on the phone screen */}
      <div
        style={{
          position: "absolute",
          top: phoneH * 0.3,
          left: phoneW * 0.08,
          right: phoneW * 0.08,
          background: pal.bubbleFill,
          borderRadius: phoneH * 0.045,
          padding: `${phoneH * 0.022}px ${phoneW * 0.05}px`,
          display: "flex",
          alignItems: "center",
          gap: phoneW * 0.04,
          boxShadow: `0 ${phoneH * 0.012}px ${phoneH * 0.03}px rgba(0,0,0,0.35)`,
          direction: "rtl",
        }}
      >
        {/* avatar dot, reads as the sender */}
        <div
          style={{
            width: phoneW * 0.14,
            height: phoneW * 0.14,
            borderRadius: "50%",
            background: pal.accent,
            flex: "0 0 auto",
          }}
        />
        <div
          style={{
            fontFamily: FONT,
            fontWeight: 700,
            fontSize: phoneH * 0.085,
            lineHeight: 1.5,
            color: pal.bubbleText,
            direction: "rtl",
            unicodeBidi: "plaintext",
            // keep the glyphs intact at any projection scale
            transform: "translateZ(0)",
            whiteSpace: "nowrap",
          }}
        >
          باشه
        </div>
      </div>

      {/* notification pill above it, so the beat is unmistakable */}
      <div
        style={{
          position: "absolute",
          top: phoneH * 0.12,
          left: phoneW * 0.14,
          right: phoneW * 0.14,
          height: phoneH * 0.07,
          borderRadius: phoneH * 0.035,
          background: pal.accent,
          opacity: 0.95,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div
          style={{
            width: phoneW * 0.34,
            height: phoneH * 0.012,
            borderRadius: 4,
            background: "rgba(0,0,0,0.35)",
            opacity: 0.55,
          }}
        />
      </div>

      {/* ripple rings on the arrival frame: sells "notification" */}
      {[0, 1].map((i) => {
        const start = 2.45 * 30 + i * 6
        const k = clamp01((frame - start) / 22)
        if (k <= 0 || k >= 1) return null
        const size = phoneW * (1 + k * 1.8)
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: phoneW / 2 - size / 2,
              top: phoneH / 2 - size / 2,
              width: size,
              height: size,
              borderRadius: "50%",
              border: `${Math.max(2, phoneW * 0.02)}px solid ${pal.accent}`,
              opacity: (1 - k) * 0.5,
            }}
          />
        )
      })}
    </div>
  )
}

/* ---------------------------------------------------------- thought shapes */

type ThoughtKind = "question" | "heart" | "anger"

interface ThoughtSpec {
  kind: ThoughtKind
  /** where it orbits, seconds */
  start: number
  phase: number
  radius: number
  size: number
}

const THOUGHTS: ThoughtSpec[] = [
  { kind: "question", start: 5.0, phase: 0.6, radius: 1.15, size: 260 },
  { kind: "heart", start: 5.4, phase: 2.6, radius: 1.35, size: 195 },
  { kind: "anger", start: 5.8, phase: 4.5, radius: 0.95, size: 205 },
]

const IconHeart: React.FC<{ color: string; size: number; cracked: string }> = ({ color, size, cracked }) => (
  <svg width={size} height={size} viewBox="0 0 100 100">
    <path
      d="M50 86 L22 60 A17 17 0 0 1 50 34 A17 17 0 0 1 78 60 Z"
      fill={color}
      stroke={cracked}
      strokeWidth="3"
      strokeLinejoin="round"
    />
    {/* the crack: a broken heart reads at a glance, a plain heart does not */}
    <path d="M50 34 L44 48 L54 56 L46 70" fill="none" stroke={cracked} strokeWidth="4" strokeLinecap="round" />
  </svg>
)

const IconAnger: React.FC<{ color: string; size: number; stroke: string }> = ({ color, size, stroke }) => (
  <svg width={size} height={size} viewBox="0 0 100 100">
    <circle cx="50" cy="52" r="30" fill={color} />
    {/* furrowed brows */}
    <path d="M30 42 L44 48" stroke={stroke} strokeWidth="5" strokeLinecap="round" />
    <path d="M70 42 L56 48" stroke={stroke} strokeWidth="5" strokeLinecap="round" />
    {/* eyes */}
    <circle cx="40" cy="55" r="3.4" fill={stroke} />
    <circle cx="60" cy="55" r="3.4" fill={stroke} />
    {/* frown */}
    <path d="M41 70 Q50 63 59 70" stroke={stroke} strokeWidth="4.4" fill="none" strokeLinecap="round" />
  </svg>
)

const ThoughtLayer: React.FC<{ pal: EliPalette; pose: EliV2Pose; camera: [number, number, number] }> = ({
  pal,
  pose,
  camera,
}) => {
  const frame = useCurrentFrame()
  const t = frame / 30
  const cam = { position: camera, pitch: CAMERA2.pitch, fov: CAMERA2.fov }

  const head = projectToFrame(
    [-0.02 + pose.enterX + pose.jitterX, 0.85 + pose.float + pose.jitterY + pose.enterY, 1.1],
    cam,
    W2,
    H2,
  )

  const settle = mix(frame, [7.6 * 30, 8.6 * 30], [0, 1], easeInOut)

  return (
    <>
      {THOUGHTS.map((spec, i) => {
        const startFrame = spec.start * 30
        const birth = clamp01((frame - startFrame) / 16)
        if (birth <= 0) return null
        const pop = easeOutBack(clamp01((frame - startFrame) / 14))

        // orbit around the head, in screen space, driven by the frame number
        const angle = spec.phase + t * 1.15 - settle * 0.5
        const rx = (spec.radius * 300 + Math.sin(t * 0.9 + i) * 16) * (1 - settle * 0.2)
        const ry = (spec.radius * 205 + Math.cos(t * 1.1 + i) * 14) * (1 - settle * 0.2)

        // tidy final arrangement: a wide arc above the head, never on the face
        const settled = [
          { x: -300, y: -230 },
          { x: 4, y: -300 },
          { x: 300, y: -215 },
        ][i]
        const orbitX = Math.cos(angle) * rx
        const orbitY = Math.sin(angle) * ry - 120
        let cx = head.x + orbitX * (1 - settle) + settled.x * settle
        let cy = head.y + orbitY * (1 - settle) + settled.y * settle

        // keep-out: never let an icon cover Eli's eyes/mouth
        const keepX = 300, keepY = 250
        const dx = cx - head.x
        const dy = cy - (head.y + 40)
        const inside = (dx / keepX) ** 2 + (dy / keepY) ** 2 < 1
        if (inside) {
          const k = 1 / Math.sqrt((dx / keepX) ** 2 + (dy / keepY) ** 2 || 1)
          cx = head.x + dx * Math.max(k, 1.05)
          cy = head.y + 40 + dy * Math.max(k, 1.05)
        }

        const x = cx - spec.size / 2
        const y = cy - spec.size / 2

        const wobble = Math.sin(t * 3 + i) * (0.06 + pose.worried * 0.08)
        const fade = 1 - clamp01((frame - 8.9 * 30) / 22) * 0.55

        const content =
          spec.kind === "question" ? (
            <div
              style={{
                fontFamily: FONT,
                fontWeight: 700,
                fontSize: spec.size * 0.95,
                lineHeight: 1,
                color: pal.accent,
                textShadow: `0 ${spec.size * 0.045}px 0 ${pal.eliDeepShade}, 0 0 ${spec.size * 0.2}px rgba(0,0,0,0.35)`,
              }}
            >
              ؟
            </div>
          ) : spec.kind === "heart" ? (
            <IconHeart color={pal.thoughtWorried} size={spec.size} cracked={pal.eliDeepShade} />
          ) : (
            <IconAnger color={pal.accent} size={spec.size} stroke={pal.eliDeepShade} />
          )

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x,
              top: y,
              width: spec.size,
              height: spec.size,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              opacity: birth * fade,
              transform: `scale(${pop}) rotate(${wobble + Math.sin(angle) * 0.08}rad)`,
              filter: `drop-shadow(0 ${spec.size * 0.05}px ${spec.size * 0.08}px rgba(0,0,0,0.35))`,
            }}
          >
            {content}
          </div>
        )
      })}
    </>
  )
}

/* ---------------------------------------------------------------- layer */

export const Overlays2: React.FC<{
  pal: EliPalette
  pose: EliV2Pose
  camera: [number, number, number]
}> = ({ pal, pose, camera }) => {
  useVazirmatn()
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <ThoughtLayer pal={pal} pose={pose} camera={camera} />
      <PhoneBubble pal={pal} pose={pose} camera={camera} />
    </AbsoluteFill>
  )
}
