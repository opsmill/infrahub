import { GenericSchema } from "@/entities/schema/types";
import { Button } from "@/shared/components/buttons/button-primitive";
import { FilterKindSelector } from "@/shared/components/filters/filter-kind-selector";
import { getFiltersFromFormData } from "@/shared/components/filters/utils/getFiltersFromFormData";
import { FormFieldValue } from "@/shared/components/form/type";
import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { Form, FormSubmit } from "@/shared/components/ui/form";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import useFilters from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { PopoverTriggerProps } from "@radix-ui/react-popover";
import { useState } from "react";

export interface KindHeaderCellProps extends PopoverTriggerProps {
  schema: GenericSchema;
}

export function KindHeaderCell({ schema, ...props }: KindHeaderCellProps) {
  const [filters, setFilters] = useFilters();
  const [showFilters, setShowFilters] = useState(false);
  const currentKindFilters = filters.find((filter) => filter.name === "kind__value");

  const handleSubmit = (formData: Record<string, FormFieldValue>) => {
    const newFilters = getFiltersFromFormData(formData);

    setFilters([...filters, ...newFilters]);
    setShowFilters(false);
  };

  return (
    <Popover open={showFilters} onOpenChange={setShowFilters}>
      <PopoverTrigger className={classNames(cellsStyle, cellHeaderStyle)} {...props}>
        <Icon icon="mdi:code-json" className="text-stone-400" />
        <span className="truncate mr-2">Kind</span>
        <Icon
          icon="mdi:filter-variant"
          className={classNames(
            "text-lg ml-auto",
            currentKindFilters ? "text-indigo-700" : "invisible"
          )}
        />
      </PopoverTrigger>

      <PopoverContent className="min-w-[19rem] relative rounded-tl-none" align="start">
        <div className="absolute font-semibold -top-[1.8rem] bg-white border border-gray-200 px-2 py-1 rounded-t-md border-b-0 -left-px">
          Filter by kind
        </div>
        <Form onSubmit={handleSubmit}>
          <FilterKindSelector genericSchema={schema} showLabel={false} />

          <div className="text-right">
            <Button variant="outline" className="mr-2" onClick={() => setShowFilters(false)}>
              Cancel
            </Button>
            <FormSubmit>Filter</FormSubmit>
          </div>
        </Form>
      </PopoverContent>
    </Popover>
  );
}
