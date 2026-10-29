import { registerRoot, Composition } from "remotion"
import { Scene as BasheScene, W as BasheW, H as BasheH, FPS as BasheFPS, DURATION_S as BasheDur } from "./BasheV3"
import { ContactSheet, W as SheetW, H as SheetH } from "./ContactSheet"
import "./global.css"

registerRoot(() => (
  <>
    <Composition
      id="BasheV3"
      width={BasheW}
      height={BasheH}
      fps={BasheFPS}
      durationInFrames={BasheDur * BasheFPS}
      component={BasheScene}
    />
    <Composition
      id="ContactSheet"
      width={SheetW}
      height={SheetH}
      fps={BasheFPS}
      durationInFrames={1}
      component={ContactSheet}
    />
  </>
))
