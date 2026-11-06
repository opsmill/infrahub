import * as R from "remeda";

import type { Dropdown, TextAttribute } from "@/shared/api/graphql/generated/types";
import { DateDisplay } from "@/shared/components/display/date-display";
import { warnUnexpectedType } from "@/shared/utils/common";

import type { NodeAttribute } from "@/entities/nodes/object/domain/model/node";
import { isEmptyAttributeValue } from "@/entities/nodes/object/domain/rules/is-empty-attribute-value";
import { JsonValueButton } from "@/entities/nodes/object/ui/attribute-values/json-value-button";
import { ListValueCell } from "@/entities/nodes/object/ui/attribute-values/list-value";
import { MaskedValue } from "@/entities/nodes/object/ui/attribute-values/masked-value";
import { ColorCell } from "@/entities/nodes/object/ui/object-table/cells/color-cell";
import { DropdownCell } from "@/entities/nodes/object/ui/object-table/cells/dropdown-cell";
import { NodeKindCell } from "@/entities/nodes/object/ui/object-table/cells/node-kind-cell";
import { UrlCell } from "@/entities/nodes/object/ui/object-table/cells/url-cell";
import { ATTRIBUTE_KIND } from "@/entities/schema/domain/model/attribute-kind";
import type { AttributeKind, AttributeSchema } from "@/entities/schema/domain/model/schema";

export interface TableAttributeCellProps {
  attributeSchema: AttributeSchema;
  attributeData?: NodeAttribute;
}

export function TableAttributeCell({ attributeSchema, attributeData }: TableAttributeCellProps) {
  const attributeKind = attributeSchema.kind as AttributeKind;
  if (!attributeData || isEmptyAttributeValue(attributeData.value)) return "-";

  const attributeLabel = attributeSchema.label ?? attributeSchema.name;

  switch (attributeKind) {
    case ATTRIBUTE_KIND.DROPDOWN: {
      return <DropdownCell dropdown={attributeData as Dropdown} />;
    }
    case ATTRIBUTE_KIND.DATETIME: {
      // A datetime *data* attribute: show the user's full preferred format+timezone inline.
      return (
        <span className="truncate">
          <DateDisplay date={attributeData.value as string | null} fullTimestamp />
        </span>
      );
    }
    case ATTRIBUTE_KIND.BOOLEAN:
    case ATTRIBUTE_KIND.CHECKBOX: {
      return <span className="truncate">{String(attributeData.value)}</span>;
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
    case ATTRIBUTE_KIND.IP_ADDRESS:
    case ATTRIBUTE_KIND.NODE_KIND:
    case ATTRIBUTE_KIND.TEXTAREA: {
      if (attributeSchema.name === "node_kind") {
        return <NodeKindCell kind={attributeData.value as string} />;
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
    case ATTRIBUTE_KIND.PASSWORD: {
      return <MaskedValue />;
    }
    case ATTRIBUTE_KIND.LIST: {
      return (
        <ListValueCell values={attributeData.value as unknown[]} attributeLabel={attributeLabel} />
      );
    }
    case ATTRIBUTE_KIND.JSON: {
      return <JsonValueCell value={attributeData.value} attributeLabel={attributeLabel} />;
    }
    case ATTRIBUTE_KIND.ANY: {
      const value: unknown = attributeData.value;
      if (Array.isArray(value)) {
        return <ListValueCell values={value} attributeLabel={attributeLabel} />;
      }
      if (R.isPlainObject(value)) {
        return <JsonValueCell value={value} attributeLabel={attributeLabel} />;
      }
      return <span className="truncate">{String(value)}</span>;
    }
    default: {
      warnUnexpectedType(attributeKind);
      return null;
    }
  }
}

function JsonValueCell({ value, attributeLabel }: { value: unknown; attributeLabel: string }) {
  return (
    <JsonValueButton
      value={value}
      title={attributeLabel}
      className="h-full w-full text-foreground-muted leading-6 hover:text-foreground"
    />
  );
}
