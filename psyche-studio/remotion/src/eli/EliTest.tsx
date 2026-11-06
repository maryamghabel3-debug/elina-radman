import { AbsoluteFill, useCurrentFrame } from "remotion"
import { ThreeCanvas } from "@remotion/three"
import { CAMERA, Room } from "./Room"
import { CloudEli, CloudThoughts } from "./CloudEli"
import { LinesEli, LineThoughts } from "./LinesEli"
import { PALETTE as P } from "./palette"
import { TIMELINE, mix, easeInOut } from "./timeline"

/**
 * Both Eli prototypes live here, on top of the identical Room component and
 * the identical pose function, so a reviewer can flip between the two files
 * and see only the character change.
 *
 * 10 s · 1080×1920 · 30 fps · silent by design (no <Audio>, no audio track).
 */

export const W = 1080
export const H = 1920
export const FPS = TIMELINE.fps
export const DURATION_FRAMES = TIMELINE.end * FPS

/** Frame-driven state shared by both versions. */
const useSharedSceneState = () => {
  const frame = useCurrentFrame()

  const phoneLit = mix(frame, [TIMELINE.phoneOn[0] * FPS, TIMELINE.phoneOn[1] * FPS], [0, 1], easeInOut)
  // a small deterministic flicker right as the notification lands
  const flicker =
    frame > TIMELINE.phoneOn[0] * FPS && frame < TIMELINE.phoneOn[0] * FPS + 10
      ? 0.75 + 0.25 * Math.sin(frame * 2.1)
      : 1
  const establish = mix(frame, [0, 2 * FPS], [0, 1], easeInOut)

  return {
    frame,
    phoneLit: phoneLit * flicker,
    establish,
    camera: CAMERA.position(frame),
  }
}

const SceneShell: React.FC<{ children: React.ReactNode; camera: [number, number, number] }> = ({
  children,
  camera,
}) => (
  <AbsoluteFill style={{ backgroundColor: P.wallLeft }}>
    <ThreeCanvas
      width={W}
      height={H}
      shadows
      camera={{
        position: camera,
        rotation: [CAMERA.pitch, 0, 0],
        fov: CAMERA.fov,
        near: 0.1,
        far: 60,
      }}
      gl={{ antialias: true, alpha: false }}
      style={{ position: "absolute", inset: 0 }}
      onCreated={({ gl }) => {
        gl.setClearColor(P.ceiling)
      }}
    >
      {children}
    </ThreeCanvas>
  </AbsoluteFill>
)

/* ------------------------------------------------- Version A: cloud */

export const EliCloudTest: React.FC = () => {
  const { phoneLit, establish, camera } = useSharedSceneState()
  return (
    <SceneShell camera={camera}>
      <color attach="background" args={[P.ceiling]} />
      <fog attach="fog" args={[P.ceiling, 12, 26]} />
      <Room establish={establish} phoneLit={phoneLit} phoneGlow={phoneLit} />
      <CloudEli phoneLit={phoneLit} />
      <CloudThoughts emerge={1} orbit={1} settle={1} />
    </SceneShell>
  )
}

/* ------------------------------------------------- Version B: lines */

export const EliLinesTest: React.FC = () => {
  const { phoneLit, establish, camera } = useSharedSceneState()
  return (
    <SceneShell camera={camera}>
      <color attach="background" args={[P.ceiling]} />
      <fog attach="fog" args={[P.ceiling, 12, 26]} />
      <Room establish={establish} phoneLit={phoneLit} phoneGlow={phoneLit} />
      <LinesEli phoneLit={phoneLit} />
      <LineThoughts />
    </SceneShell>
  )
}
