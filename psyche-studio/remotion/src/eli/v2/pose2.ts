import { PerspectiveCamera, Vector3 } from "three"
import { TIMELINE, clamp01, easeInOut, easeOut, mix, pulse } from "../timeline"

/**
 * V2 timeline. Same 10-second clock as V1 (TIMELINE is imported, not copied),
 * but the emotional arc is now explicit and measurable:
 *
 *     0 – 2.5 s   CALM        settles into the room
 *     2.5 – 5 s   CURIOUS     notification lands, turns, leans in, eyes widen
 *     5 – 8 s   WORRIED      thought shapes swarm, jitter, colour storms over
 *     8 – 10 s   RESOLVED     a strong, wide, bright final pose
 *
 * Every value is a pure function of the frame number.
 */

export type Expression = "calm" | "curious" | "worried" | "resolved"

export interface EliV2Pose {
  frame: number
  t: number
  expression: Expression
  /** 0..1 weights, useful for blending colour and face shapes */
  calm: number
  curious: number
  worried: number
  resolved: number

  enterX: number
  enterY: number

  float: number
  squash: number
  /** deterministic jitter, only grows while worried */
  jitterX: number
  jitterY: number
  jitterRot: number

  turn: number
  lookX: number
  lookY: number
  blink: number
  /** brow angle in radians: positive = inner ends raised (worried) */
  browAngle: number
  browLift: number
  /** 0..1 mouth width and openness */
  mouthWidth: number
  mouthOpen: number
  /** 0..1 eye scale */
  eyeOpen: number
  smile: number

  reach: number
  armSwing: number

  /** 0..1 how far the notification has appeared */
  notif: number
  /** 0..1 thought-shape sequence */
  thoughts: number
  /** 0..1 camera push-in on the notification beat */
  pushIn: number
}

const f = TIMELINE.fps

export const eliV2Pose = (frame: number): EliV2Pose => {
  const t = frame / f

  /* ---- expression weights ---- */
  const curious = mix(frame, [2.55 * f, 3.6 * f], [0, 1], easeInOut) *
    (1 - mix(frame, [5.0 * f, 5.9 * f], [0, 1], easeInOut) * 0.35)
  const worried = mix(frame, [5.0 * f, 6.0 * f], [0, 1], easeInOut) *
    (1 - mix(frame, [8.0 * f, 8.8 * f], [0, 1], easeInOut))
  const resolved = mix(frame, [8.2 * f, 9.0 * f], [0, 1], easeOut)
  const calm = clamp01(1 - Math.max(curious, worried, resolved))

  const expression: Expression =
    resolved > 0.5 ? "resolved" : worried > 0.35 ? "worried" : curious > 0.35 ? "curious" : "calm"

  /* ---- entrance ---- */
  const enterX = mix(frame, [TIMELINE.enter[0] * f, TIMELINE.enter[1] * f], [-2.6, 0], easeOut)
  const enterY = mix(frame, [TIMELINE.enter[0] * f, TIMELINE.enter[1] * f], [4.6, 0], easeOut)

  /* ---- idle + jitter ---- */
  const float = Math.sin(t * 1.7) * 0.1 + Math.sin(t * 2.9 + 1.1) * 0.03
  const jitterAmp = worried * 0.055
  const jitterX = Math.sin(frame * 2.7) * jitterAmp + Math.sin(frame * 4.3 + 1.7) * jitterAmp * 0.6
  const jitterY = Math.cos(frame * 3.1) * jitterAmp * 0.8 + Math.sin(frame * 5.1) * jitterAmp * 0.4
  const jitterRot = Math.sin(frame * 2.3 + 0.7) * worried * 0.05

  /* ---- squash & stretch: exaggerated, especially when worried ---- */
  const squash =
    1 +
    Math.sin(t * 1.9 + 1.2) * 0.05 +
    worried * Math.sin(t * 6.5) * 0.075 +
    resolved * 0.06 -
    curious * 0.02

  /* ---- turn to the phone ---- */
  const turn = mix(frame, [TIMELINE.turnToPhone[0] * f, TIMELINE.turnToPhone[1] * f], [0, 1], easeInOut)

  const reachOut = mix(frame, [3.4 * f, 4.6 * f], [0, 1], easeInOut)
  const reachBack = mix(frame, [7.4 * f, 8.4 * f], [0, 1], easeInOut)
  const reach = reachOut * (1 - reachBack)

  /* ---- face ---- */
  const blink = Math.max(pulse(frame, 1.35 * f, 0.13 * f), pulse(frame, 6.9 * f, 0.12 * f))

  const eyeOpen = 1 + curious * 0.16 - worried * 0.18 + resolved * 0.02
  const browAngle = worried * 0.42 - curious * 0.1 + resolved * 0.16
  const browLift = curious * 0.05 + worried * 0.02 + resolved * 0.035
  const mouthWidth = 0.55 + curious * 0.22 - worried * 0.25 + resolved * 0.95
  const mouthOpen = curious * 0.12 + resolved * 0.12
  const smile = -worried * 0.75 + resolved * 1.15 + curious * 0.35

  /* ---- story beats ---- */
  const notif = mix(frame, [TIMELINE.phoneOn[0] * f, TIMELINE.phoneOn[1] * f], [0, 1], easeInOut)
  const thoughts = mix(frame, [TIMELINE.thoughtsEmerge[0] * f, TIMELINE.thoughtsEmerge[1] * f], [0, 1], easeInOut)

  /* ---- gentle camera push-in on the notification beat ---- */
  const pushIn =
    mix(frame, [2.2 * f, 4.2 * f], [0, 1], easeInOut) * 0.55 +
    mix(frame, [5.0 * f, 7.8 * f], [0, 1], easeInOut) * 0.45

  return {
    frame,
    t,
    expression,
    calm,
    curious,
    worried,
    resolved,
    enterX,
    enterY,
    float,
    squash,
    jitterX,
    jitterY,
    jitterRot,
    turn,
    lookX: turn * 0.85 + worried * 0.1 * Math.sin(frame * 1.7),
    lookY: curious * 0.35 - worried * 0.2 + resolved * 0.05,
    blink,
    browAngle,
    browLift,
    mouthWidth,
    mouthOpen,
    eyeOpen,
    smile,
    reach,
    armSwing: reach * 0.8 + resolved * 0.9,
    notif,
    thoughts,
    pushIn,
  }
}

/* ------------------------------------------------------- 3D -> 2D projection */

export interface CameraSpec {
  position: [number, number, number]
  pitch: number
  fov: number
}

/**
 * The DOM overlays (Persian notification text, thought marks) must sit exactly
 * on top of 3D positions. Rather than guess, project the 3D point through the
 * real camera maths and hand the CSS pixel position to the overlay layer.
 */
export const projectToFrame = (
  point: [number, number, number],
  camera: CameraSpec,
  width: number,
  height: number,
): { x: number; y: number; scale: number; visible: boolean } => {
  const cam = new PerspectiveCamera(camera.fov, width / height, 0.1, 60)
  cam.position.set(...camera.position)
  cam.rotation.set(camera.pitch, 0, 0)
  cam.updateMatrixWorld()

  const v = new Vector3(point[0], point[1], point[2]).project(cam)
  const x = ((v.x + 1) / 2) * width
  const y = ((1 - v.y) / 2) * height

  // how large a 1-unit object appears, so overlays scale with depth
  const distance = new Vector3(...camera.position).distanceTo(new Vector3(...point))
  const scale = (height / 2) / (Math.tan((camera.fov * Math.PI) / 360) * Math.max(0.2, distance))

  return { x, y, scale, visible: v.z < 1 }
}
