import { gql, useReactiveVar } from "@apollo/client";
import { TrashIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/alert";
import { BUTTON_TYPES, Button } from "../../components/button";
import ModalDelete from "../../components/modal-delete";
import { Pagination } from "../../components/pagination";
import { GROUP_OBJECT } from "../../config/constants";
import { AuthContext } from "../../decorators/withAuth";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { deleteObject } from "../../graphql/mutations/objects/deleteObject";
import { getGroups } from "../../graphql/queries/groups/getGroups";
import { branchVar } from "../../graphql/variables/branchVar";
import { dateVar } from "../../graphql/variables/dateVar";
import usePagination from "../../hooks/usePagination";
import useQuery from "../../hooks/useQuery";
import { genericsState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { classNames } from "../../utils/common";
import { constructPath } from "../../utils/fetch";
import { getObjectItemDisplayValue } from "../../utils/getObjectItemDisplayValue";
import { getGroupColumns } from "../../utils/getSchemaObjectColumns";
import { getGroupDetailsUrl } from "../../utils/objects";
import { stringifyWithoutQuotes } from "../../utils/string";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";

export default function GroupItems() {
  const auth = useContext(AuthContext);

  const [schemaKindName] = useAtom(schemaKindNameState);
  const [genericList] = useAtom(genericsState);
  const branch = useReactiveVar(branchVar);
  const date = useReactiveVar(dateVar);
  const [pagination] = usePagination();
  const [rowToDelete, setRowToDelete] = useState<any>();
  const [deleteModal, setDeleteModal] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const navigate = useNavigate();

  const schemaData = genericList.filter((s) => s.name === GROUP_OBJECT)[0];

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
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schemaData
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data = {}, refetch } = useQuery(query, { skip: !schemaData });

  const result = data ? data[schemaData?.kind] ?? {} : {};

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
    console.log("Error while loading objects list: ", error);
    return <ErrorScreen />;
  }

  return (
    <div className="bg-custom-white flex-1 overflow-x-auto flex flex-col">
      <div className="sm:flex sm:items-center py-4 px-4 sm:px-6 lg:px-8 w-full">
        {schemaData && (
          <div className="sm:flex-auto flex items-center">
            <div className="text-xl font-semibold text-gray-900">
              {schemaData.name} ({count})
            </div>
            <p className="mt-2 text-sm text-gray-700 m-0 pl-2 mb-1">
              A list of all the {schemaData.kind} in your infrastructure.
            </p>
          </div>
        )}
      </div>

      {loading && !rows && <LoadingScreen />}

      {!loading && rows && (
        <div className="mt-0 flex flex-col px-4 sm:px-6 lg:px-8 w-full overflow-x-auto flex-1">
          <div className="-my-2 -mx-4 sm:-mx-6 lg:-mx-8">
            <div className="inline-block min-w-full pt-2 align-middle">
              <div className="shadow-sm ring-1 ring-custom-black ring-opacity-5">
                <table className="min-w-full border-separate" style={{ borderSpacing: 0 }}>
                  <thead className="bg-gray-50">
                    <tr>
                      {columns?.map((attribute) => (
                        <th
                          key={attribute.name}
                          scope="col"
                          className="sticky top-0 border-b border-gray-300 bg-gray-50 bg-opacity-75 py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter sm:pl-6 lg:pl-8">
                          {attribute.label}
                        </th>
                      ))}
                      <th
                        scope="col"
                        className="sticky top-0 border-b border-gray-300 bg-gray-50 bg-opacity-75 py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter sm:pl-6 lg:pl-8"></th>
                    </tr>
                  </thead>
                  <tbody className="bg-custom-white">
                    {rows?.map((row: any, index: number) => (
                      <tr
                        onClick={() =>
                          navigate(
                            constructPath(
                              getGroupDetailsUrl(row.id, row.__typename, schemaKindName)
                            )
                          )
                        }
                        key={index}
                        className="hover:bg-gray-50 cursor-pointer">
                        {columns?.map((attribute) => (
                          <td
                            key={row.id + "-" + attribute.name}
                            className={classNames(
                              index !== rows.length - 1 ? "border-b border-gray-200" : "",
                              "whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6 lg:pl-8"
                            )}>
                            {getObjectItemDisplayValue(row, attribute, schemaKindName)}
                          </td>
                        ))}

                        <td
                          className={classNames(
                            index !== rows.length - 1 ? "border-b border-gray-200" : "",
                            "whitespace-nowrap py-3 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6 lg:pl-8 flex items-center justify-end"
                          )}>
                          <Button
                            disabled={!auth?.permissions?.write}
                            buttonType={BUTTON_TYPES.INVISIBLE}
                            onClick={() => {
                              setRowToDelete(row);
                              setDeleteModal(true);
                            }}>
                            <TrashIcon className="w-6 h-6 text-red-500" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {!rows?.length && <NoDataFound />}

                <Pagination count={count} />
              </div>
            </div>
          </div>
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
