import { gql } from "@apollo/client";
import { PlusIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai/index";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { BUTTON_TYPES } from "../../components/buttons/button";
import { ButtonWithTooltip } from "../../components/buttons/button-with-tooltip";
import { Retry } from "../../components/buttons/retry";
import { RoundedButton } from "../../components/buttons/rounded-button";
import SlideOver from "../../components/display/slide-over";
import ModalDelete from "../../components/modals/modal-delete";
import { SearchInput } from "../../components/search/search-bar";
import { Tooltip } from "../../components/ui/tooltip";
import { ALERT_TYPES, Alert } from "../../components/utils/alert";
import { Pagination } from "../../components/utils/pagination";
import {
  DEFAULT_BRANCH_NAME,
  MENU_EXCLUDELIST,
  SEARCH_ANY_FILTER,
  SEARCH_FILTERS,
  SEARCH_PARTIAL_MATCH,
} from "../../config/constants";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { deleteObject } from "../../graphql/mutations/objects/deleteObject";
import { getObjectItemsPaginated } from "../../graphql/queries/objects/getObjectItems";
import useFilters, { Filter } from "../../hooks/useFilters";
import usePagination from "../../hooks/usePagination";
import { usePermission } from "../../hooks/usePermission";
import useQuery from "../../hooks/useQuery";
import { useTitle } from "../../hooks/useTitle";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { iComboBoxFilter } from "../../state/atoms/filters.atom";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { datetimeAtom } from "../../state/atoms/time.atom";
import { debounce } from "../../utils/common";
import { constructPath } from "../../utils/fetch";
import { getObjectItemDisplayValue } from "../../utils/getObjectItemDisplayValue";
import {
  getObjectAttributes,
  getObjectRelationships,
  getSchemaObjectColumns,
} from "../../utils/getSchemaObjectColumns";
import { getObjectDetailsUrl } from "../../utils/objects";
import { stringifyWithoutQuotes } from "../../utils/string";
import ErrorScreen from "../error-screen/error-screen";
import Content from "../layout/content";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";
import ObjectItemCreate from "../object-item-create/object-item-create-paginated";

export default function ObjectItems(props: any) {
  const { objectname: objectnameFromParams } = useParams();

  const {
    objectname: objectnameFromProps = "",
    filters: filtersFromProps = [],
    preventBlock,
  } = props;

  const objectname = objectnameFromProps || objectnameFromParams;

  const navigate = useNavigate();

  const permission = usePermission();
  const [filters, setFilters] = useFilters();
  const [pagination] = usePagination();

  const schemaKindName = useAtomValue(schemaKindNameState);
  const schemaList = useAtomValue(schemaState);
  const genericList = useAtomValue(genericsState);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  const [showCreateDrawer, setShowCreateDrawer] = useState(false);
  const [rowToDelete, setRowToDelete] = useState<any>();
  const [deleteModal, setDeleteModal] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const schema = schemaList.find((s) => s.kind === objectname);
  const generic = genericList.find((s) => s.kind === objectname);

  const schemaData = schema || generic;

  if ((schemaList?.length || genericList?.length) && !schemaData) {
    // If there is no schema nor generics, go to home page
    navigate("/");
    return null;
  }

  if (schemaData && MENU_EXCLUDELIST.includes(schemaData.kind) && !preventBlock) {
    navigate("/");
    return null;
  }

  // All the fiter values are being sent out as strings inside quotes.
  // This will not work if the type of filter value is not string.
  const filtersString = [
    // Add object filters
    ...filters.map((row: iComboBoxFilter) =>
      typeof row.value === "string" ? `${row.name}: "${row.value}"` : `${row.name}: ${row.value}`
    ),
    // Add pagination filters
    ...[
      { name: "offset", value: pagination?.offset },
      { name: "limit", value: pagination?.limit },
    ].map((row: any) => `${row.name}: ${row.value}`),
    ...filtersFromProps,
  ].join(",");

  // Get all the needed columns (attributes + relationships)
  const columns = getSchemaObjectColumns(schemaData, true);
  const attributes = getObjectAttributes(schemaData, true);
  const relationships = getObjectRelationships(schemaData, true);

  const queryString = getObjectItemsPaginated({
    kind: objectname,
    attributes,
    relationships,
    filters: filtersString,
  });

  const query = gql`
    ${queryString}
  `;

  const {
    loading,
    error,
    data = {},
    refetch,
  } = useQuery(query, { skip: !schemaData, notifyOnNetworkStatusChange: true });

  const result = data && schemaData?.kind ? data[schemaData?.kind] ?? {} : {};

  const { count = "...", edges } = result;

  useTitle(`${schemaKindName[objectname]} list`);

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

      refetch();

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

  const handleRefetch = () => refetch();

  const handleSearch = (value: string) => {
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

  const debouncedHandleSearch = debounce(handleSearch);

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching list." />;
  }

  return (
    <Content className="">
      <div className="flex items-center p-4 w-full bg-custom-white shadow-sm">
        {schemaData && (
          <div className="sm:flex-auto flex items-center">
            <h1 className="text-md font-semibold text-gray-900 mr-2">
              {schemaData.label} ({count})
            </h1>

            <div className="text-sm">{schemaData?.description}</div>

            <div className="ml-2">
              <Retry isLoading={loading} onClick={handleRefetch} />
            </div>
          </div>
        )}

        {schema && (
          <Tooltip
            enabled={!permission.write.allow}
            content={permission.write.message ?? undefined}>
            <RoundedButton
              data-cy="create"
              data-testid="create-object-button"
              disabled={!permission.write.allow}
              onClick={() => setShowCreateDrawer(true)}>
              <PlusIcon className="w-4 h-4" aria-hidden="true" />
            </RoundedButton>
          </Tooltip>
        )}
      </div>

      <div className="m-2 rounded-md border overflow-hidden bg-custom-white shadow-sm">
        <div className="flex items-cente">
          <SearchInput
            loading={loading}
            onChange={debouncedHandleSearch}
            placeholder="Search an object"
            testId="object-list-search-bar"
            className="!shadow-none !ring-0"
            containerClassName="!max-w-[300px] !z-0"
          />
        </div>

        {loading && !rows && <LoadingScreen />}

        {/* TODO: use new Table component for lsit */}
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
                          to={constructPath(getObjectDetailsUrl(row.id, row.__typename))}>
                          <div>{getObjectItemDisplayValue(row, attribute)}</div>
                        </Link>
                      </td>
                    ))}

                    <td className="text-right w-8">
                      <ButtonWithTooltip
                        data-cy="delete"
                        disabled={!permission.write.allow}
                        tooltipEnabled={!permission.write.allow}
                        tooltipContent={permission.write.message ?? undefined}
                        buttonType={BUTTON_TYPES.INVISIBLE}
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
              <span className="text-lg font-semibold mr-3">Create {schemaData?.label}</span>
              <div className="flex-1"></div>
              <div className="flex items-center">
                <Icon icon={"mdi:layers-triple"} />
                <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
              </div>
            </div>

            <div className="text-sm">{schemaData?.description}</div>

            <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20 mr-2">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              {schemaData?.kind}
            </span>
          </div>
        }
        open={showCreateDrawer}
        setOpen={setShowCreateDrawer}>
        <ObjectItemCreate
          onCreate={() => setShowCreateDrawer(false)}
          onCancel={() => setShowCreateDrawer(false)}
          objectname={objectname!}
          refetch={refetch}
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
    </Content>
  );
}
