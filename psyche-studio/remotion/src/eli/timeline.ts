/**
 * Deterministic animation helpers.
 *
 * Every motion in both prototypes is a pure function of the Remotion frame
 * number. No clock, no Math.random, no useFrame: the same frame always
 * produces the same picture, which is what makes the render reproducible.
 */

export const clamp01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x)

export const lerp = (a: number, b: number, t: number) => a + (b - a) * t

/** Remotion-style interpolation with clamping. */
export const mix = (
  input: number,
  inputRange: [number, number],
  outputRange: [number, number],
  easing?: (t: number) => number,
) => {
  const [inMin, inMax] = inputRange
  const span = inMax - inMin
  const raw = span === 0 ? 1 : clamp01((input - inMin) / span)
  const eased = easing ? easing(raw) : raw
  return lerp(outputRange[0], outputRange[1], eased)
}

/** Ease in/out cubic — the house easing for entrances and settles. */
export const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2)
/** Ease out cubic — arrivals. */
export const easeOut = (t: number) => 1 - Math.pow(1 - t, 3)
/** Ease in cubic — departures. */
export const easeIn = (t: number) => t * t * t
/** Back-out — a soft overshoot, used for reaction pops. */
export const easeOutBack = (t: number) => {
  const c1 = 1.70158
  const c3 = c1 + 1
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2)
}

/** A single symmetric bump: 0 -> 1 -> 0, useful for blinks and pops. */
export const pulse = (input: number, center: number, halfWidth: number, easing = easeInOut) => {
  const rise = mix(input, [center - halfWidth, center], [0, 1], easing)
  const fall = mix(input, [center, center + halfWidth], [0, 1], easing)
  return rise * (1 - fall)
}

/** Springy settle in [0,1] driven by time in seconds. */
export const springIn = (tSeconds: number, freq = 2.2, damping = 4.2) => {
  const t = Math.max(0, tSeconds)
  return 1 - Math.exp(-damping * t) * Math.cos(freq * Math.PI * t * 2)
}

export interface Timeline {
  fps: number
  /** seconds */
  secureRoom: [number, number]
  enter: [number, number]
  phoneOn: [number, number]
  turnToPhone: [number, number]
  curiosityPeak: [number, number]
  thoughtsEmerge: [number, number]
  thoughtsOrbit: [number, number]
  thoughtsSettle: [number, number]
  finalPose: [number, number]
  end: number
}

export const SECONDS = 10

/** The one shared event clock. Both compositions read exactly this. */
export const TIMELINE: Timeline = {
  fps: 30,
  secureRoom: [0, 2],
  enter: [0.15, 1.9],
  phoneOn: [2.3, 2.75],
  turnToPhone: [2.55, 3.6],
  curiosityPeak: [3.4, 4.8],
  thoughtsEmerge: [5.0, 6.1],
  thoughtsOrbit: [5.9, 7.6],
  thoughtsSettle: [7.7, 8.7],
  finalPose: [8.3, 9.2],
  end: SECONDS,
}

/**
 * Voice-over beats are the same content for both versions, so the reaction
 * logic can be shared while the visuals differ.
 */
export const BEAT = {
  curiousEyesUp: 3.3,
  reachMax: 4.3,
  blinkAt: 1.35,
  blinkAgain: 6.9,
} as const
