import { AbsoluteFill, useCurrentFrame } from "remotion"
import { ThreeCanvas } from "@remotion/three"
import { NeutralToneMapping } from "three"
import { EliPalette } from "./palette"
import { CAMERA2, Room2 } from "./Room2"
import { CloudEli2 } from "./CloudEli2"
import { Overlays2, W2, H2 } from "./Overlays2"
import { eliV2Pose } from "./pose2"

/**
 * V2 scene shell. One room, one camera, one timeline — rendered twice with
 * different palettes so the user can pick a direction.
 *
 * Renderer settings are explicit here rather than inherited, because the
 * technical investigation showed the defaults were part of the washout:
 *   - Neutral tone mapping (measured: +6 % saturation vs ACES, no clipping
 *     loss vs none)
 *   - no fog at all (V1's fog was a literal milky layer over the background)
 *   - shadows on
 * 10 s · 1080×1920 · 30 fps · silent: no <Audio>, no audio stream.
 */

export const V2Component: React.FC<{ paletteId: EliPalette["id"]; pal: EliPalette }> = ({ pal }) => {
  const frame = useCurrentFrame()
  const pose = eliV2Pose(frame)
  const camera = CAMERA2.base(frame, pose.pushIn)

  return (
    <AbsoluteFill style={{ backgroundColor: pal.wallSide }}>
      <ThreeCanvas
        width={W2}
        height={H2}
        shadows
        camera={{
          position: camera,
          rotation: [CAMERA2.pitch, 0, 0],
          fov: CAMERA2.fov,
          near: 0.1,
          far: 60,
        }}
        gl={{ antialias: true, alpha: false }}
        style={{ position: "absolute", inset: 0 }}
        onCreated={({ gl }) => {
          gl.toneMapping = NeutralToneMapping
          gl.toneMappingExposure = 1.05
        }}
      >
        <color attach="background" args={[pal.wallSide]} />
        <Room2 pal={pal} phoneLit={pose.notif} establish={1} />
        <CloudEli2 pal={pal} pose={pose} />
      </ThreeCanvas>

      {/* DOM layer: Persian notification + big readable thought marks, both
          positioned by projecting the real 3D camera */}
      <Overlays2 pal={pal} pose={pose} camera={camera} />
    </AbsoluteFill>
  )
}
