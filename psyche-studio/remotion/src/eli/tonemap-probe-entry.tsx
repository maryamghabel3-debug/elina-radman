import { registerRoot, Composition } from "remotion"
import { ToneMapProbe, PROBE_W, PROBE_H } from "./tonemap-probe"

registerRoot(() => (
  <Composition id="ToneMapProbe" width={PROBE_W} height={PROBE_H} fps={30} durationInFrames={1} component={ToneMapProbe} />
))
