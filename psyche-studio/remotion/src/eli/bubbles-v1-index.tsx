import {registerRoot, Composition} from "remotion";
import {EliElinaBubblesV1} from "./bubbles-v1";

registerRoot(() => <Composition
  id="EliElinaBubblesV1"
  width={1080}
  height={1920}
  fps={30}
  durationInFrames={360}
  component={EliElinaBubblesV1}
/>);
