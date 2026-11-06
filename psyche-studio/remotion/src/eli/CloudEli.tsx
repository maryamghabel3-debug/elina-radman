import { useCurrentFrame } from "remotion"
import { PALETTE as P } from "./palette"
import { TIMELINE, easeInOut, easeOutBack, mix } from "./timeline"
import { eliPose } from "./eliPose"

/**
 * VERSION A — Eli as a colourful cloud.
 *
 * Silhouette: one big head-cloud on top, a smaller body-cloud underneath,
 * two cloud "puffs" that act as hands, and a pair of drifting feet tufts.
 * That 2-lobe stack is the recognisable shape; it is deliberately NOT the
 * old white clay mascot (no grey clay, no plain sphere body, no props).
 *
 * Pastel scheme, three coordinated hues + warm cream:
 *   lavender crown, peach mid, sky-blue base, cream highlight.
 */

const HEAD_Y = 0.72
const BODY_Y = -0.22

/** deterministic pseudo-random so puff placement never changes between renders */
const rand = (seed: number) => {
  const x = Math.sin(seed * 127.1 + 311.7) * 43758.5453
  return x - Math.floor(x)
}

const BODY_PUFFS: { pos: [number, number, number]; r: number; color: string }[] = [
  // body: wide, flattened base-cloud, sky blue family
  { pos: [-0.46, BODY_Y, 0.02], r: 0.34, color: "#8CCDEA" },
  { pos: [0.46, BODY_Y, 0.02], r: 0.34, color: "#8CCDEA" },
  { pos: [0.0, BODY_Y - 0.05, 0.08], r: 0.4, color: "#6FB9DE" },
  { pos: [-0.24, BODY_Y + 0.16, -0.05], r: 0.3, color: "#B4E1F4" },
  { pos: [0.26, BODY_Y + 0.14, -0.02], r: 0.29, color: "#8CCDEA" },
]

const HEAD_PUFFS: { pos: [number, number, number]; r: number; color: string }[] = [
  // head: taller crown so the silhouette differs from the body
  { pos: [0.0, HEAD_Y, 0.04], r: 0.46, color: "#C2A6EC" },
  { pos: [-0.42, HEAD_Y + 0.1, 0.0], r: 0.36, color: "#D6C2F3" },
  { pos: [0.42, HEAD_Y + 0.08, 0.0], r: 0.36, color: "#C2A6EC" },
  // peach crown puffs: the warm accent that makes the silhouette asymmetric
  { pos: [-0.2, HEAD_Y + 0.44, -0.02], r: 0.33, color: "#FFB899" },
  { pos: [0.2, HEAD_Y + 0.42, -0.01], r: 0.31, color: "#FFCDB4" },
  { pos: [0.0, HEAD_Y + 0.3, 0.2], r: 0.24, color: "#FFF0E2" },
]

/* ---------------------------------------------------------------- eyes */

const Eyes: React.FC<{
  /** horizontal look, -1 left .. 1 right */
  lookX: number
  /** vertical look, -1 down .. 1 up */
  lookY: number
  /** 0 open, 1 closed */
  blink: number
  /** eye scale for surprise */
  widen: number
  /** happy arc amount (0 = round eyes, 1 = closed smile arcs) */
  joy: number
}> = ({ lookX, lookY, blink, widen, joy }) => {
  const eyeY = HEAD_Y + 0.04
  return (
    <group position={[0, 0, 0.4]}>
      {[-0.19, 0.19].map((x) => {
        const sx = 0.1 * widen - joy * 0.022
        const sy = 0.135 * widen * (1 - blink * 0.92) + joy * 0.01
        return (
          <group key={x} position={[x, eyeY, 0]}>
            {/* white-ish sclera keeps the eye readable on a pale cloud */}
            <mesh scale={[sx, sy, 0.07]} position={[0, 0, 0.15]}>
              <sphereGeometry args={[1, 24, 18]} />
              <meshStandardMaterial color="#3A2E4A" roughness={0.26} metalness={0.05} />
            </mesh>
            {/* warm iris ring keeps the eye from reading as a black hole */}
            <mesh scale={[sx * 0.62, sy * 0.62, 0.03]} position={[lookX * 0.012, -0.01, 0.235]}>
              <sphereGeometry args={[1, 20, 16]} />
              <meshStandardMaterial
                color="#8E6BB5"
                emissive="#8E6BB5"
                emissiveIntensity={0.35}
                roughness={0.4}
              />
            </mesh>
            {/* pupil highlight: the spark that makes it feel alive */}
            <mesh
              scale={[0.03 * widen, 0.033 * widen * (1 - blink * 0.9), 0.02]}
              position={[lookX * 0.028 + 0.02, lookY * 0.026 + 0.032, 0.26]}
            >
              <sphereGeometry args={[1, 16, 12]} />
              <meshStandardMaterial color="#FFFFFF" emissive="#FFFFFF" emissiveIntensity={0.55} />
            </mesh>
            {/* the look direction, drawn as a small offset glint */}
            <mesh
              scale={[0.018, 0.018 * (1 - blink * 0.9), 0.015]}
              position={[lookX * 0.045, lookY * 0.045, 0.27]}
            >
              <sphereGeometry args={[1, 12, 10]} />
              <meshStandardMaterial color="#E7D4FF" emissive="#E7D4FF" emissiveIntensity={0.4} />
            </mesh>
          </group>
        )
      })}
      {/* mouth: a small arc that widens into a smile with joy */}
      <mesh
        position={[0, eyeY - 0.115, 0.2]}
        rotation={[0, 0, Math.PI]}
        scale={[0.055 + joy * 0.02, 0.04 + joy * 0.015, 0.02]}
      >
        <torusGeometry args={[1, 0.16, 8, 24, Math.PI]} />
        <meshStandardMaterial color="#3A2E4A" roughness={0.4} />
      </mesh>
      {/* cheeks: warmth, and they sell the "reacts" beat */}
      {[-0.31, 0.31].map((x) => (
        <mesh key={x} position={[x, eyeY - 0.13, 0.12]} scale={[0.075, 0.042, 0.025]}>
          <sphereGeometry args={[1, 16, 12]} />
          <meshStandardMaterial color={P.coral} roughness={0.9} transparent opacity={0.65} />
        </mesh>
      ))}
    </group>
  )
}

/* --------------------------------------------------------------- cloud */

export interface CloudEliProps {
  /** 0..1 phone screen brightness */
  phoneLit: number
}

export const CloudEli: React.FC<CloudEliProps> = ({ phoneLit }) => {
  const frame = useCurrentFrame()
  const pose = eliPose(frame)
  const { t, turn, reach, joy, pop, blink, widen, lookX, lookY, float } = pose

  /* ---- body lean / squash, all derived from the shared pose ---- */
  const idleTilt = Math.sin(t * 1.35 + 0.6) * 0.06
  const squash = 1 + Math.sin(t * 1.8 + 1.2) * 0.062 + pop * 0.1 - joy * 0.03 + reach * 0.04
  const stretchXZ = 1 / Math.sqrt(squash)
  const leanIn = turn * 0.14
  const handLift = reach * 0.6
  const handWiggle = Math.sin(t * 4.2) * 0.06 * (0.4 + joy)

  return (
    <group
      position={[-0.32 + pose.enterDriftX, -0.3 + float + pose.enterOffset, 0.9]}
      rotation={[0, 0.16 + turn * 0.26 + idleTilt, -turn * 0.06]}
    >
      <group scale={[stretchXZ, squash, stretchXZ]} rotation={[0, 0, idleTilt]}>
        {/* ---------------- body cloud ---------------- */}
        {BODY_PUFFS.map((p, i) => (
          <mesh
            key={`b${i}`}
            position={[p.pos[0] + leanIn * 0.5, p.pos[1] + Math.sin(t * 1.3 + i) * 0.012, p.pos[2]]}
            scale={[1.12, 0.9, 0.82]}
            castShadow
            receiveShadow
          >
            <sphereGeometry args={[p.r, 32, 24]} />
            <meshStandardMaterial color={p.color} emissive={p.color} emissiveIntensity={0.3} roughness={0.92} />
          </mesh>
        ))}

        {/* ---------------- head cloud ---------------- */}
        {HEAD_PUFFS.map((p, i) => (
          <mesh
            key={`h${i}`}
            position={[p.pos[0] + leanIn * 0.8 + Math.sin(t * 1.1 + i * 1.7) * 0.014, p.pos[1], p.pos[2]]}
            scale={[1.06, 0.98, 0.92]}
            castShadow
            receiveShadow
          >
            <sphereGeometry args={[p.r, 32, 24]} />
            <meshStandardMaterial color={p.color} emissive={p.color} emissiveIntensity={0.3} roughness={0.92} />
          </mesh>
        ))}

        {/* ---------------- face ---------------- */}
        <group position={[leanIn * 0.8, 0, 0]} rotation={[0, 0, Math.sin(t * 1.35 + 1.4) * 0.05]}>
          <Eyes lookX={lookX} lookY={lookY} blink={blink} widen={widen} joy={joy} />
          {/* crown curl: three shrinking puffs that bend back — this is the
              silhouette signature that keeps the cloud from reading as a
              generic ball of spheres */}
          {[
            { p: [0.04, HEAD_Y + 0.58, 0.22] as [number, number, number], r: 0.12, c: P.yellow },
            { p: [0.14, HEAD_Y + 0.68, 0.16] as [number, number, number], r: 0.095, c: "#FFCE7A" },
            { p: [0.22, HEAD_Y + 0.74, 0.08] as [number, number, number], r: 0.07, c: "#FFE0A0" },
          ].map((c, i) => (
            <mesh key={i} position={c.p} scale={[0.72, 1.15, 0.72]} castShadow>
              <sphereGeometry args={[c.r, 20, 16]} />
              <meshStandardMaterial color={c.c} emissive={c.c} emissiveIntensity={0.34} roughness={0.8} />
            </mesh>
          ))}
        </group>

        {/* ---------------- hand puffs ---------------- */}
        {[
          { side: -1, x: -0.76, lift: 0.55 },
          { side: 1, x: 0.78, lift: 1.0 },
        ].map(({ side, x, lift }) => (
          <mesh
            key={side}
            position={[
              x + handWiggle * side,
              BODY_Y + 0.02 + handLift * lift + handWiggle * 0.5,
              0.18 + handLift * 0.3,
            ]}
            rotation={[0, 0, side * (0.35 + handLift * 0.7)]}
            scale={[1.05, 0.85, 0.85]}
            castShadow
          >
            <sphereGeometry args={[0.155, 28, 20]} />
            <meshStandardMaterial
              color={side > 0 ? "#FFAF92" : "#FFC4AE"}
              emissive={side > 0 ? "#FFAF92" : "#FFC4AE"}
              emissiveIntensity={0.26}
              roughness={0.9}
            />
          </mesh>
        ))}

        {/* ---------------- feet tufts ---------------- */}
        {[-0.24, 0.24].map((x) => (
          <mesh
            key={x}
            position={[x, BODY_Y - 0.42 + Math.sin(t * 1.9 + x) * 0.02, 0.06]}
            scale={[1.1, 0.6, 0.9]}
            castShadow
          >
            <sphereGeometry args={[0.15, 24, 18]} />
            <meshStandardMaterial color={P.lavenderSoft} emissive={P.lavenderSoft} emissiveIntensity={0.26} roughness={0.95} />
          </mesh>
        ))}
      </group>

      {/* the cloud picks up a warm glow while the phone is lit */}
      <pointLight
        position={[0.4, BODY_Y, 0.6]}
        color={P.yellowSoft}
        intensity={phoneLit * 1.8}
        distance={2.4}
        decay={2}
      />
    </group>
  )
}

/* ------------------------------------------------- thought shapes (A) */

export interface ThoughtShapeProps {
  index: number
  /** 0..1 how present the shape is */
  life: number
}

/**
 * Three rounded "idea" blobs — a thought bubble language that matches the
 * cloud, plus one small ring. They emerge from beside Eli's head, orbit, then
 * settle into a tidy arc.
 */
export const CloudThoughts: React.FC<{ emerge: number; orbit: number; settle: number }> = ({
  emerge,
  orbit,
  settle,
}) => {
  const frame = useCurrentFrame()
  const t = frame / TIMELINE.fps

  const center: [number, number, number] = [-0.42, 1.02, 1.1]

  return (
    <group>
      {[
        { color: P.yellow, r: 0.155, phase: 0.6, ring: false },
        { color: P.peach, r: 0.125, phase: 2.5, ring: false },
        { color: P.skyDeep, r: 0.11, phase: 4.6, ring: true },
      ].map((s, i) => {
        const appear = mix(
          frame,
          [TIMELINE.thoughtsEmerge[0] * 30 + i * 7, TIMELINE.thoughtsEmerge[0] * 30 + 28 + i * 7],
          [0, 1],
          easeOutBack,
        )
        const settleT = mix(
          frame,
          [TIMELINE.thoughtsSettle[0] * 30 + i * 5, TIMELINE.thoughtsSettle[1] * 30 + i * 5],
          [0, 1],
          easeInOut,
        )
        const radius = (0.5 + i * 0.14) * (1 - settleT * 0.3)
        const angle = s.phase + orbit * (1.5 + i * 0.12) - settleT * 0.55
        const x = center[0] + Math.cos(angle) * radius * 0.95
        const y = center[1] + Math.sin(angle) * radius * 0.5 + settleT * (0.3 - i * 0.06)
        const z = center[2] + Math.sin(angle * 0.7 + i) * 0.35 - settleT * 0.15
        const bob = Math.sin(t * 2.6 + i * 1.9) * 0.075 * (1 - settleT * 0.35)
        const scale = appear * (1 + Math.sin(t * 2.6 + i) * 0.04)

        return (
          <group key={i} position={[x, y + bob, z]} scale={scale}>
            {s.ring ? (
              <mesh rotation={[0.4, 0.6 + t * 0.4, 0.2]}>
                <torusGeometry args={[s.r * 0.82, s.r * 0.3, 16, 40]} />
                <meshStandardMaterial
                  color={s.color}
                  emissive={s.color}
                  emissiveIntensity={0.35}
                  roughness={0.6}
                />
              </mesh>
            ) : (
              <group scale={[1, 0.86, 0.86]}>
                <mesh>
                  <sphereGeometry args={[s.r, 28, 20]} />
                  <meshStandardMaterial
                    color={s.color}
                    emissive={s.color}
                    emissiveIntensity={0.3}
                    roughness={0.8}
                  />
                </mesh>
                <mesh position={[-s.r * 0.28, s.r * 0.3, s.r * 0.7]} scale={0.28}>
                  <sphereGeometry args={[s.r, 16, 12]} />
                  <meshStandardMaterial color={P.white} emissive={P.white} emissiveIntensity={0.6} />
                </mesh>
              </group>
            )}
          </group>
        )
      })}
    </group>
  )
}

