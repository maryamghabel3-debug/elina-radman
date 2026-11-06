import { useCurrentFrame } from "remotion"
import { PALETTE as P } from "./palette"
import { easeInOut, easeOut, mix } from "./timeline"

/**
 * The shared room. Identical geometry, materials, lights and camera framing
 * for Eli Cloud and Eli Lines — only the character swaps.
 *
 * Everything is primitive geometry: no external assets, no downloaded
 * textures, deterministic every frame.
 *
 * Scale: a small "dollhouse" set built around a 1.8 m tall character so that a
 * 9:16 frame reads as a cosy room instead of a warehouse.
 */

/* ------------------------------------------------------- set dimensions */

export const FLOOR_Y = -0.78
const WALL_Z = -3.1
const BACK_W = 8.4

/* ------------------------------------------------------------------ room */

const BackWall: React.FC = () => (
  <group>
    <mesh position={[0, 1.6, WALL_Z]} receiveShadow>
      <planeGeometry args={[BACK_W, 5.2]} />
      <meshStandardMaterial color={P.wallBack} roughness={0.96} />
    </mesh>
    {/* skirting */}
    <mesh position={[0, FLOOR_Y + 0.12, WALL_Z + 0.04]} receiveShadow>
      <boxGeometry args={[BACK_W, 0.24, 0.1]} />
      <meshStandardMaterial color={P.skirting} roughness={0.8} />
    </mesh>
  </group>
)

const Floor: React.FC = () => (
  <group>
    <mesh position={[0, FLOOR_Y, 3.0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <planeGeometry args={[14, 16]} />
      <meshStandardMaterial color={P.floor} roughness={0.92} />
    </mesh>
    {/* rug — anchors the character and carries the contact shadow */}
    <mesh position={[0.05, FLOOR_Y + 0.008, 0.55]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <circleGeometry args={[1.55, 64]} />
      <meshStandardMaterial color={P.rug} roughness={1} />
    </mesh>
    <mesh position={[0.05, FLOOR_Y + 0.014, 0.55]} rotation={[-Math.PI / 2, 0, 0]}>
      <ringGeometry args={[1.22, 1.36, 64]} />
      <meshStandardMaterial color={P.rugRing} roughness={1} />
    </mesh>
  </group>
)

const Window: React.FC = () => (
  <group position={[-1.62, 0.62, WALL_Z + 0.03]}>
    <mesh position={[0, 0, 0.03]} castShadow>
      <boxGeometry args={[1.3, 1.55, 0.08]} />
      <meshStandardMaterial color={P.cream} roughness={0.7} />
    </mesh>
    <mesh position={[0, 0, 0.08]}>
      <planeGeometry args={[1.12, 1.37]} />
      <meshStandardMaterial color={P.skySoft} roughness={0.3} />
    </mesh>
    {/* distant skyline: soft, small, purely for depth */}
    <mesh position={[-0.28, -0.44, 0.09]}>
      <planeGeometry args={[0.3, 0.5]} />
      <meshStandardMaterial color={P.sky} roughness={0.6} />
    </mesh>
    <mesh position={[0.16, -0.52, 0.09]}>
      <planeGeometry args={[0.36, 0.36]} />
      <meshStandardMaterial color="#BFE2F5" roughness={0.6} />
    </mesh>
    <mesh position={[0.4, -0.4, 0.09]}>
      <planeGeometry args={[0.2, 0.6]} />
      <meshStandardMaterial color="#8FCBEA" roughness={0.6} />
    </mesh>
    <mesh position={[0, 0.05, 0.1]}>
      <boxGeometry args={[1.16, 0.05, 0.03]} />
      <meshStandardMaterial color={P.cream} roughness={0.7} />
    </mesh>
    <mesh position={[0, 0, 0.1]}>
      <boxGeometry args={[0.05, 1.4, 0.03]} />
      <meshStandardMaterial color={P.cream} roughness={0.7} />
    </mesh>
    <mesh position={[0, -0.82, 0.14]} castShadow>
      <boxGeometry args={[1.46, 0.08, 0.26]} />
      <meshStandardMaterial color={P.creamDeep} roughness={0.8} />
    </mesh>
    {/* a tiny potted cutting on the sill */}
    <mesh position={[-0.42, -0.7, 0.16]} castShadow>
      <cylinderGeometry args={[0.07, 0.055, 0.1, 16]} />
      <meshStandardMaterial color={P.coral} roughness={0.85} />
    </mesh>
    <mesh position={[-0.42, -0.6, 0.16]} scale={[1, 1.4, 0.5]}>
      <sphereGeometry args={[0.055, 14, 10]} />
      <meshStandardMaterial color={P.sage} roughness={0.9} />
    </mesh>
  </group>
)

const Armchair: React.FC = () => (
  <group position={[1.28, FLOOR_Y, -1.5]} rotation={[0, -0.46, 0]}>
    <mesh position={[0, 0.3, 0]} castShadow receiveShadow>
      <boxGeometry args={[1.12, 0.24, 0.86]} />
      <meshStandardMaterial color={P.sky} roughness={0.88} />
    </mesh>
    <mesh position={[0, 0.62, -0.35]} rotation={[-0.14, 0, 0]} castShadow receiveShadow>
      <boxGeometry args={[1.12, 0.6, 0.2]} />
      <meshStandardMaterial color={P.skyDeep} roughness={0.88} />
    </mesh>
    {[-0.52, 0.52].map((x) => (
      <mesh key={x} position={[x, 0.42, 0.02]} castShadow receiveShadow>
        <boxGeometry args={[0.14, 0.44, 0.9]} />
        <meshStandardMaterial color={P.skyDeep} roughness={0.88} />
      </mesh>
    ))}
    {/* cushions */}
    <mesh position={[-0.24, 0.56, -0.24]} rotation={[0.22, 0, 0.1]} castShadow>
      <boxGeometry args={[0.3, 0.3, 0.1]} />
      <meshStandardMaterial color={P.peachSoft} roughness={0.95} />
    </mesh>
    <mesh position={[0.28, 0.54, -0.22]} rotation={[0.18, 0, -0.12]} castShadow>
      <boxGeometry args={[0.28, 0.28, 0.1]} />
      <meshStandardMaterial color={P.yellowSoft} roughness={0.95} />
    </mesh>
    {[
      [-0.46, 0.33],
      [0.46, 0.33],
      [-0.46, -0.33],
      [0.46, -0.33],
    ].map(([x, z]) => (
      <mesh key={`${x}-${z}`} position={[x, 0.09, z]} castShadow>
        <cylinderGeometry args={[0.032, 0.026, 0.18, 10]} />
        <meshStandardMaterial color={P.woodDeep} roughness={0.6} />
      </mesh>
    ))}
    {/* folded throw over the arm */}
    <mesh position={[0.5, 0.62, 0.1]} rotation={[0, 0.1, 0]} castShadow>
      <boxGeometry args={[0.22, 0.06, 0.5]} />
      <meshStandardMaterial color={P.cream} roughness={0.95} />
    </mesh>
  </group>
)

const SideTable: React.FC<{ phoneLit: number; phoneGlow: number }> = ({ phoneLit, phoneGlow }) => {
  return (
    <group position={[0.92, FLOOR_Y, 0.82]} rotation={[0, -0.34, 0]} scale={0.92}>
      <mesh position={[0, 0.52, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.33, 0.33, 0.055, 36]} />
        <meshStandardMaterial color={P.wood} roughness={0.62} />
      </mesh>
      <mesh position={[0, 0.27, 0]} castShadow>
        <cylinderGeometry args={[0.038, 0.038, 0.52, 14]} />
        <meshStandardMaterial color={P.woodDeep} roughness={0.6} />
      </mesh>
      <mesh position={[0, 0.03, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.18, 0.2, 0.05, 24]} />
        <meshStandardMaterial color={P.woodDeep} roughness={0.6} />
      </mesh>

      {/* ---------------- phone, propped up in a little stand ---------------- */}
      <group position={[-0.01, 0.58, 0.05]} rotation={[-0.34, 0.2, 0]}>
        <mesh castShadow receiveShadow>
          <boxGeometry args={[0.21, 0.42, 0.014]} />
          <meshStandardMaterial color="#4A4160" roughness={0.45} />
        </mesh>
        {/* screen */}
        <mesh position={[0, 0, 0.0085]}>
          <planeGeometry args={[0.182, 0.386]} />
          <meshStandardMaterial
            color={phoneLit > 0.02 ? "#FFF4DA" : "#2A2538"}
            emissive={phoneLit > 0.02 ? "#FFE9BE" : "#000000"}
            emissiveIntensity={phoneLit * 0.5}
            roughness={0.3}
          />
        </mesh>
        {/* notification card, appears with the light */}
        {phoneLit > 0.01 && (
          <group position={[0, 0.08, 0.013]}>
            <mesh>
              <planeGeometry args={[0.15, 0.1]} />
              <meshStandardMaterial
                color="#FFD9C8"
                emissive="#FFD9C8"
                emissiveIntensity={0.5 * phoneLit}
                transparent
                opacity={Math.min(1, phoneLit * 1.5)}
              />
            </mesh>
            <mesh position={[-0.048, 0.026, 0.002]}>
              <circleGeometry args={[0.022, 20]} />
              <meshStandardMaterial
                color={P.coral}
                emissive={P.coral}
                emissiveIntensity={0.8 * phoneLit}
                transparent
                opacity={Math.min(1, phoneLit * 1.5)}
              />
            </mesh>
            {[
              { y: 0.026, w: 0.062 },
              { y: 0.0, w: 0.05 },
              { y: -0.026, w: 0.07 },
            ].map((line) => (
              <mesh key={line.y} position={[0.026, line.y, 0.002]}>
                <planeGeometry args={[line.w, 0.012]} />
                <meshStandardMaterial
                  color="#8C7BA8"
                  emissive="#8C7BA8"
                  emissiveIntensity={0.25 * phoneLit}
                  transparent
                  opacity={Math.min(1, phoneLit * 1.5)}
                />
              </mesh>
            ))}
          </group>
        )}
      </group>
      {/* little stand: a wedge behind the phone */}
      <mesh position={[0, 0.62, -0.02]} rotation={[0.5, 0, 0]} castShadow>
        <boxGeometry args={[0.14, 0.1, 0.012]} />
        <meshStandardMaterial color={P.woodDeep} roughness={0.7} />
      </mesh>
      {/* the phone throws a warm pool of light */}
      <pointLight
        position={[0, 0.66, 0.16]}
        color={P.screenOn}
        intensity={phoneGlow * 2.6}
        distance={2.0}
        decay={2}
      />
      {/* a mug, for cosiness */}
      <mesh position={[0.19, 0.575, -0.09]} castShadow>
        <cylinderGeometry args={[0.045, 0.04, 0.085, 20]} />
        <meshStandardMaterial color={P.yellow} roughness={0.7} />
      </mesh>
    </group>
  )
}

const Plant: React.FC = () => {
  const frame = useCurrentFrame()
  const sway = Math.sin(frame * 0.045) * 0.05
  return (
    <group position={[-1.16, FLOOR_Y, 0.5]}>
      <mesh position={[0, 0.16, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.19, 0.15, 0.32, 22]} />
        <meshStandardMaterial color={P.coral} roughness={0.85} />
      </mesh>
      <mesh position={[0, 0.325, 0]} castShadow>
        <cylinderGeometry args={[0.205, 0.2, 0.045, 22]} />
        <meshStandardMaterial color={P.coralDeep} roughness={0.85} />
      </mesh>
      {[-0.5, -0.16, 0.18, 0.52].map((spread, i) => {
        const h = 0.5 + (i % 2) * 0.16
        return (
          <group key={spread} rotation={[0, 0, spread * 0.4 + sway * (i % 2 ? 1 : -1)]}>
            <mesh position={[0, 0.34 + h / 2, 0]} castShadow>
              <cylinderGeometry args={[0.009, 0.012, h, 8]} />
              <meshStandardMaterial color={P.sageDeep} roughness={0.9} />
            </mesh>
            <mesh
              position={[0, 0.34 + h * 0.84, 0.02]}
              rotation={[0.5, spread * 0.5, spread * 0.7]}
              scale={[1, 1.5, 0.3]}
              castShadow
            >
              <sphereGeometry args={[0.085, 16, 12]} />
              <meshStandardMaterial color={i % 2 ? P.sage : P.sageDeep} roughness={0.9} />
            </mesh>
            <mesh
              position={[0, 0.34 + h * 0.5, -0.03]}
              rotation={[-0.4, -spread * 0.4, -spread * 0.5]}
              scale={[1, 1.3, 0.3]}
              castShadow
            >
              <sphereGeometry args={[0.07, 16, 12]} />
              <meshStandardMaterial color={P.sage} roughness={0.9} />
            </mesh>
          </group>
        )
      })}
    </group>
  )
}

const Shelf: React.FC = () => (
  <group position={[-1.62, 1.35, WALL_Z + 0.12]}>
    <mesh castShadow receiveShadow>
      <boxGeometry args={[0.9, 0.05, 0.22]} />
      <meshStandardMaterial color={P.creamDeep} roughness={0.8} />
    </mesh>
    <mesh position={[-0.26, 0.14, 0]} castShadow>
      <boxGeometry args={[0.07, 0.24, 0.14]} />
      <meshStandardMaterial color={P.coral} roughness={0.85} />
    </mesh>
    <mesh position={[-0.17, 0.12, 0.01]} castShadow>
      <boxGeometry args={[0.055, 0.2, 0.13]} />
      <meshStandardMaterial color={P.yellow} roughness={0.85} />
    </mesh>
    <mesh position={[-0.09, 0.15, -0.01]} castShadow>
      <boxGeometry args={[0.075, 0.28, 0.13]} />
      <meshStandardMaterial color={P.skyDeep} roughness={0.85} />
    </mesh>
    <mesh position={[0.3, 0.13, 0]} castShadow>
      <sphereGeometry args={[0.1, 20, 16]} />
      <meshStandardMaterial color={P.lavender} roughness={0.6} />
    </mesh>
  </group>
)

const Lamp: React.FC = () => (
  <group position={[0.1, 2.12, -1.05]}>
    <mesh position={[0, 0.72, 0]}>
      <cylinderGeometry args={[0.008, 0.008, 1.4, 8]} />
      <meshStandardMaterial color={P.creamDeep} />
    </mesh>
    <mesh position={[0, -0.02, 0]} castShadow>
      <coneGeometry args={[0.28, 0.26, 32, 1, true]} />
      <meshStandardMaterial color={P.peach} roughness={0.75} side={2} />
    </mesh>
    <mesh position={[0, -0.1, 0]}>
      <sphereGeometry args={[0.06, 20, 16]} />
      <meshStandardMaterial color={P.yellowSoft} emissive={P.yellowSoft} emissiveIntensity={1.1} />
    </mesh>
    <pointLight position={[0, -0.18, 0]} color="#FFE6C6" intensity={2.2} distance={4.5} decay={1.8} />
  </group>
)

/* ------------------------------------------------------------------ room */

export interface RoomProps {
  /** 0 = room asleep, 1 = fully established */
  establish: number
  /** 0 = phone dark, 1 = notification lit */
  phoneLit: number
  /** 0..1 warm spill from the phone */
  phoneGlow: number
}

export const Room: React.FC<RoomProps> = ({ establish, phoneLit, phoneGlow }) => {
  const frame = useCurrentFrame()
  const lightUp = mix(frame, [0, 45], [0, 1], easeInOut)
  const rise = mix(frame, [0, 60], [0.22, 0], easeOut)

  return (
    <group>
      <BackWall />
      <group position={[0, rise, 0]}>
        <Floor />
        <Window />
        <Armchair />
        <SideTable phoneLit={phoneLit} phoneGlow={phoneGlow} />
        <Plant />
        <Shelf />
        <Lamp />
      </group>

      {/* --------- identical lighting for both Eli versions --------- */}
      <ambientLight intensity={0.42 * lightUp + 0.16} color="#F1E9FF" />
      <hemisphereLight args={["#FFF2E0", "#C6B2E4", 0.85 * lightUp]} />
      {/* key: soft warm, upper left, soft shadows */}
      <directionalLight
        position={[-2.6, 4.2, 3.6]}
        intensity={1.35 * (0.3 + 0.7 * lightUp)}
        color="#FFF1E0"
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-left={-4}
        shadow-camera-right={4}
        shadow-camera-top={4}
        shadow-camera-bottom={-3}
        shadow-camera-near={0.5}
        shadow-camera-far={18}
        shadow-bias={-0.0005}
        shadow-normalBias={0.02}
        shadow-radius={4}
      />
      {/* fill: cool bounce from the window side */}
      <directionalLight position={[-3.4, 1.2, -0.6]} intensity={0.42 * lightUp} color="#D6EBFB" />
      {/* rim: separates the character from the wall */}
      <pointLight
        position={[1.1, 1.0, -2.0]}
        intensity={1.5 * lightUp}
        color="#E3CFFF"
        distance={6}
        decay={2}
      />
      {/* warm bounce off the lit phone */}
      <pointLight
        position={[0.85, -0.2, 1.5]}
        color="#FFE8BE"
        intensity={phoneGlow * 1.8 * (0.7 + 0.3 * Math.sin(frame * 0.09))}
        distance={2.6}
        decay={2}
      />
    </group>
  )
}

/* ------------------------------------------------- camera (shared, fixed) */

export const CAMERA = {
  fov: 42,
  /**
   * Tiny deterministic drift so the frame never feels like a dead photo.
   * Both compositions read this exact function, so the framing is identical.
   */
  position: (frame: number): [number, number, number] => [
    0,
    0.56 + Math.sin(frame * 0.012) * 0.008,
    6.45 - mix(frame, [0, 300], [0, 0.12], easeInOut),
  ],
  /** slight downward tilt, radians */
  pitch: -0.03,
}
