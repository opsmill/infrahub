import type React from "react";

import { Icon } from "@/shared/components/display/icon";
import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { classNames } from "@/shared/utils/common";

import type { GenericSchema } from "@/entities/schema/domain/model/schema";

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
      <Icon icon="mdi:code-json" />
      <span className="mr-2">Kind</span>
    </div>
  );
}
