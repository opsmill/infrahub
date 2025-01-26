import { AttributeType } from "@/entities/nodes/getObjectItemDisplayValue";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import { AttributeKind } from "@/entities/schema/types";
import { formatFullDate } from "@/shared/utils/date";

export function formatAttributeValue({
  kind,
  value,
}: { kind: AttributeKind; value: AttributeType["value"] }): string {
  switch (kind) {
    case ATTRIBUTE_KIND.BOOLEAN:
      return value.toString();
    case ATTRIBUTE_KIND.DATETIME:
      return formatFullDate(value);
    default:
      return value;
  }
}
