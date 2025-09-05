import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { classNames } from "@/shared/utils/common";

export function ActionsHeaderCell() {
  return (
    <div
      className={classNames(
        cellsStyle,
        cellHeaderStyle,
        "-ml-px right-0 z-10 size-10 border-l hover:bg-white"
      )}
    />
  );
}
