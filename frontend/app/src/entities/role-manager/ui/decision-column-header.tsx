import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import useFilters from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";

import { DecisionFilterForm } from "@/entities/nodes/object/ui/filters/decision-filter-form";
import type { DecisionOption } from "@/entities/role-manager/domain/get-decision-options";
import type { AttributeSchema } from "@/entities/schema/types";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";

export function DecisionColumnHeader({
  attributeSchema,
  options,
}: {
  attributeSchema: AttributeSchema;
  options: DecisionOption[];
}) {
  const [filters] = useFilters();
  const [showFilters, setShowFilters] = useState(false);
  const currentFilter = filters.find((f) => f.name.startsWith(attributeSchema.name));

  return (
    <Popover open={showFilters} onOpenChange={setShowFilters}>
      <PopoverTrigger className={classNames(cellsStyle, cellHeaderStyle)}>
        <FieldSchemaIcon fieldSchema={attributeSchema} />

        <span className="mr-2 truncate">{attributeSchema.label ?? attributeSchema.name}</span>
        <Icon
          icon="mdi:filter-variant"
          className={classNames("ml-auto text-lg", currentFilter ? "text-indigo-700" : "invisible")}
        />
      </PopoverTrigger>

      <PopoverContent className="relative rounded-tl-none p-0" align="start">
        <div className="absolute -top-[1.8rem] -left-px rounded-t-md border border-gray-200 border-b-0 bg-white px-2 py-1 font-semibold">
          Filter by {attributeSchema.label ?? attributeSchema.name}
        </div>

        <DecisionFilterForm
          attributeSchema={attributeSchema}
          options={options}
          onSuccess={() => setShowFilters(false)}
        />
      </PopoverContent>
    </Popover>
  );
}
