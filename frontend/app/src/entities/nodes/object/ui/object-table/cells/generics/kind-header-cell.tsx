import { Icon } from "@iconify-icon/react";
import type React from "react";

import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { classNames } from "@/shared/utils/common";

import type { GenericSchema } from "@/entities/schema/types";

export interface KindHeaderCellProps extends React.HTMLAttributes<HTMLDivElement> {
  schema: GenericSchema;
}

export function KindHeaderCell({ schema, className, ...props }: KindHeaderCellProps) {
  return (
    <div
      className={classNames(cellsStyle, cellHeaderStyle, "hover:bg-white", className)}
      data-testid="kind-header-cell"
      {...props}
    >
      <Icon icon="mdi:code-json" className="text-stone-400" />
      <span className="mr-2">Kind</span>
    </div>
  );
}
