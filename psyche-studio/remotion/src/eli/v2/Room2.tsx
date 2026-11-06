import { useCurrentFrame } from "remotion"
import { EliPalette } from "./palette"
import { easeInOut, mix } from "../timeline"

/**
 * V2 room. Fewer objects than V1, deeper values, and a strict value ordering:
 *
 *     background wall  (deepest, low saturation)
 *       < furniture    (mid)
 *         < Eli        (brightest, most saturated, highest contrast)
 *
 * That ordering is what makes the character pop without adding glow tricks.
 * The background is also a separate layer pushed back in Z and darkened, so
 * separation survives even where hues are close.
 */

export const FLOOR_Y2 = -0.95
const WALL_Z2 = -3.6
const BACK_W2 = 8.6

export interface Room2Props {
  pal: EliPalette
  phoneLit: number
  /** 0..1, drives the room fading up at the start */
  establish: number
  /** point the notification bubble should be anchored to (bubble is a DOM overlay) */
  children?: React.ReactNode
}

/* ------------------------------------------------------------- background */

const Background: React.FC<{ pal: EliPalette }> = ({ pal }) => (
  <group>
    {/* back wall — the deepest surface in the room */}
    <mesh position={[0, 2.6, WALL_Z2]} receiveShadow>
      <planeGeometry args={[16, 12]} />
      <meshStandardMaterial color={pal.wallBack} roughness={1} />
    </mesh>

    {/* a big inset panel in a darker value: gives the wall structure and
        guarantees Eli never sits on a flat field of identical colour */}
    <mesh position={[0, 1.25, WALL_Z2 + 0.012]}>
      <planeGeometry args={[6.4, 3.6]} />
      <meshStandardMaterial color={pal.wallSide} roughness={1} />
    </mesh>

    {/* gentle upper glow, feathered with an alpha gradient so it never shows
        a hard horizontal seam across the wall */}
    <mesh position={[0, 3.35, WALL_Z2 + 0.02]}>
      <planeGeometry args={[16, 3.4]} />
      <meshStandardMaterial
        color={pal.wallUpper}
        roughness={1}
        transparent
        opacity={0.5}
        depthWrite={false}
      />
    </mesh>

    {/* skirting */}
    <mesh position={[0, FLOOR_Y2 + 0.1, WALL_Z2 + 0.06]} receiveShadow>
      <boxGeometry args={[BACK_W2, 0.2, 0.1]} />
      <meshStandardMaterial color={pal.wallTrim} roughness={0.7} />
    </mesh>
  </group>
)

const Floor: React.FC<{ pal: EliPalette }> = ({ pal }) => (
  <group>
    <mesh position={[0, FLOOR_Y2, 3.2]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <planeGeometry args={[16, 18]} />
      <meshStandardMaterial color={pal.floor} roughness={0.95} />
    </mesh>
    {/* rug: a darker value than the floor, so Eli's contact shadow reads */}
    <mesh position={[0.05, FLOOR_Y2 + 0.01, 0.5]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <circleGeometry args={[2.0, 64]} />
      <meshStandardMaterial color={pal.rug} roughness={1} />
    </mesh>
    <mesh position={[0.05, FLOOR_Y2 + 0.018, 0.5]} rotation={[-Math.PI / 2, 0, 0]}>
      <ringGeometry args={[1.62, 1.78, 64]} />
      <meshStandardMaterial color={pal.rugRing} roughness={0.85} />
    </mesh>
  </group>
)

/* ---------------------------------------------------------------- furniture */

const Sofa: React.FC<{ pal: EliPalette }> = ({ pal }) => (
  <group position={[1.85, FLOOR_Y2, -2.3]} rotation={[0, 0.46, 0]} scale={0.95}>
    <mesh position={[0, 0.3, 0]} castShadow receiveShadow>
      <boxGeometry args={[1.25, 0.26, 0.92]} />
      <meshStandardMaterial color={pal.sofa} roughness={0.92} />
    </mesh>
    <mesh position={[0, 0.64, -0.38]} rotation={[-0.14, 0, 0]} castShadow receiveShadow>
      <boxGeometry args={[1.25, 0.62, 0.22]} />
      <meshStandardMaterial color={pal.sofaDeep} roughness={0.92} />
    </mesh>
    {[-0.58, 0.58].map((x) => (
      <mesh key={x} position={[x, 0.44, 0.02]} castShadow receiveShadow>
        <boxGeometry args={[0.16, 0.46, 0.94]} />
        <meshStandardMaterial color={pal.sofaDeep} roughness={0.92} />
      </mesh>
    ))}
    <mesh position={[-0.28, 0.57, -0.26]} rotation={[0.22, 0, 0.1]} castShadow>
      <boxGeometry args={[0.32, 0.32, 0.1]} />
      <meshStandardMaterial color={pal.sofaCushion} roughness={0.95} />
    </mesh>
  </group>
)

const Plant: React.FC<{ pal: EliPalette }> = ({ pal }) => {
  const frame = useCurrentFrame()
  const sway = Math.sin(frame * 0.05) * 0.06
  return (
    <group position={[1.95, FLOOR_Y2, -1.15]} scale={0.9}>
      <mesh position={[0, 0.2, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.22, 0.17, 0.4, 22]} />
        <meshStandardMaterial color={pal.plantPot} roughness={0.85} />
      </mesh>
      {[-0.6, -0.2, 0.2, 0.6].map((spread, i) => {
        const h = 0.72 + (i % 2) * 0.24
        return (
          <group key={spread} rotation={[0, 0, spread * 0.42 + sway * (i % 2 ? 1 : -1)]}>
            <mesh position={[0, 0.4 + h / 2, 0]} castShadow>
              <cylinderGeometry args={[0.011, 0.014, h, 8]} />
              <meshStandardMaterial color={pal.plantLeafDeep} roughness={0.9} />
            </mesh>
            <mesh
              position={[0, 0.4 + h * 0.82, 0.03]}
              rotation={[0.5, spread * 0.5, spread * 0.7]}
              scale={[1, 1.6, 0.34]}
              castShadow
            >
              <sphereGeometry args={[0.11, 16, 12]} />
              <meshStandardMaterial color={i % 2 ? pal.plantLeaf : pal.plantLeafDeep} roughness={0.9} />
            </mesh>
          </group>
        )
      })}
    </group>
  )
}

const SideTable: React.FC<{ pal: EliPalette; phoneLit: number; children?: React.ReactNode }> = ({
  pal,
  phoneLit,
  children,
}) => (
  <group position={[-1.12, FLOOR_Y2, 0.66]} rotation={[0, 0.42, 0]} scale={1.0}>
    <mesh position={[0, 0.62, 0]} castShadow receiveShadow>
      <cylinderGeometry args={[0.42, 0.42, 0.06, 36]} />
      <meshStandardMaterial color={pal.tableTop} roughness={0.7} />
    </mesh>
    <mesh position={[0, 0.32, 0]} castShadow>
      <cylinderGeometry args={[0.05, 0.05, 0.62, 16]} />
      <meshStandardMaterial color={pal.tableLeg} roughness={0.6} />
    </mesh>
    <mesh position={[0, 0.035, 0]} castShadow receiveShadow>
      <cylinderGeometry args={[0.24, 0.27, 0.07, 26]} />
      <meshStandardMaterial color={pal.tableLeg} roughness={0.6} />
    </mesh>

    {/* ---------------- phone: large, tilted toward camera ---------------- */}
    <group position={[0, 0.675, 0.06]} rotation={[-0.42, 0.24, 0]}>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[0.44, 0.86, 0.035]} />
        <meshStandardMaterial color={pal.phoneBody} roughness={0.42} metalness={0.15} />
      </mesh>
      <mesh position={[0, 0, 0.019]}>
        <planeGeometry args={[0.4, 0.81]} />
        <meshStandardMaterial
          color={phoneLit > 0.02 ? pal.phoneScreenOn : pal.phoneScreenOff}
          emissive={phoneLit > 0.02 ? pal.phoneScreenOn : "#000000"}
          emissiveIntensity={phoneLit * 0.85}
          roughness={0.32}
        />
      </mesh>
      {/* the Persian chat bubble is a DOM overlay projected onto this plane,
          so the 3D screen just needs to be lit and clean */}
      {children as never}
      <pointLight
        position={[0, 0.1, 0.28]}
        color={pal.phoneScreenOn}
        intensity={phoneLit * 2.4}
        distance={3.0}
        decay={2}
      />
    </group>

    {/* phone stand */}
    <mesh position={[0, 0.68, -0.2]} rotation={[0.55, 0, 0]} castShadow>
      <boxGeometry args={[0.22, 0.3, 0.02]} />
      <meshStandardMaterial color={pal.tableLeg} roughness={0.6} />
    </mesh>
  </group>
)

const Window: React.FC<{ pal: EliPalette }> = ({ pal }) => (
  <group position={[-2.15, 2.15, WALL_Z2 + 0.05]} scale={0.85}>
    <mesh castShadow>
      <boxGeometry args={[1.5, 1.8, 0.09]} />
      <meshStandardMaterial color={pal.wallTrim} roughness={0.6} />
    </mesh>
    <mesh position={[0, 0, 0.06]}>
      <planeGeometry args={[1.3, 1.6]} />
      <meshStandardMaterial color={pal.window} emissive={pal.windowGlow} emissiveIntensity={0.55} roughness={0.25} />
    </mesh>
    <mesh position={[0, 0, 0.075]}>
      <boxGeometry args={[1.34, 0.05, 0.02]} />
      <meshStandardMaterial color={pal.wallTrim} roughness={0.6} />
    </mesh>
    <mesh position={[0, 0, 0.075]}>
      <boxGeometry args={[0.05, 1.64, 0.02]} />
      <meshStandardMaterial color={pal.wallTrim} roughness={0.6} />
    </mesh>
  </group>
)

const Lamp: React.FC<{ pal: EliPalette }> = ({ pal }) => (
  <group position={[0.05, 2.6, -1.4]}>
    <mesh position={[0, 0.6, 0]}>
      <cylinderGeometry args={[0.008, 0.008, 1.2, 8]} />
      <meshStandardMaterial color={pal.wallTrim} />
    </mesh>
    <mesh position={[0, 0, 0]} castShadow>
      <coneGeometry args={[0.3, 0.3, 30, 1, true]} />
      <meshStandardMaterial color={pal.lampShade} roughness={0.7} side={2} />
    </mesh>
    <mesh position={[0, -0.12, 0]}>
      <sphereGeometry args={[0.075, 20, 16]} />
      <meshStandardMaterial color={pal.lampGlow} emissive={pal.lampGlow} emissiveIntensity={1.5} />
    </mesh>
  </group>
)

/* ------------------------------------------------------- contact shadow */

/**
 * Soft radial contact shadow under Eli. A real shadow map gives the shape of
 * the cloud; this plane guarantees the soft ambient occlusion-style grounding
 * that makes it look like it has weight, even under SwiftShader.
 */
const ContactShadow: React.FC<{ pal: EliPalette; scale: number }> = ({ pal, scale }) => (
  <mesh position={[-0.1, FLOOR_Y2 + 0.03, 0.55]} rotation={[-Math.PI / 2, 0, 0]}>
    <circleGeometry args={[1.05 * scale, 48]} />
    <meshBasicMaterial color={pal.shadowTint} transparent opacity={0.55} depthWrite={false} />
  </mesh>
)

/* ------------------------------------------------------------------ room */

export const Room2: React.FC<Room2Props> = ({ pal, phoneLit, establish, children }) => {
  const frame = useCurrentFrame()
  const lightUp = mix(frame, [0, 42], [0.15, 1], easeInOut)

  return (
    <group>
      <Background pal={pal} />
      <Floor pal={pal} />
      <Window pal={pal} />
      <Lamp pal={pal} />
      <Sofa pal={pal} />
      <Plant pal={pal} />
      <SideTable pal={pal} phoneLit={phoneLit}>
        {children}
      </SideTable>

      {/* ---------- lighting: key + fill + rim, low ambient ---------- */}
      {/* ambient is deliberately tiny: it sets the floor of the value range,
          and V1 died because this floor was too high */}
      <ambientLight intensity={0.1 + 0.06 * lightUp} color={pal.ambientGround} />
      <hemisphereLight args={[pal.wallUpper, pal.ambientGround, 0.22 * lightUp]} />

      {/* KEY: warm, high, from the left. Hard enough to make a real shadow. */}
      <directionalLight
        position={[-2.4, 4.4, 3.2]}
        intensity={2.7 * lightUp}
        color={pal.keyLight}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-left={-3.6}
        shadow-camera-right={3.6}
        shadow-camera-top={3.6}
        shadow-camera-bottom={-2.4}
        shadow-camera-near={0.5}
        shadow-camera-far={16}
        shadow-bias={-0.0004}
        shadow-normalBias={0.022}
      />

      {/* FILL: opposite side, low intensity, tinted with the room colour so
          the shadow side stays coloured instead of going grey */}
      <directionalLight position={[3.0, 1.1, 2.0]} intensity={0.55 * lightUp} color={pal.fillLight} />

      {/* RIM: behind and above, traces Eli's silhouette against the wall */}
      <spotLight
        position={[0.9, 3.2, -2.6]}
        angle={0.9}
        penumbra={0.85}
        intensity={9 * lightUp}
        color={pal.rimLight}
        distance={9}
        decay={1.6}
      />
      <pointLight position={[-2.0, 1.6, 0.8]} intensity={1.5 * lightUp} color={pal.windowGlow} distance={5} decay={2} />

      {/* warm spill from the phone once the notification lands */}
      <pointLight
        position={[1.2, 0.2, 1.0]}
        color={pal.phoneScreenOn}
        intensity={phoneLit * 2.2 * (0.8 + 0.2 * Math.sin(frame * 0.09))}
        distance={2.6}
        decay={2}
      />
    </group>
  )
}

/* -------------------------------------------------------------- camera */

/**
 * Fixed framing with a gentle push-in on the notification beat.
 * Eli's ground line is at FLOOR_Y2 and its body spans roughly y −0.95 … 2.1, so
 * the camera is placed to keep all of it inside y 250–1500 of the 1080×1920
 * frame. `safeAreaCheck` in the render script asserts this on the stills.
 */
export const CAMERA2 = {
  fov: 42,
  base: (frame: number, pushIn: number): [number, number, number] => [
    0,
    0.42 + Math.sin(frame * 0.011) * 0.006,
    8.0 - pushIn * 0.45 - mix(frame, [0, 300], [0, 0.07], easeInOut),
  ],
  pitch: -0.02,
}
