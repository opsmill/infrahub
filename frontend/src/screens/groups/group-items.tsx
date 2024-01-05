import { gql } from "@apollo/client";
import { TrashIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import { useContext, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { BUTTON_TYPES, Button } from "../../components/buttons/button";
import ModalDelete from "../../components/modals/modal-delete";
import { ALERT_TYPES, Alert } from "../../components/utils/alert";
import { Pagination } from "../../components/utils/pagination";
import { GROUP_OBJECT } from "../../config/constants";
import { AuthContext } from "../../decorators/withAuth";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { deleteObject } from "../../graphql/mutations/objects/deleteObject";
import { getGroups } from "../../graphql/queries/groups/getGroups";
import usePagination from "../../hooks/usePagination";
import useQuery from "../../hooks/useQuery";
import { useTitle } from "../../hooks/useTitle";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { datetimeAtom } from "../../state/atoms/time.atom";
import { classNames } from "../../utils/common";
import { constructPath } from "../../utils/fetch";
import { getObjectItemDisplayValue } from "../../utils/getObjectItemDisplayValue";
import { getGroupColumns } from "../../utils/getSchemaObjectColumns";
import { getObjectDetailsUrl } from "../../utils/objects";
import { stringifyWithoutQuotes } from "../../utils/string";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";

export default function GroupItems() {
  const { groupname } = useParams();

  const kind = groupname || GROUP_OBJECT;

  const auth = useContext(AuthContext);
  const [schemaKindName] = useAtom(schemaKindNameState);
  const [schemaList] = useAtom(schemaState);
  const [genericList] = useAtom(genericsState);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [pagination] = usePagination();
  const [rowToDelete, setRowToDelete] = useState<any>();
  const [deleteModal, setDeleteModal] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const navigate = useNavigate();
  useTitle(groupname ? `${groupname} details` : "Groups list");

  const schemaData =
    genericList.find((s) => s.kind === kind) || schemaList.find((s) => s.kind === kind);

  // All the fiter values are being sent out as strings inside quotes.
  // This will not work if the type of filter value is not string.
  const filtersString = [
    // Add pagination filters
    ...[
      { name: "offset", value: pagination?.offset },
      { name: "limit", value: pagination?.limit },
    ].map((row: any) => `${row.name}: ${row.value}`),
  ].join(",");

  // Get all the needed columns (attributes + relationships)
  const columns = getGroupColumns(schemaData);

  const queryString = schemaData
    ? getGroups({
        attributes: schemaData.attributes,
        filters: filtersString,
        groupKind: kind,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schemaData
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data = {}, refetch } = useQuery(query, { skip: !schemaData });

  const result = data && schemaData?.kind ? data[schemaData?.kind] ?? {} : {};

  const { count, edges } = result;

  const rows = edges?.map((edge: any) => edge.node);

  const handleDeleteObject = async () => {
    if (!rowToDelete?.id) {
      return;
    }

    setIsLoading(true);

    const mutationString = deleteObject({
      kind: schemaKindName[rowToDelete.__typename],
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

    setIsLoading(false);

    setRowToDelete(undefined);

    toast(
      <Alert type={ALERT_TYPES.SUCCESS} message={`Object ${rowToDelete?.display_label} deleted`} />
    );
  };

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the group items." />;
  }

  return (
    <div className="bg-custom-white flex-1 flex flex-col">
      <div className="flex items-center p-4 w-full">
        {schemaData && (
          <div className="sm:flex-auto flex items-center">
            <div className="text-md font-semibold text-gray-900">
              {schemaData.name} ({count})
            </div>
          </div>
        )}
      </div>

      {loading && !rows && <LoadingScreen />}

      {!loading && rows && (
        <div className="flex-1 shadow-sm ring-1 ring-custom-black ring-opacity-5 overflow-x-auto">
          <table className="min-w-full border-separate" style={{ borderSpacing: 0 }}>
            <thead className="bg-gray-50">
              <tr>
                {columns?.map((attribute) => (
                  <th
                    key={attribute.name}
                    scope="col"
                    className="sticky top-0 border-b border-gray-300 bg-gray-50 bg-opacity-75 px-4 py-2 text-left text-xs font-semibold text-gray-900 backdrop-blur backdrop-filter">
                    {attribute.label}
                  </th>
                ))}
                <th
                  scope="col"
                  className="sticky top-0 border-b border-gray-300 bg-gray-50 bg-opacity-75 px-4 py-2 text-left text-xs font-semibold text-gray-900 backdrop-blur backdrop-filter"></th>
              </tr>
            </thead>
            <tbody className="bg-custom-white">
              {rows?.map((row: any, index: number) => (
                <tr
                  onClick={() =>
                    navigate(constructPath(getObjectDetailsUrl(row.id, row.__typename)))
                  }
                  key={index}
                  className="hover:bg-gray-50 cursor-pointer">
                  {columns?.map((attribute) => (
                    <td
                      key={row.id + "-" + attribute.name}
                      className={classNames(
                        index !== rows.length - 1 ? "border-b border-gray-200" : "",
                        "whitespace-wrap p-4 text-xs text-gray-900"
                      )}>
                      {getObjectItemDisplayValue(row, attribute, schemaKindName)}
                    </td>
                  ))}

                  <td
                    className={classNames(
                      index !== rows.length - 1 ? "border-b border-gray-200" : "",
                      "whitespace-wrap p-4 text-xs text-gray-900"
                    )}>
                    <Button
                      disabled={!auth?.permissions?.write}
                      buttonType={BUTTON_TYPES.INVISIBLE}
                      onClick={() => {
                        setRowToDelete(row);
                        setDeleteModal(true);
                      }}>
                      <TrashIcon className="w-4 h-4 text-red-500" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {!rows?.length && <NoDataFound message="No group items found." />}

          <Pagination count={count} />
        </div>
      )}

      <ModalDelete
        title="Delete"
        description={
          <>
            Are you sure you want to remove the group <br /> <b>`{rowToDelete?.display_label}`</b>?
          </>
        }
        onCancel={() => setDeleteModal(false)}
        onDelete={handleDeleteObject}
        open={!!deleteModal}
        setOpen={() => setDeleteModal(false)}
        isLoading={isLoading}
      />
    </div>
  );
}
