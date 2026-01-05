import type { Dropdown, TextAttribute } from "@/shared/api/graphql/generated/graphql";
import { DateDisplay } from "@/shared/components/display/date-display";
import { warnUnexpectedType } from "@/shared/utils/common";

import type { AttributeType } from "@/entities/nodes/getObjectItemDisplayValue";
import { ColorCell } from "@/entities/nodes/object/ui/object-table/cells/color-cell";
import { DropdownCell } from "@/entities/nodes/object/ui/object-table/cells/dropdown-cell";
import { NodeKindCell } from "@/entities/nodes/object/ui/object-table/cells/node-kind-cell";
import { UrlCell } from "@/entities/nodes/object/ui/object-table/cells/url-cell";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import type { AttributeKind, AttributeSchema } from "@/entities/schema/types";

export interface TableAttributeCellProps {
  attributeSchema: AttributeSchema;
  attributeData: AttributeType;
}

export function TableAttributeCell({ attributeSchema, attributeData }: TableAttributeCellProps) {
  const attributeKind = attributeSchema.kind as AttributeKind;
  if (
    !attributeData ||
    (!attributeData.value && attributeData.value !== 0 && attributeData.value !== false)
  )
    return "-";

  switch (attributeKind) {
    case ATTRIBUTE_KIND.DROPDOWN: {
      return <DropdownCell dropdown={attributeData as Dropdown} />;
    }
    case ATTRIBUTE_KIND.DATETIME: {
      return (
        <span className="truncate">
          <DateDisplay date={attributeData.value} />
        </span>
      );
    }
    case ATTRIBUTE_KIND.BOOLEAN:
    case ATTRIBUTE_KIND.CHECKBOX: {
      return <span className="truncate">{attributeData.value.toString()}</span>;
    }
    case ATTRIBUTE_KIND.ID:
    case ATTRIBUTE_KIND.TEXT:
    case ATTRIBUTE_KIND.NUMBER:
    case ATTRIBUTE_KIND.BANDWIDTH:
    case ATTRIBUTE_KIND.EMAIL:
    case ATTRIBUTE_KIND.MAC_ADDRESS:
    case ATTRIBUTE_KIND.FILE:
    case ATTRIBUTE_KIND.IP_HOST:
    case ATTRIBUTE_KIND.IP_NETWORK:
    case ATTRIBUTE_KIND.TEXTAREA: {
      if (attributeSchema.name === "node_kind") {
        return <NodeKindCell kind={attributeData.value} />;
      }

      return <span className="truncate">{attributeData.value}</span>;
    }
    case ATTRIBUTE_KIND.URL: {
      return <UrlCell url={attributeData as TextAttribute} />;
    }
    case ATTRIBUTE_KIND.COLOR: {
      return <ColorCell color={attributeData as TextAttribute} />;
    }
    case ATTRIBUTE_KIND.HASHED_PASSWORD:
    case ATTRIBUTE_KIND.PASSWORD:
    case ATTRIBUTE_KIND.ANY:
    case ATTRIBUTE_KIND.JSON:
    case ATTRIBUTE_KIND.LIST: {
      return null; // Not visible in table view
    }
    default: {
      warnUnexpectedType(attributeKind);
      return null;
    }
  }
}
