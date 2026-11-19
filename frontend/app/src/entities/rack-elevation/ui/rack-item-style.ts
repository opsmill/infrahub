import type React from "react";

export const RACK_FRAME_COLOR = "#1c1917";

export function faceplateStyle(color: string): React.CSSProperties {
  return {
    backgroundColor: `color-mix(in oklch, ${color} 30%, ${RACK_FRAME_COLOR})`,
    borderColor: `color-mix(in oklch, ${color} 65%, transparent)`,
    boxShadow: `inset 3px 0 0 ${color}`,
  };
}

export function ghostStyle(color: string): React.CSSProperties {
  return {
    backgroundImage:
      "repeating-linear-gradient(135deg, rgb(255 255 255 / 0.07) 0 4px, transparent 4px 8px)",
    borderColor: `color-mix(in oklch, ${color} 40%, transparent)`,
  };
}
