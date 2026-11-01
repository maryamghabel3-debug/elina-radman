import { BEAT, TIMELINE, easeInOut, easeOut, easeOutBack, mix, pulse } from "./timeline"

/**
 * One pose, computed once, consumed by both characters.
 *
 * Keeping this in a single pure function is what guarantees that Eli Cloud and
 * Eli Lines hit exactly the same beats: the entrance, the turn to the phone,
 * the curiosity peak, the thought-shape window and the final pose are all
 * derived from the frame number here and nowhere else.
 */
export interface EliPose {
  /** seconds */
  t: number
  /** 0..1 entrance progress (overshoots slightly, use with care) */
  enter: number
  /** world-space vertical entrance offset, metres */
  enterOffset: number
  /** world-space horizontal entrance offset, metres */
  enterDriftX: number
  /** 0..1 how far the head has turned to the phone */
  turn: number
  /** -1..1 horizontal gaze */
  lookX: number
  /** -1..1 vertical gaze */
  lookY: number
  /** 0 open .. 1 closed */
  blink: number
  /** eye scale multiplier */
  widen: number
  /** 0..1 happy-squint / smile amount */
  joy: number
  /** 0..1 surprise pop right after the screen lights */
  pop: number
  /** 0..1 reaching toward the phone (and back down again) */
  reach: number
  /** passive float offset, metres */
  float: number
  /** 0..1 how much of the thought-shape sequence has played */
  thoughts: number
  /** 0..1 how settled the thought shapes are */
  settle: number
}

export const eliPose = (frame: number): EliPose => {
  const f = TIMELINE.fps
  const t = frame / f

  const enter = mix(frame, [TIMELINE.enter[0] * f, TIMELINE.enter[1] * f], [0, 1], easeOutBack)
  const enterOffset = mix(frame, [TIMELINE.enter[0] * f, TIMELINE.enter[1] * f], [4.4, 0], easeOut)
  const enterDriftX = mix(frame, [TIMELINE.enter[0] * f, TIMELINE.enter[1] * f], [-1.5, 0], easeOut)

  const turn = mix(frame, [TIMELINE.turnToPhone[0] * f, TIMELINE.turnToPhone[1] * f], [0, 1], easeInOut)

  const pop = Math.sin(mix(frame, [TIMELINE.phoneOn[0] * f, TIMELINE.phoneOn[1] * f + 30], [0, Math.PI], (x) => x))

  const curious = mix(
    frame,
    [TIMELINE.curiosityPeak[0] * f, TIMELINE.curiosityPeak[1] * f],
    [0, 1],
    easeInOut,
  )
  const joy = mix(frame, [TIMELINE.finalPose[0] * f, TIMELINE.finalPose[1] * f], [0, 1], easeInOut)

  const reachOut = mix(frame, [3.5 * f, 4.7 * f], [0, 1], easeInOut)
  const reachBack = mix(frame, [7.6 * f, 8.6 * f], [0, 1], easeInOut)

  const blinkA = pulse(frame, BEAT.blinkAt * f, 0.13 * f)
  const blinkB = pulse(frame, BEAT.blinkAgain * f, 0.13 * f)

  const thoughts = mix(
    frame,
    [TIMELINE.thoughtsEmerge[0] * f, TIMELINE.thoughtsEmerge[1] * f],
    [0, 1],
    easeInOut,
  )
  const settle = mix(frame, [TIMELINE.thoughtsSettle[0] * f, TIMELINE.thoughtsSettle[1] * f], [0, 1], easeInOut)

  return {
    t,
    enter,
    enterOffset,
    enterDriftX,
    turn,
    lookX: turn * 0.9,
    lookY: 0.15 + curious * 0.4 - joy * 0.05,
    blink: Math.max(blinkA, blinkB),
    widen: 1 + curious * 0.16 + Math.max(0, pop) * 0.14 - joy * 0.04,
    joy,
    pop: Math.max(0, pop),
    reach: reachOut * (1 - reachBack),
    float: Math.sin(t * 1.55) * 0.085,
    thoughts,
    settle,
  }
}
