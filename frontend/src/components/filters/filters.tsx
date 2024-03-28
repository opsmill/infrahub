import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useState } from "react";
import { DEFAULT_BRANCH_NAME, SEARCH_FILTERS } from "../../config/constants";
import useFilters from "../../hooks/useFilters";
import { Form } from "../../screens/edit-form-hook/form";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import getFormStructureForCreateEdit from "../../utils/formStructureForCreateEdit";
import { BUTTON_TYPES, Button } from "../buttons/button";
import { ButtonWithTooltip } from "../buttons/button-with-tooltip";
import SlideOver from "../display/slide-over";

type tFilters = {
  schema: any;
};

const computeFilter = (data: [key: string, value: any]) => {
  const [key, value] = data;

  if (value.value)
    return {
      name: `${key}__value`,
      value: value.value,
    };

  if (value.id) {
    return {
      name: `${key}__ids`,
      value: [value.id],
    };
  }

  if (value.list?.length) {
    return {
      name: `${key}__ids`,
      value: value.list,
    };
  }
};

const constructNewFilters = (data: any) => Object.entries(data).map(computeFilter).filter(Boolean);

const parseFilter = (acc: any, filter: any, schema: any) => {
  if (!filter?.name) return;

  if (filter.name.includes("__value")) {
    const key = filter.name.replace("__value", "");

    return {
      ...acc,
      [key]: {
        value: filter.value,
      },
    };
  }

  if (schema && filter.name.includes("__ids")) {
    const key = filter.name.replace("__ids", "");

    const field =
      schema.attributes.find((attribute) => attribute.name === key) ||
      schema.relationships.find((relationship) => relationship.name === key);

    if (field.cardinality === "many") {
      return {
        ...acc,
        [key]: {
          edges: filter.value.map((id) => ({ node: { id } })),
        },
      };
    }

    return {
      ...acc,
      [key]: {
        node: {
          id: filter.value,
        },
      },
    };
  }

  return acc;
};

export const Filters = (props: tFilters) => {
  const { schema } = props;

  const branch = useAtomValue(currentBranchAtom);
  const schemaList = useAtomValue(schemaState);
  const genericList = useAtomValue(genericsState);

  const [filters, setFilters] = useFilters();
  const [showFilters, setShowFilters] = useState(false);

  const removeFilters = () => {
    const newFilters = filters.filter((filter) => SEARCH_FILTERS.includes(filter.name));

    setFilters(newFilters);
  };

  const handleShowFilters = () => setShowFilters(true);

  const handleSubmit = (data: any) => {
    const newFilters = constructNewFilters(data);

    setFilters([...filters, ...newFilters]);

    setShowFilters(false);
  };

  const filtersObject = filters.reduce((acc, filter) => parseFilter(acc, filter, schema), {});

  const currentFilters = filters.filter((filter) => !SEARCH_FILTERS.includes(filter.name));

  const fields = getFormStructureForCreateEdit({
    schema,
    schemas: schemaList,
    generics: genericList,
    row: filtersObject,
    isFilters: true,
  });

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
          <Button onClick={removeFilters} buttonType={BUTTON_TYPES.INVISIBLE}>
            <Icon icon="mdi:close" className="text-gray-400" />
          </Button>
        )}
      </div>

      <SlideOver
        title={
          <div className="space-y-2">
            <div className="flex items-center w-full">
              <span className="text-lg font-semibold mr-3">Apply filters</span>
              <div className="flex-1"></div>
              <div className="flex items-center">
                <Icon icon={"mdi:layers-triple"} />
                <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
              </div>
            </div>

            <div className="text-sm">{schema?.description}</div>

            <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20 mr-2">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              {schema?.kind}
            </span>
          </div>
        }
        open={showFilters}
        setOpen={setShowFilters}>
        <Form fields={fields} submitLabel="Apply filters" onSubmit={handleSubmit} />
      </SlideOver>
    </div>
  );
};
