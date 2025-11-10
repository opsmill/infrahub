import { Icon } from "@iconify-icon/react";

import { Checkbox, type CheckboxProps } from "@/shared/components/aria/checkbox";
import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import type { ModelSchema } from "@/entities/schema/types";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";

interface TableIdentifierHeaderProps extends CheckboxProps {
  schema: ModelSchema;
}

export function TableIdentifierHeader({ schema, className, ...props }: TableIdentifierHeaderProps) {
  const { isAuthenticated } = useAuth();

  return (
    <div
      className={classNames(cellsStyle, cellHeaderStyle, "left-0 z-10 hover:bg-white", className)}
    >
      {isAuthenticated && <Checkbox {...props} data-testid="select-all-rows" />}
      {schema.icon && <Icon icon={getSchemaIcon(schema)} className="text-stone-400" />}
      <span className="truncate">{schema.label}</span>
    </div>
  );
}
