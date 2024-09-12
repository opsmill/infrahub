import { ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { Filters } from "@/components/filters/filters";
import ModalDelete from "@/components/modals/modal-delete";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { Pagination } from "@/components/ui/pagination";
import { SearchInput, SearchInputProps } from "@/components/ui/search-input";
import {
  ACCOUNT_OBJECT,
  ACCOUNT_TOKEN_OBJECT,
  MENU_EXCLUDELIST,
  SEARCH_ANY_FILTER,
  SEARCH_FILTERS,
  SEARCH_PARTIAL_MATCH,
} from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { deleteObject } from "@/graphql/mutations/objects/deleteObject";
import useFilters, { Filter } from "@/hooks/useFilters";
import { usePermission } from "@/hooks/usePermission";
import { useTitle } from "@/hooks/useTitle";
import ErrorScreen from "@/screens/errors/error-screen";
import NoDataFound from "@/screens/errors/no-data-found";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { classNames, debounce } from "@/utils/common";
import { getSchemaObjectColumns } from "@/utils/getSchemaObjectColumns";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai/index";
import { useState } from "react";
import { Navigate } from "react-router-dom";
import { toast } from "react-toastify";
import { useObjectItems } from "@/hooks/useObjectItems";
import { ObjectItemsCell, TextCell } from "@/screens/object-items/object-items-cell";
import { getDisplayValue } from "@/utils/getObjectItemDisplayValue";
import { ObjectCreateFormTrigger } from "@/components/form/object-create-form-trigger";

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
  const permission = usePermission();
  const [filters, setFilters] = useFilters();

  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  const [rowToDelete, setRowToDelete] = useState<any>();
  const [deleteModal, setDeleteModal] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const kindFilter = filters?.find((filter) => filter.name == "kind__value");

  if (schema && MENU_EXCLUDELIST.includes(schema.kind as string) && !preventBlock) {
    return <Navigate to="/" />;
  }

  // Get all the needed columns (attributes + relationships)
  const columns = getSchemaObjectColumns({ schema: schema, forListView: true });

  const { loading, error, data = {} } = useObjectItems(schema, filters);

  const result = data && schema?.kind ? data[kindFilter?.value || schema?.kind] ?? {} : {};

  const { count = "...", edges } = result;

  useTitle(`${schema.label || schema.name} list`);

  const rows = edges?.map((edge: any) => edge.node);

  const handleDeleteObject = async () => {
    if (!rowToDelete?.id) {
      return;
    }

    setIsLoading(true);

    try {
      const mutationString = deleteObject({
        kind:
          rowToDelete.__typename === "AccountTokenNode"
            ? ACCOUNT_TOKEN_OBJECT
            : rowToDelete.__typename,
        data: stringifyWithoutQuotes({
          id: rowToDelete?.id,
        }),
      });

      const mutation = gql`
        ${mutationString}
      `;

      await graphqlClient.mutate({
        mutation,
        context: { branch: branch?.name, date },
      });

      graphqlClient.refetchQueries({ include: [schema.kind!] });

      setDeleteModal(false);

      setRowToDelete(undefined);

      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={`Object ${rowToDelete?.display_label} deleted`}
        />
      );
    } catch (error) {
      console.error("Error while deleting object: ", error);
    }

    setIsLoading(false);
  };

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
    return <ErrorScreen message="Something went wrong when fetching list." />;
  }

  return (
    <>
      <div
        className="rounded-md border overflow-hidden bg-custom-white shadow-sm"
        data-testid="object-items">
        <div className="flex items-center p-2">
          <SearchInput
            loading={loading}
            onChange={debouncedHandleSearch}
            placeholder="Search an object"
            className="border-none focus-visible:ring-0 h-7"
            data-testid="object-list-search-bar"
          />

          <Filters schema={schema} />

          <ObjectCreateFormTrigger schema={schema} onSuccess={onSuccess} isLoading={loading} />
        </div>

        {loading && !rows && <LoadingScreen />}

        {/* TODO: use new Table component for list */}
        {rows && (
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
                    data-cy="object-table-row">
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
                        disabled={!permission.write.allow}
                        tooltipEnabled={!permission.write.allow}
                        tooltipContent={permission.write.message ?? undefined}
                        variant="ghost"
                        onClick={() => {
                          setRowToDelete(row);
                          setDeleteModal(true);
                        }}>
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

      <ModalDelete
        title="Delete"
        description={
          rowToDelete?.display_label || rowToDelete?.name?.value || rowToDelete?.name ? (
            <>
              Are you sure you want to remove the <i>{schema.label}</i>
              <b className="ml-2">
                &quot;{rowToDelete?.display_label || rowToDelete?.name?.value || rowToDelete?.name}
                &quot;
              </b>
              ?
            </>
          ) : (
            <>
              Are you sure you want to remove this <i>{schema.label}</i>?
            </>
          )
        }
        onCancel={() => setDeleteModal(false)}
        onDelete={handleDeleteObject}
        open={!!deleteModal}
        setOpen={() => setDeleteModal(false)}
        isLoading={isLoading}
      />
    </>
  );
}
