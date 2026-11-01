import { useCurrentFrame, AbsoluteFill } from "remotion"
import { ThreeCanvas } from "@remotion/three"
import { useLayoutEffect } from "react"
import { MeshStandardMaterial } from "three"

/**
 * Minimal 3D probe: one spinning, lit box on a shaded floor plus a text overlay.
 * Purpose: prove that a real WebGL frame reaches the encoder before any
 * production work is invested. Render with:
 *   npx remotion still src/three-probe/index.tsx ThreeProbe out/probe.png
 */
export const W = 1080
export const H = 1920
export const FPS = 30
export const DURATION_S = 2

const Probe: React.FC = () => {
  const frame = useCurrentFrame()
  const t = frame / FPS

  return (
    <AbsoluteFill style={{ backgroundColor: "#EDE7F8" }}>
      <ThreeCanvas width={W} height={H} camera={{ position: [0, 1.6, 5], fov: 40 }} gl={{ antialias: true }}>
        <color attach="background" args={["#E9E3F7"]} />
        <ambientLight intensity={0.6} />
        <directionalLight position={[3, 6, 4]} intensity={1.4} castShadow />
        <mesh rotation={[0, t * 1.2, 0]} position={[0, 1.1, 0]} castShadow>
          <boxGeometry args={[1.2, 1.2, 1.2]} />
          <meshStandardMaterial color="#FF8A6B" roughness={0.35} metalness={0.05} />
        </mesh>
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
          <planeGeometry args={[30, 30]} />
          <meshStandardMaterial attach="material" color="#F7EFE3" />
        </mesh>
      </ThreeCanvas>
      <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 80 }}>
        <div style={{ fontFamily: "sans-serif", fontSize: 64, color: "#3B3355" }}>{`frame ${frame}`}</div>
      </AbsoluteFill>
    </AbsoluteFill>
  )
}

export { Probe }
