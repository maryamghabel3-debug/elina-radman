import { registerRoot, Composition } from "remotion"
import { Scene } from "./BasheV3"
import "./global.css"

registerRoot(() => (
  <Composition
    id="BasheV3"
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={40 * 30}
    component={Scene}
  />
))
