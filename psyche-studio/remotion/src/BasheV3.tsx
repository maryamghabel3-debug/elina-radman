import { ComponentType, ReactNode } from "react"
import {
  useCurrentFrame,
  interpolate,
  HtmlInCanvas,
  Audio,
  staticFile,
} from "remotion"

import timeline from "./data/timeline.json"

export const W = 1080
export const H = 1920
export const FPS = 30
export const DURATION_S = 40

// ---------- design tokens (overhauled dark-glass) ----------
const BG_START = "#0B0B12"
const BG_END = "#16161F"
const ORANGE = "#d97757"
const HEADLINE_COLOR = "#F5F0E8"
const KEY_COLOR_1 = "#FFB169" // mustard/gold
const KEY_COLOR_2 = "#FF8A5C" // coral
const NEGATIVE_TINT = "#FF6B6B" // coral/red for negative thoughts
const SUB_FILL = "#FFFFFF"
const CHIP_BG = "rgba(255,255,255,0.05)"
const CHIP_BORDER = "rgba(255,255,255,0.12)"
const GLASS = "rgba(14, 14, 20, 0.80)"
const GLASS_BORDER = "rgba(255,255,255,0.10)"
const PHONE_W = 660
const PHONE_H = 1000

// ---------- timeline ----------
type AnyWord = { t: number; end?: number; text: string; role?: string | null; reliability?: string; is_key?: boolean; [key: string]: unknown }
type AnyEvent = { t: number; end?: number; text: string; role?: string | null; reliability?: string; is_key?: boolean; word_level_impact_allowed?: boolean; words?: AnyWord[]; [key: string]: unknown }

const allEvents: AnyEvent[] = (timeline as any).stems.flatMap((s: any) => s.events ?? [])

// Only content events (with text + end) drive visible beats
const contentEvents: AnyEvent[] = allEvents.filter((e) => e.text && e.end)

const frameFor = (t: number) => t * FPS

// ---------- style helpers ----------
const st = (obj: Record<string, any>): React.CSSProperties => obj as any

// ---------- animation helpers ----------

// Gentle float: continuous idle motion so nothing is ever perfectly still
function floatY(frame: number, offset: number, speed: number = 0.5, amp: number = 14): number {
  return Math.sin((frame / FPS) * speed + offset) * amp
}

function breath(frame: number, speed: number = 0.7): number {
  return Math.sin((frame / FPS) * speed) * 0.03 + 1.0
}

// ---------- get active event ----------
function getActiveEvent(frame: number): AnyEvent | null {
  return (
    contentEvents.find(
      (e) => frame >= frameFor(e.t) && frame <= frameFor(e.end ?? e.t + 4)
    ) || null
  )
}

// Get active key words (only from high-reliability events where wlia is allowed)
function getKeyWords(frame: number): AnyWord[] {
  const ev = getActiveEvent(frame)
  if (!ev) return []
  return (ev.words || []).filter(
    (w: AnyWord) =>
      w.is_key &&
      ev.word_level_impact_allowed !== false &&
      ev.reliability === "high"
  )
}

// ---------- background layers ----------

const Bloom = () => {
  const frame = useCurrentFrame()
  const breath = Math.sin((frame / FPS) * 0.6) * 0.05 + 0.10
  return (
    <div
      style={st({
        position: "absolute",
        inset: 0,
        background: `radial-gradient(700px 1000px at 50% 35%, rgba(217,119,87,${breath}) 0%, transparent 55%)`,
        pointerEvents: "none",
      })}
    />
  )
}

const FloorGrid = () => {
  const frame = useCurrentFrame()
  const drift = interpolate(frame, [0, DURATION_S * FPS], [0, 100])
  return (
    <div
      style={st({
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        pointerEvents: "none",
        background: `linear-gradient(#232330 1px, transparent 1px),
                     linear-gradient(90deg, #232330 1px, transparent 1px)`,
        backgroundSize: "72px 72px",
        backgroundPosition: `${drift}px ${drift * 0.5}px`,
        transform: `perspective(1000px) rotateX(60deg) scale(1.7)`,
        transformOrigin: "bottom center",
        opacity: 0.25,
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

// ---------- top-right dot (chrome) ----------

const TopRightDot = () => (
  <div
    style={st({
      position: "absolute",
      top: 40,
      right: 40,
      width: 12,
      height: 12,
      borderRadius: 50,
      background: ORANGE,
      boxShadow: `0 0 20px ${ORANGE}`,
      opacity: breath(useCurrentFrame()) > 1 ? 0.9 : 1,
    })}
  />
)

// ---------- RTL progress bar (bottom) ----------

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
        bottom: 64,
        height: 7,
        background: "rgba(255,255,255,0.06)",
        borderRadius: 4,
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
          borderRadius: 4,
          transition: "width 0.15s linear",
        })}
      />
      {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => (
        <div
          key={i}
          style={st({
            position: "absolute",
            left: `${(i / 9) * 100}%`,
            top: "-7px",
            width: 16,
            height: 16,
            borderRadius: 50,
            background: i / 9 <= pct / 100 ? ORANGE : "rgba(255,255,255,0.10)",
            border: `1px solid rgba(255,255,255,0.12)`,
          })}
        />
      ))}
    </div>
  )
}

// ---------- subtitle (always visible, y≈1480) ----------

const Subtitle = () => {
  const frame = useCurrentFrame()
  const ev = getActiveEvent(frame)
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
      <span
        dir="rtl"
        lang="fa"
        style={st({
          fontFamily: "Vazirmatn, system-ui",
          fontSize: 56,
          fontWeight: 700,
          color: SUB_FILL,
          opacity: 0.95,
          textAlign: "center",
          direction: "rtl",
          whiteSpace: "pre-wrap",
          lineHeight: 1.3,
          textShadow: "0 4px 24px rgba(0,0,0,0.7)",
        })}
      >
        {ev ? ev.text : "bashe"}
      </span>
    </div>
  )
}

// ---------- headline (beat text, y 560-760) ----------

const Headline = () => {
  const frame = useCurrentFrame()
  const ev = getActiveEvent(frame)
  if (!ev) return null
  return (
    <div
      style={st({
        position: "absolute",
        left: W * 0.04,
        right: W * 0.04,
        top: 620,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        pointerEvents: "none",
      })}
    >
      <span
        dir="rtl"
        lang="fa"
        style={st({
          fontFamily: "Vazirmatn, system-ui",
          fontWeight: 900,
          fontSize: 110,
          color: HEADLINE_COLOR,
          textAlign: "center",
          direction: "rtl",
          whiteSpace: "pre-wrap",
          lineHeight: 1.15,
          maxWidth: W * 0.92,
          textShadow: "0 4px 32px rgba(0,0,0,0.65)",
        })}
      >
        {ev.text}
      </span>
    </div>
  )
}

// ---------- key-word stamps (large, solid color, scale pop) ----------

type KeyStampProps = { word: AnyWord; frame: number; index: number }

const KeyStamp: ComponentType<KeyStampProps> = ({ word, frame, index }) => {
  const start = frameFor(word.t)
  const end = frameFor(word.end != null ? word.end : word.t + 1.5)
  const inProg = Math.max(0, Math.min(1, (frame - start) / 10))
  const outProg = Math.max(0, Math.min(1, (frame - (end - 10)) / 10))
  const base = inProg * (1 - outProg)
  if (base <= 0.01) return null

  // scale pop 1.35 -> 1.0 with overshoot
  const stamp = Math.max(0, Math.min(1, (frame - start) / 8))
  const popScale = 1 + 0.35 * stamp * (2 - stamp) // 1 -> 1.35 -> ~1.0
  const scale = popScale * base

  // position stamps in a vertical stack above the headline area
  const y = 320 + index * 170
  const color = index % 2 === 0 ? KEY_COLOR_1 : KEY_COLOR_2

  return (
    <div
      style={st({
        position: "absolute",
        left: W * 0.08,
        right: W * 0.08,
        top: y,
        opacity: base,
        transform: `scale(${scale})`,
        transition: "all 0.2s ease",
        pointerEvents: "none",
      })}
    >
      <span
        dir="rtl"
        lang="fa"
        style={st({
          fontFamily: "Vazirmatn, system-ui",
          fontWeight: 900,
          fontSize: 160,
          color,
          textAlign: "center",
          direction: "rtl",
          whiteSpace: "pre-wrap",
          lineHeight: 1.1,
          textShadow: `0 4px 28px ${color}40, 0 4px 32px rgba(0,0,0,0.7)`,
        })}
      >
        {word.text}
      </span>
    </div>
  )
}

// ---------- phone mockup (hero, centered, dark glass) ----------

type PhoneProps = { frame: number }

const PhoneMockup: ComponentType<PhoneProps> = ({ frame }) => {
  const fy = floatY(frame, 0, 0.4, 10)
  const bx = breath(frame, 0.3)
  const x = (W - PHONE_W) / 2
  const y = 520 + fy

  return (
    <div
      style={st({
        position: "absolute",
        left: x,
        top: y,
        width: PHONE_W,
        height: PHONE_H,
        borderRadius: 52,
        background: GLASS,
        border: `1.5px solid ${GLASS_BORDER}`,
        boxShadow: "0 32px 80px rgba(0,0,0,0.55), inset 0 0 40px rgba(255,255,255,0.03)",
        backdropFilter: "blur(24px) saturate(1.1)",
        WebkitBackdropFilter: "blur(24px) saturate(1.1)",
        transform: `scale(${bx})`,
        transition: "transform 0.15s ease",
        overflow: "hidden",
      })}
    >
      {/* phone inner screen */}
      <div
        style={st({
          position: "absolute",
          left: 30,
          top: 40,
          right: 30,
          bottom: 40,
          background: "#050508",
          borderRadius: 40,
          overflow: "hidden",
        })}
      >
        {/* notch area */}
        <div
          style={st({
            position: "absolute",
            left: "50%",
            top: 20,
            width: 160,
            height: 24,
            background: "#050508",
            borderRadius: "0 0 16 16",
            transform: "translateX(-50%)",
          })}
        />
        {/* status dots */}
        <div style={st({ position: "absolute", top: 24, left: 40, right: 40, display: "flex", justifyContent: "center", gap: 8 })}>
          {[0, 1, 2].map((i) => (
            <div key={i} style={st({ width: 8, height: 8, borderRadius: 50, background: "rgba(255,255,255,0.25)" })} />
          ))}
        </div>

        {/* chat bubble with «باشه» */}
        <div
          style={st({
            position: "absolute",
            left: 60,
            right: 60,
            top: PHONE_H / 2 - 120,
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
          })}
        >
          <span
            dir="rtl"
            lang="fa"
            style={st({
              fontFamily: "Vazirmatn, system-ui",
              fontWeight: 900,
              fontSize: 96,
              color: "#FFFFFF",
              textAlign: "center",
              direction: "rtl",
              background: KEY_COLOR_2,
              paddingLeft: 40,
              paddingRight: 40,
              paddingTop: 24,
              paddingBottom: 24,
              borderRadius: 36,
              boxShadow: `0 8px 32px ${KEY_COLOR_2}50, 0 4px 24px rgba(0,0,0,0.6)`,
              whiteSpace: "pre-wrap",
              lineHeight: 1.1,
            })}
          >
            باشه
          </span>
        </div>
      </div>
    </div>
  )
}

// ---------- thought chips ----------

type ChipProps = { frame: number; index: number }

const ThoughtChip: ComponentType<ChipProps> = ({ frame, index }) => {
  // Positions around the center band (y 300-1400)
  const positions = [
    { x: 40, y: 320, neg: false },
    { x: 360, y: 320, neg: true },
    { x: 40, y: 760, neg: true },
    { x: 360, y: 760, neg: false },
    { x: 40, y: 1200, neg: false },
    { x: 360, y: 1200, neg: true },
  ]
  const pos = positions[index]
  if (!pos) return null

  const fy = floatY(frame, index * 1.1, 0.35, 12)
  const bx = breath(frame, 0.4 + index * 0.1)
  const x = pos.x
  const y = pos.y + fy

  const tint = pos.neg ? NEGATIVE_TINT : ORANGE
  const chipBg = pos.neg ? "rgba(255,107,107,0.10)" : CHIP_BG
  const chipBorder = pos.neg ? "rgba(255,107,107,0.30)" : CHIP_BORDER

  // Staggered entrance: each chip fades in at a different time
  const startFrame = index * 25
  const inProg = Math.max(0, Math.min(1, (frame - startFrame) / 30))
  const opacity = inProg
  if (opacity <= 0.01) return null

  const texts = [
    "فکرهای من چیه؟",
    "باشه. responding",
    "واقعیت رو تفکیک کنیم",
    "من چی می‌خوام؟",
    "حالت چیه؟",
    "بلاکش کنم",
  ]

  return (
    <div
      style={st({
        position: "absolute",
        left: x,
        top: y,
        width: 680,
        height: 160,
        borderRadius: 44,
        background: chipBg,
        border: `1px solid ${chipBorder}`,
        boxShadow: pos.neg
          ? `0 16px 40px rgba(255,107,107,0.25), inset 0 0 20px rgba(255,255,255,0.02)`
          : `0 16px 40px rgba(0,0,0,0.35), inset 0 0 20px rgba(255,255,255,0.02)`,
        backdropFilter: "blur(16px) saturate(1.0)",
        WebkitBackdropFilter: "blur(16px) saturate(1.0)",
        opacity,
        transform: `scale(${0.85 + 0.15 * inProg}) * ${bx}`,
        transformOrigin: "center center",
        transition: "all 0.3s ease",
        overflow: "hidden",
      })}
    >
      {/* negative badge */}
      {pos.neg && (
        <div
          style={st({
            position: "absolute",
            top: -10,
            right: -10,
            width: 34,
            height: 34,
            borderRadius: 50,
            background: NEGATIVE_TINT,
            border: `2px solid #16161F`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          })}
        >
          <span
            dir="rtl"
            lang="fa"
            style={st({
              fontFamily: "Vazirmatn, system-ui",
              fontWeight: 900,
              fontSize: 20,
              color: "#FFFFFF",
            })}
          >
            ؟
          </span>
        </div>
      )}
      <span
        dir="rtl"
        lang="fa"
        style={st({
          fontFamily: "Vazirmatn, system-ui",
          fontWeight: 700,
          fontSize: 60,
          color: pos.neg ? "#FFB3A7" : "#F5F0E8",
          textAlign: "center",
          direction: "rtl",
          whiteSpace: "pre-wrap",
          lineHeight: 1.2,
          paddingLeft: 40,
          paddingRight: 40,
          paddingTop: 20,
          paddingBottom: 20,
          textShadow: "0 2px 16px rgba(0,0,0,0.5)",
        })}
      >
        {texts[index]}
      </span>
    </div>
  )
}

const ThoughtChips: ComponentType<{ frame: number }> = ({ frame }) => (
  <div style={st({ position: "absolute", inset: 0, pointerEvents: "none" })}>
    {[0, 1, 2, 3, 4, 5].map((i) => (
      <ThoughtChip key={i} frame={frame} index={i} />
    ))}
  </div>
)

// ---------- connector curves (thin SVG lines) ----------

const ConnectorCurves = () => {
  const frame = useCurrentFrame()
  const drift = Math.sin((frame / FPS) * 0.4) * 8
  return (
    <div
      style={st({
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
      })}
    >
      <svg width={W} height={H} style={st({ display: "block" })}>
        {/* curve from phone top to top-left chip */}
        <path
          d={`M 540 540 Q 200 420 ${100 + drift} 340`}
          stroke="rgba(255,255,255,0.12)"
          strokeWidth="2"
          fill="none"
        />
        {/* curve from phone top to top-right chip */}
        <path
          d={`M 540 540 Q 880 420 ${980 - drift} 340`}
          stroke="rgba(255,255,255,0.10)"
          strokeWidth="2"
          fill="none"
        />
        {/* curve from phone side to mid-left chip */}
        <path
          d={`M 340 800 Q 180 800 ${80} 760`}
          stroke="rgba(255,255,255,0.10)"
          strokeWidth="2"
          fill="none"
        />
        {/* curve from phone side to mid-right chip */}
        <path
          d={`M 740 800 Q 900 800 ${1000} 760`}
          stroke="rgba(255,255,255,0.10)"
          strokeWidth="2"
          fill="none"
        />
      </svg>
    </div>
  )
}

// ---------- main scene ----------

export const Scene: ComponentType = () => {
  const frame = useCurrentFrame()

  const keyWords = getKeyWords(frame)

  return (
    <HtmlInCanvas width={W} height={H} durationInFrames={DURATION_S * FPS}>
      <Audio src={staticFile("full_voice_cleaned.mp3")} />
      <BackgroundLayer />
      <TopRightDot />
      <FloorGrid />
      <ConnectorCurves />
      <ThoughtChips frame={frame} />
      <PhoneMockup frame={frame} />
      <Headline />
      {keyWords.map((w, i) => (
        <KeyStamp key={i} word={w} frame={frame} index={i} />
      ))}
      <Subtitle />
      <ProgressBar />
    </HtmlInCanvas>
  )
}
