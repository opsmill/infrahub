const ELLIPSIS = "…";

export const truncateLabel = (label: string, maxCharacters: number) => {
  if (label.length <= maxCharacters) return label;
  if (maxCharacters <= 1) return ELLIPSIS;

  return `${label.slice(0, maxCharacters - 1)}${ELLIPSIS}`;
};
