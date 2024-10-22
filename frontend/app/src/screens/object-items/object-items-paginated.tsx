import { ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { Filters } from "@/components/filters/filters";
import { ObjectCreateFormTrigger } from "@/components/form/object-create-form-trigger";
import ModalDeleteObject from "@/components/modals/modal-delete-object";
import { Pagination } from "@/components/ui/pagination";
import { SearchInput, SearchInputProps } from "@/components/ui/search-input";
import {
  MENU_EXCLUDELIST,
  SEARCH_ANY_FILTER,
  SEARCH_FILTERS,
  SEARCH_PARTIAL_MATCH,
} from "@/config/constants";
import useFilters, { Filter } from "@/hooks/useFilters";
import { useObjectItems } from "@/hooks/useObjectItems";
import { useTitle } from "@/hooks/useTitle";
import ErrorScreen from "@/screens/errors/error-screen";
import NoDataFound from "@/screens/errors/no-data-found";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { ObjectItemsCell, TextCell } from "@/screens/object-items/object-items-cell";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { classNames, debounce } from "@/utils/common";
import { getDisplayValue } from "@/utils/getObjectItemDisplayValue";
import { getSchemaObjectColumns } from "@/utils/getSchemaObjectColumns";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { Navigate } from "react-router-dom";
import UnauthorizedScreen from "../errors/unauthorized-screen";

type ObjectItemsProps = {
  schema: IModelSchema;
  onSuccess?: (newObject: any) => void;
  preventBlock?: boolean;
  preventLinks?: boolean;
};

export default function ObjectItems({
  schema,
  onSuccess,
  preventBlock,
  preventLinks,
}: ObjectItemsProps) {
  const [filters, setFilters] = useFilters();

  const [rowToDelete, setRowToDelete] = useState<any>();
  const [deleteModal, setDeleteModal] = useState<boolean>(false);

  const kindFilter = filters?.find((filter) => filter.name == "kind__value");

  if (schema && MENU_EXCLUDELIST.includes(schema.kind as string) && !preventBlock) {
    return <Navigate to="/" />;
  }

  if (!schema.kind) {
    return <ErrorScreen message="No schema available for this object." />;
  }

  // Get all the needed columns (attributes + relationships)
  const columns = getSchemaObjectColumns({ schema: schema, forListView: true });

  const {
    loading,
    error,
    data = {},
    refetch,
    permission,
  } = useObjectItems(schema, filters, kindFilter?.value);

  const result = data && schema?.kind ? (data[kindFilter?.value || schema?.kind] ?? {}) : {};

  const { count = "...", edges } = result;

  useTitle(`${schema.label || schema.name} list`);

  const rows = edges?.map((edge: any) => edge.node);

  const handleSearch: SearchInputProps["onChange"] = (e) => {
    const value = e.target.value as string;
    if (!value) {
      const newFilters = filters.filter((filter: Filter) => !SEARCH_FILTERS.includes(filter.name));

      setFilters(newFilters);

      return;
    }

    const newFilters = [
      ...filters,
      {
        name: SEARCH_PARTIAL_MATCH,
        value: true,
      },
      {
        name: SEARCH_ANY_FILTER,
        value: value,
      },
    ];

    setFilters(newFilters);
  };

  const debouncedHandleSearch = debounce(handleSearch, 500);

  if (error) {
    if (error.networkError?.statusCode === 403) {
      const { message } = error.networkError?.result?.errors?.[0] ?? {};

      return <UnauthorizedScreen message={message} />;
    }

    return <ErrorScreen message="Something went wrong when fetching list." />;
  }

  if (!loading && !permission.view.isAllowed) {
    return <UnauthorizedScreen message={permission.view.message} />;
  }

  return (
    <>
      <div className="overflow-hidden" data-testid="object-items">
        <div className="flex items-center p-2">
          <SearchInput
            loading={loading}
            onChange={debouncedHandleSearch}
            placeholder="Search an object"
            className="border-none focus-visible:ring-0 h-7"
            data-testid="object-list-search-bar"
          />

          <Filters schema={schema} />

          <ObjectCreateFormTrigger
            schema={schema}
            onSuccess={onSuccess}
            isLoading={loading}
            permission={permission}
          />
        </div>

        {loading && !rows && <LoadingScreen />}

        {/* TODO: use new Table component for list */}
        {!loading && rows && (
          <div className="overflow-auto">
            <table className="table-auto border-spacing-0 w-full" cellPadding="0">
              <thead className="bg-gray-50 text-left border-y border-gray-300">
                <tr>
                  {columns?.map((attribute) => (
                    <th key={attribute.name} scope="col" className="h-9 font-semibold">
                      <TextCell>{attribute.label}</TextCell>
                    </th>
                  ))}
                  <th scope="col"></th>
                </tr>
              </thead>

              <tbody className="bg-custom-white">
                {rows?.map((row: any, index: number) => (
                  <tr
                    key={index}
                    className={classNames(
                      "border-b border-gray-200",
                      !preventLinks && "hover:bg-gray-50"
                    )}
                    data-cy="object-table-row"
                  >
                    {columns?.map((attribute, index) => {
                      return (
                        <td key={index} className="h-9">
                          {preventLinks ? (
                            <TextCell key={index}>{getDisplayValue(row, attribute)}</TextCell>
                          ) : (
                            <ObjectItemsCell row={row} attribute={attribute} />
                          )}
                        </td>
                      );
                    })}

                    <td className="h-9 text-right">
                      <ButtonWithTooltip
                        data-cy="delete"
                        data-testid="delete-row-button"
                        disabled={!permission?.delete.isAllowed}
                        tooltipEnabled={!permission?.delete.isAllowed}
                        tooltipContent={permission?.delete.message}
                        variant="ghost"
                        onClick={() => {
                          setRowToDelete(row);
                          setDeleteModal(true);
                        }}
                      >
                        <Icon icon="mdi:trash" className="text-red-500" />
                      </ButtonWithTooltip>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {!rows?.length && <NoDataFound message="No items found." />}

            <Pagination count={count} />
          </div>
        )}
      </div>

      <ModalDeleteObject
        label={schema.label ?? schema.kind}
        rowToDelete={rowToDelete}
        open={!!deleteModal}
        close={() => setDeleteModal(false)}
        onDelete={refetch}
      />
    </>
  );
}
