import { Icon } from "@iconify-icon/react";
import { Button, Sheet, Tooltip } from "@infrahub/ui";
import { useState } from "react";

import { getFiltersFromFormData } from "@/shared/components/filters/utils/getFiltersFromFormData";
import type { FormFieldValue } from "@/shared/components/form/type";
import { SEARCH_FILTERS } from "@/shared/config/constants";
import useFilters from "@/shared/hooks/useFilters";
import usePagination from "@/shared/hooks/usePagination";

import { TasksFilterForm } from "@/entities/tasks/ui/tasks-filter-form";

export const TaskFilters = () => {
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
      <div className="flex items-center gap-1">
        <Tooltip message="Apply filters">
          <Button
            variant="ghost"
            size="xs"
            shape="circle"
            data-testid="apply-filters"
            onPress={() => setShowFilters(true)}
          >
            <Icon icon={"mdi:filter-outline"} className="text-custom-blue-100" />
          </Button>
        </Tooltip>

        <span className="text-xs">Filters: {currentFilters.length}</span>

        {!!currentFilters.length && (
          <Button
            onPress={removeFilters}
            variant="ghost"
            size="xs"
            shape="circle"
            data-testid="remove-filters"
          >
            <Icon icon="mdi:close" className="text-gray-400" />
          </Button>
        )}
      </div>

      <Sheet isOpen={showFilters} onOpenChange={setShowFilters} aria-label="Apply filters">
        <h3 className="font-semibold text-lg">Apply filters</h3>
        <TasksFilterForm
          filters={filters}
          onSubmit={handleSubmit}
          onCancel={() => setShowFilters(false)}
        />
      </Sheet>
    </>
  );
};
