import {Composition, registerRoot} from "remotion";
import {EliElinaFullDraft} from "./full-draft";
import timing from "./full-draft-duration.json";

registerRoot(() => (
  <Composition
    id="EliElinaFullDraft"
    component={EliElinaFullDraft}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={timing.durationInFrames}
  />
));
