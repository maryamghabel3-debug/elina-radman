import { ComponentType, ReactNode } from "react"
import {
  useCurrentFrame,
  interpolate,
  HtmlInCanvas,
} from "remotion"

import timeline from "../../../content/style_test/timeline.json"

export const W = 1080
export const H = 1920
export const FPS = 30
export const DURATION_S = 40

// ---------- design tokens (dark-glass grammar) ----------
const BG_START = "#050508"
const BG_END = "#101116"
const ORANGE = "#d97757"
const GLASS = "rgba(46,41,42,0.55)"
const GLASS_BORDER = "rgba(255,255,255,0.10)"
const PANEL_RADIUS = 44
const SILVER = "#a7acb8"
const SUB_FILL = "#a5aeb5"

type PhraseEvent = (typeof timeline)["stems"][number]["events"][number]
type WordEvent = PhraseEvent["words"][number]

// flat, ordered list of every phrase/word beat
const events: PhraseEvent[] = timeline.stems.flatMap((s) => s.events)

const frameFor = (t: number) => t * FPS
const inFrames = 12 // 0.4s fade-in
const outFrames = 12 // 0.4s fade-out

type Anim = { inProgress: number; outProgress: number; opacity: number }

function eventAnim(frame: number, ev: PhraseEvent): Anim {
  const start = frameFor(ev.t)
  const end = frameFor(ev.end)
  const inProgress = Math.max(0, Math.min(1, (frame - start) / inFrames))
  const outProgress = Math.max(
    0,
    Math.min(1, (frame - (end - outFrames)) / outFrames)
  )
  return { inProgress, outProgress, opacity: inProgress * (1 - outProgress) }
}

type WordAnim = { opacity: number; scale: number }

function wordAnim(frame: number, w: WordEvent): WordAnim {
  const start = frameFor(w.t)
  const end = frameFor(w.end)
  const inProg = Math.max(0, Math.min(1, (frame - start) / 10))
  const outProg = Math.max(0, Math.min(1, (frame - (end - 10)) / 10))
  const base = inProg * (1 - outProg)
  let scale = 1
  if (w.is_key) {
    const stamp = Math.max(0, Math.min(1, (frame - start) / 8))
    scale = 0.4 + 0.85 * stamp * (2 - stamp) // pop 0 -> 1.25 -> ~1.0
    scale *= base
  }
  return { opacity: base, scale }
}

// ---------- style helpers (camelCase for inline styles) ----------

const st = (obj: Record<string, any>): React.CSSProperties => obj as any

// ---------- layers ----------

const Bloom = () => {
  const frame = useCurrentFrame()
  const breath = Math.sin((frame / FPS) * 0.8) * 0.06 + 0.10
  return (
    <div
      style={st({
        position: "absolute",
        inset: 0,
        background: `radial-gradient(600px 900px at 50% 30%, rgba(217,119,87,${breath}) 0%, transparent 60%)`,
        pointerEvents: "none",
      })}
    />
  )
}

const FloorGrid = () => {
  const frame = useCurrentFrame()
  const drift = interpolate(frame, [0, DURATION_S * FPS], [0, 120])
  return (
    <div
      style={st({
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        pointerEvents: "none",
        background: `linear-gradient(#1a1c24 1px, transparent 1px),
                     linear-gradient(90deg, #1a1c24 1px, transparent 1px)`,
        backgroundSize: "64px 64px",
        backgroundPosition: `${drift}px ${drift * 0.6}px`,
        transform: `perspective(900px) rotateX(65deg) scale(1.6)`,
        transformOrigin: "bottom center",
        opacity: 0.35,
      })}
    />
  )
}

const BackgroundLayer = () => (
  <div
    style={st({
      position: "absolute",
      inset: 0,
      background: `linear-gradient(180deg, ${BG_START}, ${BG_END})`,
    })}
  >
    <Bloom />
    <FloorGrid />
  </div>
)

// ---------- glass panel (content-hugging) ----------

type GlassPanelProps = {
  children: ReactNode
  x?: number
  y?: number
  opacity?: number
}
const GlassPanel: ComponentType<GlassPanelProps> = ({
  children,
  x,
  y,
  opacity,
}) => (
  <div
    style={st({
      position: "absolute",
      left: x ?? 0,
      top: y ?? 0,
      display: "inline-flex",
      flexDirection: "column",
      alignItems: "center",
      gap: 10,
      padding: 24,
      borderRadius: PANEL_RADIUS,
      background: GLASS,
      border: `1px solid ${GLASS_BORDER}`,
      boxShadow: "0 24px 48px rgba(0,0,0,0.45)",
      backdropFilter: "blur(16px) saturate(1.2)",
      WebkitBackdropFilter: "blur(16px) saturate(1.2)",
      opacity: opacity ?? 1,
    })}
  >
    {children}
  </div>
)

// ---------- text ----------

type TextProps = {
  children: string
  size: number
  weight?: number
  color?: string
  align?: "center" | "start" | "end"
  italic?: boolean
  opacity?: number
  gradient?: boolean
}
const PersianText: ComponentType<TextProps> = ({
  children,
  size,
  weight = 700,
  color,
  align = "center",
  italic,
  opacity,
  gradient,
}) => (
  <span
    dir="rtl"
    lang="fa"
    style={st({
      fontFamily: "Vazirmatn, system-ui",
      fontSize: size,
      fontWeight: weight,
      fontStyle: italic ? "italic" : "normal",
      color: gradient ? "transparent" : color,
      textAlign: align,
      opacity: opacity ?? 1,
      direction: "rtl",
      whiteSpace: "pre-wrap",
      lineHeight: 1.35,
      letterSpacing: 0.2,
      ...(gradient
        ? {
            background:
              "linear-gradient(135deg, #e8e8ea 0%, #c9cfd6 35%, #ffffff 55%, #a7acb8 85%)",
            WebkitBackgroundClip: "text",
            backgroundClip: "text",
          }
        : {}),
    })}
  >
    {children}
  </span>
)

// ---------- icons (self-drawing SVG) ----------

const StrokeIcon: ComponentType<{
  path: string
  size?: number
  color?: string
  frame: number
  startFrame: number
  duration?: number
}> = ({ path, size = 40, color = ORANGE, frame, startFrame, duration = 24 }) => {
  const dash = Math.min(1, Math.max(0, (frame - startFrame) / duration))
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={st({
        opacity: Math.min(1, dash * 1.5),
        filter: `drop-shadow(0 0 8px ${color}80)`,
        transition: "opacity 0.2s ease",
      })}
    >
      <path
        d={path}
        strokeDasharray="96"
        strokeDashoffset={96 * (1 - dash)}
        style={{ transition: "stroke-dashoffset 0.4s ease" }}
      />
    </svg>
  )
}

const icons: Record<string, string> = {
  phone: "M15 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zM3 10h1M7 10h1m12 10h1m-9-4H3m18 0h-1M5 5L3 3m0 0L3 3m18 12L21 15m0 0L21 15",
  chat: "M17 20h1v-6a3 3 0 0 0-3-3H8a3 3 0 0 0-3 3v3m0 0v-3m3 3h1",
  head: "M12 2C7 2 4.8 5.2 4.8 9.2c0 3.2 2 5.8 4.8 6.8 2.8-1 4.8-3.6 4.8-6.8C19.2 5.2 17 2 12 2ZM9 12c0 2.8 2.2 5 5 5s5-2.2 5-5",
  magnifier: "M21 21l-6-6m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0Z",
  question: "M13 2h3a1 1 0 0 1 1 1v1h-1a2 2 0 0 0-2-2H9a2 2 0 0 0-2 2v1a2 2 0 0 0 2 2h1v1a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1h-1a1 1 0 0 0-1-1v-1a1 1 0 0 1 1-1z",
  check: "M20 6L9 17l-5-5",
  cross: "M18 6L6 18M6 6l12 12",
}

// ---------- beats renderer ----------

const PhraseBeat: ComponentType<{ frame: number; ev: PhraseEvent }> = ({
  frame,
  ev,
}) => {
  const anim = eventAnim(frame, ev)
  if (anim.opacity <= 0.01) return null
  const isWeak = !!ev.weakRegionPhrase || ev.reliability !== "high"

  return (
    <GlassPanel
      x={W / 2 - 420}
      y={interpolate(frame, [0, DURATION_S * FPS], [1120, 1180])}
      opacity={anim.opacity}
    >
      <div
        style={st({
          transform: `translateY(${20 * (1 - anim.inProgress)}px) scale(${0.92 + 0.08 * anim.inProgress})`,
          transition: "opacity 0.4s ease, transform 0.4s ease",
        })}
      >
        {isWeak ? (
          // weak region: phrase-level panel only, no word stamps
          <PersianText size={40} color="#e8e8ea" opacity={anim.opacity}>
            {ev.text}
          </PersianText>
        ) : (
          ev.words.map((w, i) => {
            const wa = wordAnim(frame, w)
            if (wa.opacity <= 0.01) return null
            return (
              <div
                key={i}
                style={st({
                  display: "inline-block",
                  margin: "0 7px",
                  opacity: wa.opacity,
                  transform: `scale(${wa.scale})`,
                  transition: "all 0.25s ease",
                })}
              >
                {w.is_key ? (
                  <PersianText
                    size={52}
                    color="#e8e8ea"
                    opacity={wa.opacity}
                    gradient
                  >
                    {w.text}
                  </PersianText>
                ) : (
                  <PersianText
                    size={34}
                    color="#c9cfd6"
                    opacity={wa.opacity}
                  >
                    {w.text}
                  </PersianText>
                )}
              </div>
            )
          })
        )}
      </div>
    </GlassPanel>
  )
}

const Subtitle = () => {
  const frame = useCurrentFrame()
  const ev = events.find((e) => frame >= frameFor(e.t) && frame <= frameFor(e.end))
  return (
    <div
      style={st({
        position: "absolute",
        left: 0,
        right: 0,
        top: 1480,
        display: "flex",
        justifyContent: "center",
        pointerEvents: "none",
      })}
    >
      {ev ? (
        <PersianText size={22} color={SUB_FILL} align="center" italic>
          {ev.text}
        </PersianText>
      ) : (
        <PersianText size={22} color="#6b727a" align="center" italic>
          psychology style test
        </PersianText>
      )}
    </div>
  )
}

const ProgressBar = () => {
  const frame = useCurrentFrame()
  const total = DURATION_S * FPS
  const pct = Math.max(0, Math.min(100, (frame / total) * 100))
  return (
    <div
      style={st({
        position: "absolute",
        left: W * 0.06,
        right: W * 0.06,
        bottom: 60,
        height: 6,
        background: "rgba(255,255,255,0.08)",
        borderRadius: 3,
        overflow: "hidden",
      })}
    >
      <div
        style={st({
          position: "absolute",
          right: 0,
          top: 0,
          bottom: 0,
          width: `${pct}%`,
          background: ORANGE,
          borderRadius: 3,
          transition: "width 0.2s linear",
        })}
      />
      {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => (
        <div
          key={i}
          style={st({
            position: "absolute",
            left: `${(i / 9) * 100}%`,
            top: "-6px",
            width: 14,
            height: 14,
            borderRadius: 50,
            background: i / 9 <= pct / 100 ? ORANGE : "rgba(255,255,255,0.10)",
            border: `1px solid rgba(255,255,255,0.12)`,
          })}
        />
      ))}
    </div>
  )
}

const TopRightDot = () => (
  <div
    style={st({
      position: "absolute",
      top: 40,
      right: 40,
      width: 10,
      height: 10,
      borderRadius: 50,
      background: ORANGE,
      boxShadow: `0 0 16px ${ORANGE}`,
    })}
  />
)

// ---------- scene rendered inside the composition ----------

export const Scene: ComponentType = () => {
  const frame = useCurrentFrame()

  return (
    <HtmlInCanvas width={W} height={H} durationInFrames={DURATION_S * FPS}>
      <BackgroundLayer />
      <TopRightDot />
      <FloorGrid />
      {events.map((ev, i) => (
        <PhraseBeat key={i} frame={frame} ev={ev} />
      ))}
      <Subtitle />
      <ProgressBar />
    </HtmlInCanvas>
  )
}
