import { Button, ButtonWithTooltip } from "@/components/buttons/button-primitive";
import SlideOver from "@/components/display/slide-over";
import { Filters } from "@/components/filters/filters";
import ModalDelete from "@/components/modals/modal-delete";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { Pagination } from "@/components/ui/pagination";
import { SearchInput, SearchInputProps } from "@/components/ui/search-input";
import { Tooltip } from "@/components/ui/tooltip";
import {
  DEFAULT_BRANCH_NAME,
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
import ObjectForm from "@/components/form/object-form";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { debounce } from "@/utils/common";
import { constructPath } from "@/utils/fetch";
import { getObjectItemDisplayValue } from "@/utils/getObjectItemDisplayValue";
import { getSchemaObjectColumns } from "@/utils/getSchemaObjectColumns";
import { getObjectDetailsUrl } from "@/utils/objects";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai/index";
import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { toast } from "react-toastify";
import { useObjectItems } from "@/hooks/useObjectItems";

type ObjectItemsProps = {
  schema: IModelSchema;
  preventBlock?: boolean;
  overrideDetailsViewUrl?: (objectId: string, objectKind: string) => string;
};

export default function ObjectItems({
  schema,
  overrideDetailsViewUrl,
  preventBlock,
}: ObjectItemsProps) {
  const permission = usePermission();
  const [filters, setFilters] = useFilters();

  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  const [showCreateDrawer, setShowCreateDrawer] = useState(false);
  const [rowToDelete, setRowToDelete] = useState<any>();
  const [deleteModal, setDeleteModal] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  if (schema && MENU_EXCLUDELIST.includes(schema.kind as string) && !preventBlock) {
    return <Navigate to="/" />;
  }

  // Get all the needed columns (attributes + relationships)
  const columns = getSchemaObjectColumns({ schema: schema, forListView: true });

  const { loading, error, data = {} } = useObjectItems(schema, filters);

  const result = data && schema?.kind ? data[schema?.kind] ?? {} : {};

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
        kind: rowToDelete.__typename,
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

      toast(() => (
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={`Object ${rowToDelete?.display_label} deleted`}
        />
      ));
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

          <Tooltip
            enabled={!permission.write.allow}
            content={permission.write.message ?? undefined}>
            <Button
              data-cy="create"
              data-testid="create-object-button"
              disabled={!permission.write.allow}
              onClick={() => setShowCreateDrawer(true)}
              size="sm">
              <Icon icon="mdi:plus" className="text-sm" />
              Add {schema?.label}
            </Button>
          </Tooltip>
        </div>

        {loading && !rows && <LoadingScreen />}

        {/* TODO: use new Table component for list */}
        {rows && (
          <div className="overflow-auto">
            <table className="table-auto border-spacing-0 w-full">
              <thead className="bg-gray-50 text-left border-y border-gray-300">
                <tr>
                  {columns?.map((attribute) => (
                    <th
                      key={attribute.name}
                      scope="col"
                      className="p-2 text-xs font-semibold text-gray-900">
                      {attribute.label}
                    </th>
                  ))}
                  <th scope="col"></th>
                </tr>
              </thead>

              <tbody className="bg-custom-white text-left">
                {rows?.map((row: any, index: number) => (
                  <tr
                    key={index}
                    className="border-b border-gray-200 hover:bg-gray-50 cursor-pointer h-[36px]"
                    data-cy="object-table-row">
                    {columns?.map((attribute) => (
                      <td key={row.id + "-" + attribute.name} className="p-0">
                        <Link
                          className="whitespace-wrap px-2 py-1 text-xs text-gray-900 flex items-center"
                          to={
                            overrideDetailsViewUrl
                              ? overrideDetailsViewUrl(row.id, row.__typename)
                              : constructPath(getObjectDetailsUrl(row.id, row.__typename))
                          }>
                          <div>{getObjectItemDisplayValue(row, attribute)}</div>
                        </Link>
                      </td>
                    ))}

                    <td className="text-right w-8">
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

      <SlideOver
        title={
          <div className="space-y-2">
            <div className="flex items-center w-full">
              <span className="text-lg font-semibold mr-3">Create {schema?.label}</span>
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
        open={showCreateDrawer}
        setOpen={setShowCreateDrawer}>
        <ObjectForm
          onSuccess={async () => {
            setShowCreateDrawer(false);
            await graphqlClient.refetchQueries({ include: [schema.kind!] });
          }}
          onCancel={() => setShowCreateDrawer(false)}
          kind={schema.kind!}
        />
      </SlideOver>

      <ModalDelete
        title="Delete"
        description={
          <>
            Are you sure you want to remove the object <br /> <b>`{rowToDelete?.display_label}`</b>?
          </>
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
