/**
 * Shared art direction for both Eli prototypes.
 *
 * One palette, one room, one camera. Only the character (and the visual
 * language of its thought shapes) changes between versions A and B.
 */
export const PALETTE = {
  wallBack: "#CFC0EE",
  /** deeper wash used behind the character for contrast */
  wallWash: "#B9A5DF",
  wallLeft: "#E3D8F6",
  skirting: "#FBF1E4",
  ceiling: "#F3ECFB",
  floor: "#F7E9D9",
  floorShadowTint: "#E7D3BE",
  rug: "#FFD9C4",
  rugRing: "#D9C6F0",

  cream: "#FCF3E7",
  creamDeep: "#F1E0CB",
  wood: "#E8CBA6",
  woodDeep: "#D9B689",

  peach: "#FFB99F",
  peachSoft: "#FFD9C8",
  coral: "#FF8A6B",
  coralDeep: "#F2705A",

  sky: "#A3D6F1",
  skyDeep: "#7BBDDF",
  skySoft: "#CDE8F8",

  lavender: "#CBB9EC",
  lavenderSoft: "#E5DCF8",

  yellow: "#FFD680",
  yellowSoft: "#FFEFC2",

  sage: "#9DBBA6",
  sageDeep: "#84A491",

  ink: "#4C4168",
  inkSoft: "#6F648C",
  white: "#FFFFFF",

  screenOff: "#3B3555",
  screenOn: "#FFF6DE",
} as const
