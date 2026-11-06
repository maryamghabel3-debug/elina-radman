import { registerRoot, Composition } from "remotion"
import { PALETTES } from "./palette"
import { V2Component } from "./Eli2"
import { TIMELINE } from "../timeline"

/**
 * Two palette variants of the same Eli Cloud V2 scene:
 *   EliCloudV2Warm  — warm peach/coral/cream room, vivid violet Eli
 *   EliCloudV2Cool  — cool teal/mint room, vivid violet Eli
 *
 * Separate entry point; V1 and BasheV3 are untouched.
 */
export const V2_W = 1080
export const V2_H = 1920
export const V2_FPS = TIMELINE.fps
export const V2_FRAMES = TIMELINE.end * V2_FPS

registerRoot(() => (
  <>
    <Composition
      id="EliCloudV2Warm"
      width={V2_W}
      height={V2_H}
      fps={V2_FPS}
      durationInFrames={V2_FRAMES}
      component={() => <V2Component paletteId="warm" pal={PALETTES.warm} />}
    />
    <Composition
      id="EliCloudV2Cool"
      width={V2_W}
      height={V2_H}
      fps={V2_FPS}
      durationInFrames={V2_FRAMES}
      component={() => <V2Component paletteId="cool" pal={PALETTES.cool} />}
    />
  </>
))
