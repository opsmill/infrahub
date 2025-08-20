import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { classNames } from "@/shared/utils/common";

export function ActionsHeaderCell() {
  return (
    <div
      className={classNames(
        cellsStyle,
        cellHeaderStyle,
        "right-0 z-10 border-l size-10 -ml-px hover:bg-white"
      )}
    />
  );
}
