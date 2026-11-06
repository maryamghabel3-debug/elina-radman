import { useCurrentFrame } from "remotion"
import { useMemo } from "react"
import { Color } from "three"
import { EliPalette } from "./palette"
import { EliV2Pose, eliV2Pose } from "./pose2"

/**
 * V2 Eli — ONE creature.
 *
 * The V1 problem was that the head cloud and the body cloud read as two
 * separate objects. Here the silhouette is one continuous mass: the lobes
 * overlap their neighbours, and three "neck" lobes sit inside both the head and
 * the body so there is no pinch point between them.
 *
 * Expression is built from three separable parts so it can actually change:
 *   brows (angle + lift), eyes (scale + blink + gaze + squint), mouth (width +
 *   open + curve). Calm -> curious -> worried -> resolved each move all three.
 */

/* ------------------------------------------------------------ silhouette */

type Puff = { p: [number, number, number]; r: number; tone: 0 | 1 | 2 }

/**
 * One continuous mass, bottom-up. Every lobe overlaps its neighbour, and the
 * neck lobes (y ≈ 0.02) are buried inside both the body and the head.
 * The whole silhouette is deliberately WIDER THAN TALL at the base and narrows
 * to a smaller head, which is what reads as "one chubby creature" rather than
 * "a ball on a cushion".
 */
const PUFTS: Puff[] = [
  // ---- body base: a wide, soft cloud foot ----
  { p: [-0.44, -0.62, 0.06], r: 0.31, tone: 1 },
  { p: [0.44, -0.62, 0.06], r: 0.31, tone: 1 },
  { p: [-0.2, -0.66, 0.16], r: 0.33, tone: 0 },
  { p: [0.22, -0.66, 0.15], r: 0.32, tone: 0 },
  { p: [0.0, -0.7, 0.2], r: 0.31, tone: 1 },
  // ---- torso ----
  { p: [-0.27, -0.32, 0.14], r: 0.32, tone: 0 },
  { p: [0.27, -0.32, 0.14], r: 0.32, tone: 0 },
  { p: [0.0, -0.3, 0.22], r: 0.34, tone: 0 },
  // ---- neck: buried in both masses, this is the weld ----
  { p: [-0.16, 0.02, 0.14], r: 0.27, tone: 1 },
  { p: [0.16, 0.02, 0.14], r: 0.27, tone: 1 },
  // ---- head ----
  { p: [0.0, 0.36, 0.1], r: 0.42, tone: 0 },
  { p: [-0.28, 0.26, 0.08], r: 0.3, tone: 1 },
  { p: [0.28, 0.26, 0.08], r: 0.3, tone: 1 },
  { p: [-0.16, 0.6, 0.0], r: 0.27, tone: 2 },
  { p: [0.17, 0.59, 0.0], r: 0.26, tone: 2 },
  // ---- crown curl: silhouette signature, shrinking, all overlapping ----
  { p: [-0.03, 0.76, 0.16], r: 0.125, tone: 2 },
  { p: [0.07, 0.86, 0.1], r: 0.1, tone: 1 },
  { p: [0.16, 0.93, 0.02], r: 0.076, tone: 2 },
  { p: [0.22, 0.97, -0.06], r: 0.058, tone: 1 },
]

const HEAD_Y = 0.36
/** face sits on the front of the head */
const FACE_Z = 0.55

/* ------------------------------------------------------------------ face */

const Brow: React.FC<{ x: number; angle: number; lift: number; color: string }> = ({ x, angle, lift, color }) => (
  <mesh position={[x, HEAD_Y + 0.2 + lift, FACE_Z + 0.01]} rotation={[0, 0, angle]}>
    <capsuleGeometry args={[0.017, 0.072, 4, 10]} />
    <meshStandardMaterial color={color} roughness={0.5} />
  </mesh>
)

const Eye: React.FC<{
  x: number
  open: number
  lookX: number
  lookY: number
  blink: number
  pal: EliPalette
  squeeze: number
}> = ({ x, open, lookX, lookY, blink, pal, squeeze }) => {
  // eye radius, deliberately modest: the iris + catchlight carry the read
  const r = 0.098 * open
  const h = r * (1 - blink * 0.95)
  const squint = squeeze * 0.02

  return (
    <group position={[x, HEAD_Y + 0.06, FACE_Z]}>
      {/* sclera */}
      <mesh scale={[r, Math.max(0.004, h), 0.02]} position={[0, 0, 0]}>
        <sphereGeometry args={[1, 26, 18]} />
        <meshStandardMaterial color="#FFFBF2" roughness={0.3} />
      </mesh>
      {/* iris — large relative to the sclera, which is what makes it cute */}
      <mesh scale={[r * 0.92, Math.max(0.003, h * 0.96), 0.016]} position={[lookX * 0.012, lookY * 0.012 - squint, 0.012]}>
        <sphereGeometry args={[1, 24, 16]} />
        <meshStandardMaterial color={pal.eyeIris} roughness={0.28} emissive={pal.eyeIris} emissiveIntensity={0.3} />
      </mesh>
      {/* pupil */}
      <mesh scale={[r * 0.42, Math.max(0.002, h * 0.5), 0.014]} position={[lookX * 0.014, lookY * 0.014 - squint, 0.02]}>
        <sphereGeometry args={[1, 20, 14]} />
        <meshStandardMaterial color={pal.eyeDark} roughness={0.2} />
      </mesh>
      {/* catchlight */}
      <mesh scale={[r * 0.24, Math.max(0.002, h * 0.22), 0.01]} position={[lookX * 0.012 + 0.026, lookY * 0.012 + 0.032, 0.028]}>
        <sphereGeometry args={[1, 14, 10]} />
        <meshStandardMaterial color="#FFFFFF" emissive="#FFFFFF" emissiveIntensity={1.4} />
      </mesh>
    </group>
  )
}

/**
 * Mouth: torus arc whose width, openness and curvature animate.
 * smile > 0 curves up; worried turns it into a small open frown.
 */
const Mouth: React.FC<{ width: number; open: number; smile: number; pal: EliPalette }> = ({
  width,
  open,
  smile,
  pal,
}) => {
  const arc = Math.PI * Math.min(0.62, 0.42 + Math.abs(smile) * 0.26)
  const flip = smile >= 0
  return (
    <group position={[0, HEAD_Y - 0.15, FACE_Z + 0.03]} rotation={[0, 0, flip ? Math.PI : 0]} scale={[width, 1, 1]}>
      <mesh>
        <torusGeometry args={[0.078, 0.026, 12, 32, arc]} />
        <meshStandardMaterial color={pal.mouth} roughness={0.4} />
      </mesh>
      {/* the open mouth: a small ellipse with a warm tongue dot */}
      {open > 0.05 ? (
        <group>
          <mesh scale={[0.042 * open * 1.6, 0.055 * open * 1.6, 0.016]} position={[0, -0.048 * open, -0.008]}>
            <sphereGeometry args={[1, 20, 16]} />
            <meshStandardMaterial color={pal.mouth} roughness={0.45} />
          </mesh>
          <mesh scale={[0.026 * open * 1.6, 0.018 * open * 1.6, 0.012]} position={[0, -0.062 * open, 0.004]}>
            <sphereGeometry args={[1, 16, 12]} />
            <meshStandardMaterial color="#E8607A" roughness={0.5} />
          </mesh>
        </group>
      ) : null}
    </group>
  )
}

/* ------------------------------------------------------------ the creature */

export interface CloudEli2Props {
  pal: EliPalette
  pose: EliV2Pose
}

export const CloudEli2: React.FC<CloudEli2Props> = ({ pal, pose }) => {
  const frame = useCurrentFrame()
  const p = pose ?? eliV2Pose(frame)

  /* colour: violet, drifting towards a stormier tint while worried */
  const core = useMemo(() => {
    const base = new Color(pal.eliCore)
    return base.clone().lerp(new Color(pal.eliWorried), p.worried * 0.7)
  }, [pal.id, p.worried])

  const toneColor = (tone: 0 | 1 | 2): string => {
    if (tone === 0) return `#${core.getHexString()}`
    const c = core.clone()
    if (tone === 2) c.lerp(new Color(pal.eliLight), 0.1)
    else c.lerp(new Color(pal.eliDeepShade), 0.04)
    return `#${c.getHexString()}`
  }

  const squash = p.squash
  const stretchXZ = 1 / Math.sqrt(squash)

  return (
    <group position={[-0.02 + p.enterX + p.jitterX, 0.06 + p.float + p.jitterY + p.enterY, 0.9]}>
      <group
        rotation={[0, 0.06 + p.turn * 0.2 + p.jitterRot, -p.turn * 0.04]}
        scale={[stretchXZ * 1.04, squash * 1.12, stretchXZ * 1.04]}
      >
        {/* ---------------- body: one merged mass ---------------- */}
        {PUFTS.map((puff, i) => (
          <mesh
            key={i}
            position={[puff.p[0], puff.p[1] + Math.sin(p.t * 1.6 + i * 1.3) * 0.008, puff.p[2]]}
            scale={[1.08, 0.98, 0.92]}
            castShadow
            receiveShadow
          >
            <sphereGeometry args={[puff.r, 32, 24]} />
            <meshStandardMaterial
              color={toneColor(puff.tone)}
              roughness={0.6}
              metalness={0}
              emissive={toneColor(puff.tone)}
              emissiveIntensity={0.2}
            />
          </mesh>
        ))}

        {/* ---------------- arms: attached and rooted inside the body ---------------- */}
        {[-1, 1].map((side) => {
          const swing = side > 0 ? p.armSwing : p.armSwing * 0.75
          return (
            <group
              key={side}
              position={[side * 0.36, -0.24, 0.2]}
              rotation={[0, 0, side * (0.35 + swing * 0.5)]}
            >
              <mesh position={[side * 0.14, -0.08, 0]} rotation={[0, 0, side * 0.3]} castShadow>
                <capsuleGeometry args={[0.1, 0.14, 6, 14]} />
                <meshStandardMaterial color={toneColor(1)} roughness={0.6} />
              </mesh>
              <mesh position={[side * 0.24, -0.22, 0.03]} rotation={[0, 0, side * 0.45]} castShadow>
                <capsuleGeometry args={[0.08, 0.11, 6, 14]} />
                <meshStandardMaterial color={toneColor(0)} roughness={0.6} />
              </mesh>
              <mesh position={[side * 0.3, -0.34, 0.05]} scale={[1, 0.92, 0.95]} castShadow>
                <sphereGeometry args={[0.105, 22, 16]} />
                <meshStandardMaterial color={toneColor(2)} roughness={0.58} />
              </mesh>
            </group>
          )
        })}

        {/* ---------------- face ---------------- */}
        <group>
          <Brow x={-0.135} angle={-p.browAngle} lift={p.browLift} color="#3A2555" />
          <Brow x={0.135} angle={p.browAngle} lift={p.browLift} color="#3A2555" />

          <Eye x={-0.14} open={p.eyeOpen} lookX={p.lookX} lookY={p.lookY} blink={p.blink} pal={pal} squeeze={p.worried} />
          <Eye x={0.14} open={p.eyeOpen} lookX={p.lookX} lookY={p.lookY} blink={p.blink} pal={pal} squeeze={p.worried} />

          <Mouth width={p.mouthWidth} open={p.mouthOpen} smile={p.smile} pal={pal} />

          {/* cheeks */}
          {[-0.24, 0.24].map((x) => (
            <mesh key={x} position={[x, HEAD_Y - 0.06, FACE_Z - 0.03]} scale={[0.046, 0.028, 0.018]}>
              <sphereGeometry args={[1, 16, 12]} />
              <meshStandardMaterial
                color={pal.eliBlush}
                transparent
                opacity={0.5 + p.resolved * 0.3}
                roughness={0.9}
              />
            </mesh>
          ))}
        </group>
      </group>

      {/* Eli carries its own light: a character-only key + rim, so it stays the
          brightest object no matter how dark the room is */}
      <pointLight position={[0.7, 1.4, 1.8]} color={pal.eliRim} intensity={10.5 + p.resolved * 4} distance={4.5} decay={2} />
      <pointLight position={[-0.9, 0.2, 1.4]} color={pal.eliLight} intensity={4.6 + p.worried * 0.6} distance={3.5} decay={2} />
      <pointLight position={[0, 0.9, -1.2]} color={pal.rimLight} intensity={4.6} distance={4.0} decay={2} />
    </group>
  )
}

/** approximate world-space height of Eli's crown, used by overlays */
export const ELI_CROWN_Y = 0.95
