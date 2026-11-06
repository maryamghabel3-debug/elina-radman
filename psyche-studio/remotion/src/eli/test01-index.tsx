import {registerRoot, Composition} from "remotion";
import {EliElinaTest01} from "./test01";
registerRoot(()=><Composition id="EliElinaTest01" width={1080} height={1920} fps={30} durationInFrames={360} component={EliElinaTest01} />);
