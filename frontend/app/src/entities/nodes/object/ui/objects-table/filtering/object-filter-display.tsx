import { AttributeType } from "@/entities/nodes/getObjectItemDisplayValue";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import { AttributeKind } from "@/entities/schema/types";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import useFilters, { Filter } from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";
import { formatFullDate } from "@/shared/utils/date";
import { Icon } from "@iconify-icon/react";
import React from "react";
import { Button, ButtonProps } from "react-aria-components";

type FilterBadgeProps = {
  schema: IModelSchema;
  filter: Filter;
};

export const ObjectFilterDisplay = ({ schema, filter }: FilterBadgeProps) => {
  const [filters, setFilters] = useFilters();
  const [fieldName, fieldKey] = filter.name.split("__");

  const handleRemoveFilter = (filterName: string) => {
    setFilters(filters.filter((f) => f.name !== filterName));
  };

  if (!fieldName || !fieldKey) {
    return null;
  }

  if (fieldKey === "value" || fieldKey === "values") {
    const attributeSchema = schema.attributes?.find(({ name }) => name === fieldName);
    if (!attributeSchema) {
      return null;
    }

    return (
      <FilterButton
        onPress={() => handleRemoveFilter(filter.name)}
        label={attributeSchema.label ?? attributeSchema.name}
        value={formatAttributeFilterValue({
          kind: attributeSchema.kind as AttributeKind,
          value: filter.value,
        })}
      />
    );
  }

  if (fieldKey === "ids") {
    const relationshipSchema = schema.relationships?.find(({ name }) => name === fieldName);
    if (!relationshipSchema) {
      return null;
    }

    const value = filter.value
      .map(({ display_label }: { display_label: string }) => display_label)
      .join(", ");

    return (
      <FilterButton
        onPress={() => handleRemoveFilter(filter.name)}
        label={relationshipSchema.label ?? relationshipSchema.name}
        value={value}
      />
    );
  }

  return null;
};

interface FilterButtonProps extends Omit<ButtonProps, "value"> {
  label: React.ReactNode;
  value: React.ReactNode;
}

const FilterButton = ({ label, value, className, ...props }: FilterButtonProps) => {
  return (
    <Button
      className={classNames(
        focusVisibleStyle,
        "text-gray-600 text-sm whitespace-nowrap",
        "group bg-neutral-100 rounded-full inline-flex items-center gap-1.5 px-1",
        "border border-gray-300",
        "data-[hovered]:bg-gray-100 data-[hovered]:border-indigo-700",
        className
      )}
      {...props}
    >
      <span className="ml-1.5">{label}</span>
      <div className="w-px bg-gray-300 self-stretch h-6" />
      <span className="text-indigo-700 font-medium">{value}</span>
      <Icon
        icon="mdi:close-circle-outline"
        className="text-base text-gray-400 group-hover:text-indigo-700"
      />
    </Button>
  );
};

export function formatAttributeFilterValue({
  kind,
  value,
}: { kind: AttributeKind; value: AttributeType["value"] }) {
  switch (kind) {
    case ATTRIBUTE_KIND.BOOLEAN:
      return value.toString();
    case ATTRIBUTE_KIND.DATETIME:
      return formatFullDate(value);
    default:
      return value;
  }
}
