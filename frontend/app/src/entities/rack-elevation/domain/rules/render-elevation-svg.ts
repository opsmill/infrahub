import type {
  Elevation,
  ElevationItem,
  RackFace,
} from "@/entities/rack-elevation/domain/model/elevation";

export type ExportTheme = "dark" | "light";

export interface SvgExportOptions {
  faces: RackFace[];
  theme: ExportTheme;
  title: string;
  subtitle: string;
  matchedKeys: Set<string> | null;
}

export interface RenderedSvg {
  svg: string;
  width: number;
  height: number;
}

const UNIT = 18;
const RACK_WIDTH = UNIT * 11;
const RAIL = 22;
const FRAME = 5;
const HEADER = 22;
const FACE_GAP = 48;
const MARGIN = 32;
const TITLE_BLOCK = 56;
const FACE_TITLE = 20;
const CHAR_WIDTH = 5.6;
const FONT = "Inter, -apple-system, Segoe UI, Helvetica, Arial, sans-serif";

const THEMES = {
  dark: {
    frame: "#292524",
    header: "#1c1917",
    headerText: "#e7e5e4",
    interior: "#0c0a09",
    rail: "#44403c",
    railText: "#a8a29e",
    unitLine: "#1c1917",
    itemOpacity: 0.35,
    text: "#fafaf9",
    subtext: "#d6d3d1",
    ghostText: "#78716c",
    hatch: "#ffffff",
  },
  light: {
    frame: "#a8a29e",
    header: "#e7e5e4",
    headerText: "#1c1917",
    interior: "#ffffff",
    rail: "#e7e5e4",
    railText: "#57534e",
    unitLine: "#f5f5f4",
    itemOpacity: 0.18,
    text: "#1c1917",
    subtext: "#57534e",
    ghostText: "#a8a29e",
    hatch: "#000000",
  },
} as const;

type Palette = (typeof THEMES)[ExportTheme];

function escapeXml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function truncate(value: string, maxChars: number): string {
  if (value.length <= maxChars) return value;
  return `${value.slice(0, Math.max(0, maxChars - 1))}…`;
}

function renderItem(
  item: ElevationItem,
  face: RackFace,
  x: number,
  rackTop: number,
  rackHeight: number,
  palette: Palette,
  matchedKeys: Set<string> | null
): string {
  const position = item.position ?? 1;
  const y = rackTop + (rackHeight - (position + item.height - 1)) * UNIT + 1;
  const height = item.height * UNIT - 2;
  const width = RACK_WIDTH - 4;
  const isGhost = item.face !== face;
  const opacity = matchedKeys && !matchedKeys.has(item.key) ? 0.2 : 1;
  const color = escapeXml(item.color);
  const maxChars = Math.floor((width - 14) / CHAR_WIDTH);
  const textX = x + 9;
  const centerY = y + height / 2;

  if (isGhost) {
    return [
      `<g opacity="${opacity}">`,
      `<rect x="${x}" y="${y}" width="${width}" height="${height}" rx="2" fill="url(#hatch)" stroke="${color}" stroke-opacity="0.5" stroke-dasharray="3 2"/>`,
      `<text x="${textX}" y="${centerY}" dominant-baseline="central" font-size="9" fill="${palette.ghostText}">${escapeXml(truncate(`${item.label} · mounted ${item.face}`, maxChars))}</text>`,
      "</g>",
    ].join("");
  }

  const label = escapeXml(truncate(item.label, maxChars));
  let text: string;
  if (item.height > 1 && item.subtitle) {
    text =
      `<text x="${textX}" y="${centerY - 6}" dominant-baseline="central" font-size="10" font-weight="600" fill="${palette.text}">${label}</text>` +
      `<text x="${textX}" y="${centerY + 7}" dominant-baseline="central" font-size="9" fill="${palette.subtext}">${escapeXml(truncate(item.subtitle, maxChars))}</text>`;
  } else {
    const remaining = maxChars - item.label.length - 2;
    const subtitle =
      item.subtitle && remaining > 3 ? escapeXml(truncate(item.subtitle, remaining)) : null;
    text =
      `<text x="${textX}" y="${centerY}" dominant-baseline="central" font-size="10" fill="${palette.text}">` +
      `<tspan font-weight="600">${label}</tspan>` +
      (subtitle ? `<tspan fill="${palette.subtext}" dx="6">${subtitle}</tspan>` : "") +
      "</text>";
  }

  return [
    `<g opacity="${opacity}">`,
    `<rect x="${x}" y="${y}" width="${width}" height="${height}" rx="2" fill="${palette.interior}"/>`,
    `<rect x="${x}" y="${y}" width="${width}" height="${height}" rx="2" fill="${color}" fill-opacity="${palette.itemOpacity}" stroke="${color}" stroke-opacity="0.8"/>`,
    `<rect x="${x}" y="${y}" width="3" height="${height}" fill="${color}"/>`,
    text,
    "</g>",
  ].join("");
}

function renderFace(
  elevation: Elevation,
  face: RackFace,
  originX: number,
  originY: number,
  palette: Palette,
  matchedKeys: Set<string> | null
): string {
  const rackPixelHeight = elevation.height * UNIT;
  const outerWidth = RACK_WIDTH + RAIL * 2 + FRAME * 2;
  const rackTop = originY + FACE_TITLE + FRAME + HEADER;
  const interiorX = originX + FRAME + RAIL;
  const parts: string[] = [
    `<text x="${originX + outerWidth / 2}" y="${originY + 10}" text-anchor="middle" font-size="10" font-weight="600" letter-spacing="1" fill="#78716c">${face === "front" ? "FRONT" : "REAR"}</text>`,
    `<rect x="${originX}" y="${originY + FACE_TITLE}" width="${outerWidth}" height="${rackPixelHeight + HEADER + FRAME * 2}" rx="6" fill="${palette.frame}"/>`,
    `<rect x="${originX + FRAME}" y="${originY + FACE_TITLE + FRAME}" width="${outerWidth - FRAME * 2}" height="${HEADER - 3}" rx="3" fill="${palette.header}"/>`,
    `<text x="${originX + FRAME + 8}" y="${originY + FACE_TITLE + FRAME + (HEADER - 3) / 2}" dominant-baseline="central" font-size="10" font-weight="600" fill="${palette.headerText}">${escapeXml(truncate(elevation.label, 34))}</text>`,
    `<text x="${originX + outerWidth - FRAME - 8}" y="${originY + FACE_TITLE + FRAME + (HEADER - 3) / 2}" dominant-baseline="central" text-anchor="end" font-size="10" fill="${palette.railText}">${elevation.height}U</text>`,
    `<rect x="${interiorX}" y="${rackTop}" width="${RACK_WIDTH}" height="${rackPixelHeight}" fill="${palette.interior}"/>`,
  ];

  for (const side of [originX + FRAME, interiorX + RACK_WIDTH]) {
    parts.push(
      `<rect x="${side}" y="${rackTop}" width="${RAIL}" height="${rackPixelHeight}" fill="${palette.rail}"/>`
    );
  }
  for (let unit = 1; unit <= elevation.height; unit++) {
    const y = rackTop + (elevation.height - unit) * UNIT;
    parts.push(
      `<line x1="${interiorX}" y1="${y + UNIT}" x2="${interiorX + RACK_WIDTH}" y2="${y + UNIT}" stroke="${palette.unitLine}"/>`
    );
    for (const side of [originX + FRAME, interiorX + RACK_WIDTH]) {
      parts.push(
        `<text x="${side + RAIL / 2}" y="${y + UNIT / 2}" text-anchor="middle" dominant-baseline="central" font-size="8" fill="${palette.railText}">${unit}</text>`
      );
    }
  }

  for (const item of elevation.placed) {
    if (item.face !== face && !item.fullDepth) continue;
    parts.push(
      renderItem(item, face, interiorX + 2, rackTop, elevation.height, palette, matchedKeys)
    );
  }
  return parts.join("");
}

export function renderElevationSvg(elevation: Elevation, options: SvgExportOptions): RenderedSvg {
  const palette = THEMES[options.theme];
  const faceWidth = RACK_WIDTH + RAIL * 2 + FRAME * 2;
  const faceHeight = FACE_TITLE + elevation.height * UNIT + HEADER + FRAME * 2;
  const facesWidth = options.faces.length * faceWidth + (options.faces.length - 1) * FACE_GAP;
  const width = Math.max(facesWidth, 320) + MARGIN * 2;
  const height = TITLE_BLOCK + faceHeight + MARGIN * 2;
  const facesX = (width - facesWidth) / 2;

  const faces = options.faces
    .map((face, index) =>
      renderFace(
        elevation,
        face,
        facesX + index * (faceWidth + FACE_GAP),
        MARGIN + TITLE_BLOCK,
        palette,
        options.matchedKeys
      )
    )
    .join("");

  const svg = [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" font-family="${FONT}">`,
    `<defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="${palette.interior}"/><line x1="0" y1="0" x2="0" y2="6" stroke="${palette.hatch}" stroke-opacity="0.12" stroke-width="3"/></pattern></defs>`,
    `<rect width="${width}" height="${height}" fill="#ffffff"/>`,
    `<text x="${MARGIN}" y="${MARGIN + 14}" font-size="18" font-weight="700" fill="#1c1917">${escapeXml(options.title)}</text>`,
    `<text x="${MARGIN}" y="${MARGIN + 34}" font-size="11" fill="#78716c">${escapeXml(options.subtitle)}</text>`,
    faces,
    "</svg>",
  ].join("");

  return { svg, width, height };
}
