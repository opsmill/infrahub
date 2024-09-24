import { BUTTON_TYPES, Button } from "@/components/buttons/button";
import { ButtonWithTooltip } from "@/components/buttons/button-with-tooltip";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import { SEARCH_FILTERS } from "@/config/constants";
import useFilters from "@/hooks/useFilters";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import ObjectForm from "@/components/form/object-form";
import usePagination from "@/hooks/usePagination";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { FormFieldValue } from "@/components/form/type";
import { getObjectFromFilters } from "@/components/filters/utils/getObjectFromFilters";
import { getFiltersFromFormData } from "./utils/getFiltersFromFormData";

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

  const handleShowFilters = () => setShowFilters(true);

  const handleSubmit = (formData: Record<string, FormFieldValue>) => {
    const newFilters = getFiltersFromFormData(formData);

    setShowFilters(false);

    setPagination({
      ...pagination,
      offset: 0,
    });

    setFilters(newFilters);
  };

  const currentFilters = filters.filter((filter) => !SEARCH_FILTERS.includes(filter.name));

  return (
    <div className="flex flex-1">
      <div className="flex flex-1 items-center">
        <ButtonWithTooltip
          tooltipEnabled
          tooltipContent="Apply filters"
          buttonType={BUTTON_TYPES.INVISIBLE}
          className="h-full rounded-r-md border border-transparent"
          type="submit"
          data-testid="apply-filters"
          onClick={handleShowFilters}>
          <Icon icon={"mdi:filter-outline"} className="text-custom-blue-100" />
        </ButtonWithTooltip>

        <span className="text-xs">Filters: {currentFilters.length}</span>

        {!!currentFilters.length && (
          <Button
            onClick={removeFilters}
            buttonType={BUTTON_TYPES.INVISIBLE}
            data-testid="remove-filters">
            <Icon icon="mdi:close" className="text-gray-400" />
          </Button>
        )}
      </div>

      <SlideOver
        title={<SlideOverTitle schema={schema} currentObjectLabel="All" title="Apply filters" />}
        open={showFilters}
        setOpen={setShowFilters}>
        <ObjectForm
          onSubmit={({ formData }) => handleSubmit(formData)}
          kind={schema?.kind}
          isFilterForm
          submitLabel="Apply filters"
          currentObject={getObjectFromFilters(schema, currentFilters)}
        />
      </SlideOver>
    </div>
  );
};
