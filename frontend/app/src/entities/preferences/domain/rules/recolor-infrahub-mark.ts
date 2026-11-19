// The accent fill and gradient starts, then the two stops of the hexagon outline gradient.
const RECOLORED_MARK_COLORS = /#0B97BB|#264D59|#0C3E54/gi;

export function recolorInfrahubMark(markSvg: string, color: string): string {
  return markSvg.replace(RECOLORED_MARK_COLORS, color);
}
