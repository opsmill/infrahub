import { Checkbox, type CheckboxProps } from "@infrahub/ui";

import { Row } from "@/shared/components/container";
import { Icon } from "@/shared/components/display/icon";
import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { getSchemaIcon } from "@/entities/schema/domain/rules/get-schema-icon";

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

      <Row className="mx-2 gap-1.5">
        {schema.icon && <Icon icon={getSchemaIcon(schema)} />}
        <span className="truncate">{schema.label}</span>
      </Row>
    </div>
  );
}
