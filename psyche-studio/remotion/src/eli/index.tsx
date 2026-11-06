import { registerRoot, Composition } from "remotion"
import { EliCloudTest, EliLinesTest, W, H, FPS, DURATION_FRAMES } from "./EliTest"

/**
 * Entry point for the two Eli 3D prototypes. Kept separate from src/index.tsx
 * so the existing BasheV3 / ContactSheet compositions are untouched.
 */
registerRoot(() => (
  <>
    <Composition
      id="EliCloudTest"
      width={W}
      height={H}
      fps={FPS}
      durationInFrames={DURATION_FRAMES}
      component={EliCloudTest}
    />
    <Composition
      id="EliLinesTest"
      width={W}
      height={H}
      fps={FPS}
      durationInFrames={DURATION_FRAMES}
      component={EliLinesTest}
    />
  </>
))
