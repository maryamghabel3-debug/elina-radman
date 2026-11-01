import { registerRoot, Composition } from "remotion"
import { Probe, W, H, FPS, DURATION_S } from "./Probe"

// Separate entry point so probing never disturbs the Bashe compositions.
registerRoot(() => (
  <Composition id="ThreeProbe" width={W} height={H} fps={FPS} durationInFrames={DURATION_S * FPS} component={Probe} />
))
