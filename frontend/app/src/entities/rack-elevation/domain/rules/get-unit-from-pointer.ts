export interface GetUnitFromPointerParams {
  /** Vertical pointer coordinate in the drawing's own coordinate system. */
  y: number;
  /** Vertical coordinate of the top edge of the highest unit. */
  top: number;
  unitHeight: number;
  rackHeight: number;
}

/** Unit under the pointer, numbered from 1 at the bottom, or null outside the rack. */
export const getUnitFromPointer = ({
  y,
  top,
  unitHeight,
  rackHeight,
}: GetUnitFromPointerParams): number | null => {
  const rowFromTop = Math.floor((y - top) / unitHeight);
  if (rowFromTop < 0 || rowFromTop >= rackHeight) return null;

  return rackHeight - rowFromTop;
};
