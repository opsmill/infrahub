import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import useFilters, { Filter } from "@/shared/hooks/useFilters";
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
        value={filter.value}
      />
    );
  }

  if (fieldKey === "ids") {
    const relationshipSchema = schema.relationships?.find(({ name }) => name === fieldName);
    if (!relationshipSchema) {
      return null;
    }

    const value =
      relationshipSchema.cardinality === "many"
        ? filter.value
            .map(({ display_label }: { display_label: string }) => display_label)
            .join(", ")
        : filter.value.display_label;

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

const FilterButton = ({ label, value, ...props }: FilterButtonProps) => {
  return (
    <Button
      className="group border border-dashed border-gray-300 bg-neutral-100 text-gray-600 rounded-full inline-flex items-center px-1 text-sm hover:bg-gray-100 gap-1.5"
      {...props}
    >
      <span className="ml-1.5">{label}</span>
      <div className="w-px bg-gray-300 self-stretch h-6" />
      <span className="text-indigo-700 font-medium">{value}</span>
      <Icon
        icon="mdi:close-circle-outline"
        className="text-base text-gray-400 group-hover:text-gray-700"
      />
    </Button>
  );
};
