import { AbsoluteFill } from "remotion"
import { ThreeCanvas } from "@remotion/three"
import { ACESFilmicToneMapping, AgXToneMapping, NeutralToneMapping, NoToneMapping, ToneMapping } from "three"
import { PALETTE as P } from "./palette"

/**
 * V2 diagnostic: is the washed-out V1 look partly a renderer problem?
 *
 * Four tiles, identical geometry and lights, only the tone mapping differs.
 * Rendered once as a still and measured with a saturation/contrast script.
 *
 *   npx remotion still src/eli/tonemap-probe-entry.tsx ToneMapProbe out/probe/tonemap.png
 */
const TILE_W = 540
const TILE_H = 480

type Variant = {
  label: string
  toneMapping: ToneMapping
  exposure: number
}

const VARIANTS: Variant[] = [
  { label: "ACESFilmic (R3F default)", toneMapping: ACESFilmicToneMapping, exposure: 1 },
  { label: "NoToneMapping", toneMapping: NoToneMapping, exposure: 1 },
  { label: "AgXToneMapping", toneMapping: AgXToneMapping, exposure: 1 },
  { label: "NeutralToneMapping", toneMapping: NeutralToneMapping, exposure: 1.05 },
]

const Tile: React.FC<{ v: Variant }> = ({ v }) => (
  <div style={{ width: TILE_W, height: TILE_H, position: "relative", overflow: "hidden" }}>
    <ThreeCanvas
      width={TILE_W}
      height={TILE_H}
      gl={{ antialias: true }}
      camera={{ position: [0, 0.2, 4.2], fov: 40 }}
      onCreated={({ gl }) => {
        gl.toneMapping = v.toneMapping
        gl.toneMappingExposure = v.exposure
      }}
    >
      <color attach="background" args={["#8C7BB0"]} />
      {/* vivid subject on a mid background: the exact situation under test */}
      <ambientLight intensity={0.55} />
      <directionalLight position={[-2, 3, 3]} intensity={1.5} color="#FFF1E0" />
      <mesh position={[-0.55, 0, 0]}>
        <sphereGeometry args={[0.72, 48, 32]} />
        <meshStandardMaterial color="#7C3AED" roughness={0.55} />
      </mesh>
      <mesh position={[0.85, 0.1, 0.2]}>
        <boxGeometry args={[0.7, 0.7, 0.7]} />
        <meshStandardMaterial color="#FFC93C" roughness={0.6} />
      </mesh>
      <mesh position={[0.05, -0.75, -0.2]}>
        <boxGeometry args={[2.6, 0.06, 1.2]} />
        <meshStandardMaterial color="#EFE3D2" roughness={0.9} />
      </mesh>
    </ThreeCanvas>
    <div
      style={{
        position: "absolute",
        bottom: 6,
        left: 8,
        fontFamily: "sans-serif",
        fontSize: 17,
        color: "#fff",
        background: "rgba(0,0,0,0.55)",
        padding: "2px 8px",
        borderRadius: 5,
      }}
    >
      {v.label}
    </div>
  </div>
)

export const ToneMapProbe: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: P.ink, display: "flex", flexWrap: "wrap" }}>
    {VARIANTS.map((v) => (
      <Tile key={v.label} v={v} />
    ))}
  </AbsoluteFill>
)

export const PROBE_W = TILE_W * 2
export const PROBE_H = TILE_H * 2
