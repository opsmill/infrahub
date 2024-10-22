import { Button, ButtonWithTooltip } from "@/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import { FilterForm } from "@/components/filters/filter-form";
import { getFiltersFromFormData } from "@/components/filters/utils/getFiltersFromFormData";
import { FormFieldValue } from "@/components/form/type";
import { SEARCH_FILTERS } from "@/config/constants";
import useFilters from "@/hooks/useFilters";
import usePagination from "@/hooks/usePagination";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";

type FiltersProps = {
  schema: IModelSchema;
};

export const Filters = ({ schema }: FiltersProps) => {
  const [filters, setFilters] = useFilters();
  const [pagination, setPagination] = usePagination();
  const [showFilters, setShowFilters] = useState(false);

  const removeFilters = () => {
    const newFilters = filters.filter((filter) => SEARCH_FILTERS.includes(filter.name));

    setPagination({
      ...pagination,
      offset: 0,
    });

    setFilters(newFilters);
  };

  const handleSubmit = (formData: Record<string, FormFieldValue>) => {
    const newFilters = getFiltersFromFormData(formData);

    setPagination({
      ...pagination,
      offset: 0,
    });

    setFilters(newFilters);

    setShowFilters(false);
  };

  const currentFilters = filters.filter((filter) => !SEARCH_FILTERS.includes(filter.name));

  return (
    <>
      <div className="flex-grow flex items-center gap-1">
        <ButtonWithTooltip
          tooltipEnabled
          tooltipContent="Apply filters"
          variant="ghost"
          size="icon"
          data-testid="apply-filters"
          onClick={() => setShowFilters(true)}
        >
          <Icon icon={"mdi:filter-outline"} className="text-custom-blue-100" />
        </ButtonWithTooltip>

        <span className="text-xs">Filters: {currentFilters.length}</span>

        {!!currentFilters.length && (
          <Button onClick={removeFilters} variant="ghost" size="icon" data-testid="remove-filters">
            <Icon icon="mdi:close" className="text-gray-400" />
          </Button>
        )}
      </div>

      <SlideOver
        title={<SlideOverTitle schema={schema} currentObjectLabel="All" title="Apply filters" />}
        open={showFilters}
        setOpen={setShowFilters}
      >
        <FilterForm
          filters={filters}
          schema={schema}
          onSubmit={handleSubmit}
          onCancel={() => setShowFilters(false)}
        />
      </SlideOver>
    </>
  );
};
