import { SEARCH_FILTERS, TASK_OBJECT } from "@/config/constants";
import { ModelSchema } from "@/entities/schema/types";
import { Button, ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import { FilterForm } from "@/shared/components/filters/filter-form";
import { getFiltersFromFormData } from "@/shared/components/filters/utils/getFiltersFromFormData";
import { FormFieldValue } from "@/shared/components/form/type";
import useFilters from "@/shared/hooks/useFilters";
import usePagination from "@/shared/hooks/usePagination";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { TasksFilterForm } from "./tasks-filter-form";

type FiltersProps = {
  schema?: ModelSchema;
  kind?: string;
};

export const Filters = ({ schema, kind }: FiltersProps) => {
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

  const getForm = () => {
    if (kind === TASK_OBJECT) {
      return (
        <SlideOver title={"Apply filters"} open={showFilters} setOpen={setShowFilters}>
          <TasksFilterForm
            filters={filters}
            onSubmit={handleSubmit}
            onCancel={() => setShowFilters(false)}
          />
        </SlideOver>
      );
    }

    return (
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
    );
  };

  return (
    <>
      <div className="flex items-center gap-1">
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

      {getForm()}
    </>
  );
};
