/**
 * V2 colour system — two palette variants of the same scene.
 *
 * Design rules (measured, not vibes):
 *  - Eli is a vivid VIOLET in both variants: the same character, two rooms.
 *  - The room is the complementary / triadic counterweight:
 *      warm variant -> deep coral-peach room,  yellow secondary accent
 *      cool variant -> deep teal room,          mint/cream secondary accent
 *  - Roughly 60 / 30 / 10 by area:
 *      60 %  room base (walls, floor — mid-to-deep value, never near-white)
 *      30 %  secondary surfaces (furniture, rugs, plant)
 *      10 %  accent (Eli's highlights, thought shapes, the notification)
 *  - Eli is the only object allowed to reach the top of the value range, so it
 *    is always the brightest and highest-contrast thing in frame.
 *
 * Values are real sRGB hexes at saturated mid-values. There are deliberately
 * NO near-white surfaces bigger than a highlight: V1 died of pastel-on-pastel.
 */

export interface EliPalette {
  id: "warm" | "cool"

  /* ---- room base (≈60 % of the frame) ---- */
  wallBack: string
  wallUpper: string
  wallSide: string
  wallTrim: string
  floor: string
  floorDeep: string
  skirting: string

  /* ---- secondary surfaces (≈30 %) ---- */
  sofa: string
  sofaDeep: string
  sofaCushion: string
  rug: string
  rugRing: string
  tableTop: string
  tableLeg: string
  plantPot: string
  plantLeaf: string
  plantLeafDeep: string
  shelf: string
  shelfProp: string
  window: string
  windowGlow: string
  lampShade: string
  lampGlow: string

  /* ---- Eli: the vivid violet subject (shared by both variants) ---- */
  eliCore: string
  eliMid: string
  eliLight: string
  eliDeepShade: string
  eliRim: string
  /** worried / overthinking tint — slightly darker and stormier */
  eliWorried: string
  eliBlush: string

  /* ---- accent (≈10 %) ---- */
  accent: string
  accentSoft: string
  thoughtPositive: string
  thoughtWorried: string
  thoughtBubble: string

  /* ---- face ---- */
  eyeDark: string
  eyeIris: string
  mouth: string

  /* ---- phone ---- */
  phoneBody: string
  phoneScreenOn: string
  phoneScreenOff: string
  bubbleFill: string
  bubbleText: string

  /* ---- lighting ---- */
  keyLight: string
  fillLight: string
  rimLight: string
  ambientGround: string
  shadowTint: string
}

const ELI = {
  eliCore: "#8B3DF5", // vivid violet — the subject
  eliMid: "#A766F7",
  eliLight: "#D2B6FF",
  eliDeepShade: "#4C1D95",
  eliRim: "#E9D5FF",
  eliWorried: "#5B3E8F", // stormier, slightly desaturated
  eliBlush: "#FF8FA3",
  eyeDark: "#20122E",
  eyeIris: "#B98CF5",
  mouth: "#2B1B3D",
} as const

/** WARM — peach / coral / cream room, violet Eli, sunny-yellow accent */
export const WARM: EliPalette = {
  id: "warm",

  wallBack: "#8E3320",
  wallUpper: "#A8442A",
  wallSide: "#6B2517",
  wallTrim: "#F0C39B",
  floor: "#6E3A22",
  floorDeep: "#522913",
  skirting: "#F2C6A4",

  sofa: "#7A2C19",
  sofaDeep: "#5C1F11",
  sofaCushion: "#FFB58F",
  rug: "#4E1B0E",
  rugRing: "#FFC93C",
  tableTop: "#C9976C",
  tableLeg: "#A66C42",
  plantPot: "#FF8A5C",
  plantLeaf: "#3E7C59",
  plantLeafDeep: "#2C5C42",
  shelf: "#A66C42",
  shelfProp: "#FFC93C",
  window: "#FFE3B0",
  windowGlow: "#FFF3D6",
  lampShade: "#F7B267",
  lampGlow: "#FFE0A3",

  ...ELI,

  accent: "#FFC93C", // sunny yellow — 10 %
  accentSoft: "#FFE08A",
  thoughtPositive: "#FFC93C",
  thoughtWorried: "#3DDC97",
  thoughtBubble: "#FFF4E0",

  phoneBody: "#2A2036",
  phoneScreenOn: "#FFF6E2",
  phoneScreenOff: "#3B3050",
  bubbleFill: "#FFFFFF",
  bubbleText: "#2A2036",

  keyLight: "#FFEFD6",
  fillLight: "#FFB59A",
  rimLight: "#FFF2C2",
  ambientGround: "#7A3A2A",
  shadowTint: "#5A2A1E",
}

/** COOL — teal / mint / deep-blue room, violet Eli, coral accent */
export const COOL: EliPalette = {
  id: "cool",

  wallBack: "#17565D",
  wallUpper: "#1E6B73",
  wallSide: "#0E3B41",
  wallTrim: "#8FE3D2",
  floor: "#182C39",
  floorDeep: "#152936",
  skirting: "#7FD8C8",

  sofa: "#0F4C55",
  sofaDeep: "#0A353C",
  sofaCushion: "#7FD8C8",
  rug: "#0A2C36",
  rugRing: "#FF8A6B",
  tableTop: "#A8DFD2",
  tableLeg: "#3E7C80",
  plantPot: "#FF8A6B",
  plantLeaf: "#2F8F6B",
  plantLeafDeep: "#1E6B4E",
  shelf: "#3E7C80",
  shelfProp: "#FFC93C",
  window: "#BFEAF2",
  windowGlow: "#E8FBFF",
  lampShade: "#8FE3D2",
  lampGlow: "#D8FFF5",

  ...ELI,

  accent: "#FF8A6B", // coral — complementary pop against the teal room
  accentSoft: "#FFB59A",
  thoughtPositive: "#FFC93C",
  thoughtWorried: "#FF6B8A",
  thoughtBubble: "#F0FFFB",

  phoneBody: "#12212B",
  phoneScreenOn: "#EAFBFF",
  phoneScreenOff: "#1C3340",
  bubbleFill: "#FFFFFF",
  bubbleText: "#12212B",

  keyLight: "#EAF6FF",
  fillLight: "#7FD8C8",
  rimLight: "#FFF2C2",
  ambientGround: "#0B2B33",
  shadowTint: "#07222A",
}

export const PALETTES: Record<EliPalette["id"], EliPalette> = { warm: WARM, cool: COOL }
