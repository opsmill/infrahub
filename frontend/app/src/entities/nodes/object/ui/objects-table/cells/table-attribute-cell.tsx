import { AttributeType } from "@/entities/nodes/getObjectItemDisplayValue";
import { DropdownCell } from "@/entities/nodes/object/ui/objects-table/cells/dropdown-cell";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import { AttributeSchema } from "@/entities/schema/types";
import { Dropdown } from "@/shared/api/graphql/generated/graphql";
import { formatRelativeTimeFromNow } from "@/shared/utils/date";

export interface TableAttributeCellProps {
  attributeSchema: AttributeSchema;
  attributeData: AttributeType;
}

export function TableAttributeCell({ attributeSchema, attributeData }: TableAttributeCellProps) {
  switch (attributeSchema.kind) {
    case ATTRIBUTE_KIND.DROPDOWN: {
      return <DropdownCell dropdown={attributeData as Dropdown} />;
    }
    case ATTRIBUTE_KIND.DATETIME: {
      return <span className="truncate">{formatRelativeTimeFromNow(attributeData.value)}</span>;
    }
    case ATTRIBUTE_KIND.BOOLEAN: {
      return <span className="truncate">{attributeData.value.toString()}</span>;
    }
    default: {
      return <span className="truncate">{attributeData.value}</span>;
    }
  }
}
