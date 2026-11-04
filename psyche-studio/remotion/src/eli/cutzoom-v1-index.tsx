import {registerRoot, Composition} from "remotion";
import {EliElinaCutzoomV1} from "./cutzoom-v1";

registerRoot(() => <Composition
  id="EliElinaCutzoomV1"
  width={1080}
  height={1920}
  fps={30}
  durationInFrames={360}
  component={EliElinaCutzoomV1}
/>);
