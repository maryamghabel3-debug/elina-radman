import { useCurrentFrame } from "remotion"
import { useMemo } from "react"
import { CatmullRomCurve3, TubeGeometry, Vector3 } from "three"
import { PALETTE as P } from "./palette"
import { TIMELINE, easeInOut, mix } from "./timeline"
import { eliPose } from "./eliPose"

/**
 * VERSION B — Eli as flowing luminous lines.
 *
 * The body is a small, fixed set of neon ribbons, drawn like a signature:
 *
 *   head   – one closed oval that carries the face (the anchor)
 *   crown  – a bright arch across the top of the head: silhouette signature
 *   body   – a single ribbon that loops into a rounded torso
 *   arms   – two arcs from the torso that lift toward the phone
 *   tails  – three ribbons streaming behind, to read as "mind in motion"
 *
 * Colours are the same family as the cloud version — peach head, coral body,
 * lavender crown, sky-blue tails — so the comparison is about form, not hue.
 *
 * Deliberately low ribbon count: it must read as a character, not a
 * screensaver.
 */

const CROWN = "#C9A8F5"
const HEAD = "#FF9E6E"
const BODY = "#FF8F7E"
const TAIL = "#63C6F2"
const ACCENT = "#FFD680"

const vec = (p: [number, number, number]) => new Vector3(p[0], p[1], p[2])

/** deterministic tube: the same points + radius always produce the same mesh */
const useTube = (
  points: [number, number, number][],
  radius: number,
  closed: boolean,
  segments: number,
) =>
  useMemo(() => {
    const curve = new CatmullRomCurve3(points.map(vec), closed, "catmullrom", 0.5)
    return new TubeGeometry(curve, segments, radius, 8, closed)
  }, [JSON.stringify(points), radius, closed, segments])

const GlowMaterial: React.FC<{ color: string; power?: number }> = ({ color, power = 1 }) => (
  <meshStandardMaterial
    color={color}
    emissive={color}
    emissiveIntensity={0.42 * power}
    roughness={0.3}
    metalness={0}
    toneMapped={false}
  />
)

/** ring of points; `wobble` adds a slow wave so the line feels alive */
const ring = (
  cx: number,
  cy: number,
  cz: number,
  rx: number,
  ry: number,
  n: number,
  wobble: number,
  phase: number,
): [number, number, number][] =>
  Array.from({ length: n }, (_, i) => {
    const a = (i / n) * Math.PI * 2
    const w = Math.sin(a * 2 + phase) * wobble
    return [
      cx + Math.cos(a) * (rx + w),
      cy + Math.sin(a) * (ry + w),
      cz + Math.sin(a + phase) * wobble * 1.4,
    ]
  })

/* ------------------------------------------------------------- pieces */

const HeadLoop: React.FC<{ t: number; breathe: number }> = ({ t, breathe }) => {
  const geo = useTube(
    ring(0, 0.62, 0.04, 0.42 * breathe, 0.36 * breathe, 28, 0.008, t * 0.7),
    0.027,
    true,
    132,
  )
  return (
    <mesh geometry={geo}>
      <GlowMaterial color={HEAD} power={1.15} />
    </mesh>
  )
}

const CrownArch: React.FC<{ t: number }> = ({ t }) => {
  const pts = useMemo(() => {
    const n = 20
    return Array.from({ length: n }, (_, i) => {
      const u = i / (n - 1)
      const a = 0.16 + u * (Math.PI - 0.32)
      const r = 0.4
      return [
        -Math.cos(a) * r,
        0.78 + Math.sin(a) * r * 0.92 + Math.sin(t * 1.4 + u * 4) * 0.012,
        0.03 + Math.cos(u * Math.PI) * 0.06,
      ] as [number, number, number]
    })
  }, [Math.round(t * 10)])
  const geo = useTube(pts, 0.024, false, 90)
  return (
    <mesh geometry={geo}>
      <GlowMaterial color={CROWN} power={1.2} />
    </mesh>
  )
}

/** a single ribbon that loops twice to suggest a soft torso */
const TorsoLoop: React.FC<{ t: number; breathe: number }> = ({ t, breathe }) => {
  const pts = useMemo(() => {
    const n = 40
    return Array.from({ length: n }, (_, i) => {
      const a = (i / n) * Math.PI * 2
      // figure-of-eight: reads as a rounded, folded body rather than a circle
      const rx = 0.3 * (1 - 0.16 * Math.sin(a)) * breathe
      const ry = 0.3
      return [
        Math.cos(a) * rx,
        -0.16 + Math.sin(a) * ry,
        0.02 + Math.sin(a * 2) * 0.07,
      ] as [number, number, number]
    })
  }, [Math.round(t * 8), breathe])
  const geo = useTube(pts, 0.028, true, 150)
  return (
    <mesh geometry={geo}>
      <GlowMaterial color={BODY} />
    </mesh>
  )
}

const Arm: React.FC<{ t: number; side: 1 | -1; lift: number }> = ({ t, side, lift }) => {
  const pts = useMemo(() => {
    const n = 14
    return Array.from({ length: n }, (_, i) => {
      const u = i / (n - 1)
      // starts at the shoulder, bends outward, then rises with the reach beat
      const x = side * (0.3 + Math.sin(u * Math.PI * 0.8) * 0.14 + u * 0.16)
      const y = 0.02 - u * 0.06 + u * u * (0.26 + lift * 0.6)
      const z = 0.08 + u * 0.14 + lift * 0.18
      return [x, y + Math.sin(t * 4.2 + u * 2) * 0.012, z] as [number, number, number]
    })
  }, [side, lift, Math.round(t * 12)])
  const geo = useTube(pts, 0.017, false, 70)
  const tip = pts[pts.length - 1]
  return (
    <group>
      <mesh geometry={geo}>
        <GlowMaterial color={ACCENT} power={0.85} />
      </mesh>
      {/* a small glowing hand closes the gesture */}
      <mesh position={[tip[0], tip[1], tip[2]]}>
        <sphereGeometry args={[0.034, 18, 14]} />
        <meshStandardMaterial color={ACCENT} emissive={ACCENT} emissiveIntensity={1.5} toneMapped={false} />
      </mesh>
    </group>
  )
}

const Tail: React.FC<{ t: number; offset: number; speed: number; scale: number }> = ({
  t,
  offset,
  speed,
  scale,
}) => {
  const pts = useMemo(() => {
    const n = 18
    return Array.from({ length: n }, (_, i) => {
      const u = i / (n - 1)
      const wave = Math.sin(u * 2.4 + t * speed + offset) * 0.2 * u
      const curl = Math.sin(u * Math.PI) * 0.18
      return [
        -0.18 - u * 0.7 * scale + curl * 0.6,
        -0.12 + u * 0.16 * scale + wave * 0.75,
        -0.32 - u * 0.34 * scale + Math.cos(u * 2.4 + t * speed * 0.8 + offset) * 0.1,
      ] as [number, number, number]
    })
  }, [Math.round(t * 12), offset, speed, scale])
  const geo = useTube(pts, 0.024, false, 80)
  return (
    <mesh geometry={geo}>
      <GlowMaterial color={TAIL} power={0.9} />
    </mesh>
  )
}

/* -------------------------------------------------------------- face */

const LineFace: React.FC<{
  lookX: number
  lookY: number
  blink: number
  widen: number
  joy: number
}> = ({ lookX, lookY, blink, widen, joy }) => {
  const eyeY = 0.65
  const open = 1 - blink * 0.92
  return (
    <group position={[0, 0, 0.3]}>
      {[-0.155, 0.155].map((x) => (
        <group key={x} position={[x, eyeY, 0]}>
          {/* warm iris disc, drawn bright so it survives the bloom-ish glow */}
          <mesh scale={[0.052 * widen, 0.058 * widen * open, 0.016]} position={[lookX * 0.02, lookY * 0.02, 0.02]}>
            <sphereGeometry args={[1, 24, 18]} />
            <meshStandardMaterial color="#4A3A63" emissive="#4A3A63" emissiveIntensity={0.5} roughness={0.3} toneMapped={false} />
          </mesh>
          <mesh
            scale={[0.02 * widen, 0.021 * widen * open, 0.012]}
            position={[lookX * 0.032 + 0.017, lookY * 0.03 + 0.022, 0.045]}
          >
            <sphereGeometry args={[1, 16, 12]} />
            <meshStandardMaterial color="#FFFFFF" emissive="#FFFFFF" emissiveIntensity={1.8} toneMapped={false} />
          </mesh>
          {/* joy: the eye closes into a smiling crescent */}
          {joy > 0.03 && (
            <mesh scale={[0.055 * joy, 0.05 * joy, 0.014]} position={[0, 0.012, 0.03]} rotation={[0, 0, Math.PI]}>
              <torusGeometry args={[1, 0.24, 10, 26, Math.PI]} />
              <meshStandardMaterial
                color="#4A3A63"
                emissive="#4A3A63"
                emissiveIntensity={0.6}
                transparent
                opacity={Math.min(1, joy * 1.5)}
                toneMapped={false}
              />
            </mesh>
          )}
        </group>
      ))}
      {/* mouth: a small warm arc */}
      <mesh position={[0, eyeY - 0.14, 0.06]} rotation={[0, 0, Math.PI]} scale={[0.045 + joy * 0.018, 0.032, 0.012]}>
        <torusGeometry args={[1, 0.2, 8, 22, Math.PI]} />
        <meshStandardMaterial color="#5A4478" emissive="#5A4478" emissiveIntensity={0.4} toneMapped={false} />
      </mesh>
      {/* cheeks */}
      {[-0.29, 0.29].map((x) => (
        <mesh key={x} position={[x, eyeY - 0.12, 0.05]} rotation={[0, 0, x > 0 ? -0.35 : 0.35]}>
          <torusGeometry args={[0.04, 0.008, 8, 18, Math.PI]} />
          <meshStandardMaterial color="#FFC7B0" emissive="#FFC7B0" emissiveIntensity={0.9} toneMapped={false} />
        </mesh>
      ))}
    </group>
  )
}

/* -------------------------------------------------------------- Eli B */

export interface LinesEliProps {
  phoneLit: number
}

export const LinesEli: React.FC<LinesEliProps> = ({ phoneLit }) => {
  const frame = useCurrentFrame()
  const pose = eliPose(frame)
  const { t, turn, reach, joy, blink, widen, lookX, lookY, float } = pose

  const breathe = 1 + Math.sin(t * 1.9) * 0.045
  const tilt = Math.sin(t * 1.35) * 0.07

  return (
    <group
      position={[-0.3 + pose.enterDriftX, -0.1 + float + pose.enterOffset, 0.8]}
      rotation={[0, 0.18 + turn * 0.24 + tilt, -turn * 0.05]}
    >
      <group scale={1.0}>
        {/* reading order is crown -> head -> body, so the eye finds a face
            first and motion second */}
        <CrownArch t={t} />
        <HeadLoop t={t} breathe={breathe} />
        <TorsoLoop t={t} breathe={breathe} />
        <Arm t={t} side={1} lift={reach} />
        <Arm t={t} side={-1} lift={reach * 0.55} />
        <Tail t={t} offset={0} speed={1.1} scale={1} />
        <Tail t={t} offset={2.1} speed={1.5} scale={0.86} />
        <Tail t={t} offset={4.2} speed={0.9} scale={0.7} />
        <LineFace lookX={lookX} lookY={lookY} blink={blink} widen={widen} joy={joy} />
      </group>

      {/* the lines light the room, and brighten with the phone */}
      <pointLight position={[0, 0.3, 0.5]} color={HEAD} intensity={1.4 + phoneLit * 1.4} distance={2.4} decay={2} />
      <pointLight position={[-0.25, -0.3, 0.35]} color={TAIL} intensity={0.7} distance={1.8} decay={2} />
    </group>
  )
}

/* ------------------------------------------- thought shapes (version B) */

/**
 * The same three thoughts as version A, told in the language of version B:
 * light ribbons that curl, then tighten and settle into a tidy stack.
 */
export const LineThoughts: React.FC = () => {
  const frame = useCurrentFrame()
  const t = frame / TIMELINE.fps

  const settle = mix(frame, [TIMELINE.thoughtsSettle[0] * 30, TIMELINE.thoughtsSettle[1] * 30], [0, 1], easeInOut)
  const center: [number, number, number] = [-0.42, 1.15, 1.2]

  return (
    <group>
      {[
        { color: ACCENT, r: 0.16, phase: 0.4, kind: "loop" as const },
        { color: P.skyDeep, r: 0.13, phase: 2.4, kind: "knot" as const },
        { color: "#C9A8F5", r: 0.11, phase: 4.5, kind: "spark" as const },
      ].map((s, i) => {
        const appear = mix(
          frame,
          [TIMELINE.thoughtsEmerge[0] * 30 + i * 7, TIMELINE.thoughtsEmerge[0] * 30 + 26 + i * 7],
          [0, 1],
          easeInOut,
        )
        const radius = (0.5 + i * 0.13) * (1 - settle * 0.32)
        const angle = s.phase + t * (1.25 + i * 0.15) - settle * 0.6
        const x = center[0] + Math.cos(angle) * radius * 1.05
        const y = center[1] + Math.sin(angle) * radius * 0.5 + settle * (0.26 - i * 0.06)
        const z = center[2] + Math.sin(angle * 0.7 + i) * 0.28 - settle * 0.1
        const spin = t * 1.5 + i

        return (
          <group
            key={i}
            position={[x, y, z]}
            scale={appear * (1 - settle * 0.05)}
            rotation={[spin * 0.35, spin * 0.6, spin * 0.2]}
          >
            {s.kind === "loop" && (
              <mesh>
                <torusGeometry args={[s.r, 0.018, 10, 40]} />
                <meshStandardMaterial color={s.color} emissive={s.color} emissiveIntensity={1.5} toneMapped={false} />
              </mesh>
            )}
            {s.kind === "knot" && (
              <mesh rotation={[0.5, 0, 0]}>
                <torusKnotGeometry args={[s.r * 0.8, 0.014, 64, 8, 2, 3]} />
                <meshStandardMaterial color={s.color} emissive={s.color} emissiveIntensity={1.4} toneMapped={false} />
              </mesh>
            )}
            {s.kind === "spark" && (
              <group>
                <mesh>
                  <sphereGeometry args={[s.r * 0.55, 20, 16]} />
                  <meshStandardMaterial color={s.color} emissive={s.color} emissiveIntensity={1.8} toneMapped={false} />
                </mesh>
                <mesh rotation={[0, 0, Math.PI / 4]}>
                  <torusGeometry args={[s.r * 0.95, 0.01, 8, 32]} />
                  <meshStandardMaterial color={s.color} emissive={s.color} emissiveIntensity={1.2} toneMapped={false} />
                </mesh>
              </group>
            )}
          </group>
        )
      })}
    </group>
  )
}
