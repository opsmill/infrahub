import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import SlideOver from "../../../components/display/slide-over";
import ModalDelete from "../../../components/modals/modal-delete";
import { Table } from "../../../components/table/table";
import { ALERT_TYPES, Alert } from "../../../components/utils/alert";
import { Link } from "../../../components/utils/link";
import { Pagination } from "../../../components/utils/pagination";
import { DEFAULT_BRANCH_NAME, IPAM_IP_ADDRESS_OBJECT } from "../../../config/constants";
import graphqlClient from "../../../graphql/graphqlClientApollo";
import { deleteObject } from "../../../graphql/mutations/objects/deleteObject";
import { GET_IP_ADDRESSES } from "../../../graphql/queries/ipam/ip-address";
import useQuery from "../../../hooks/useQuery";
import { currentBranchAtom } from "../../../state/atoms/branches.atom";
import { datetimeAtom } from "../../../state/atoms/time.atom";
import { stringifyWithoutQuotes } from "../../../utils/string";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
import ObjectItemEditComponent from "../../object-item-edit/object-item-edit-paginated";
import { IPAM_QSP, IPAM_TABS } from "../constants";
import { constructPathForIpam } from "../common/utils";

export default function IpamIPAddressesList() {
  const { prefix } = useParams();
  const [isLoading, setIsLoading] = useState(false);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [relatedRowToDelete, setRelatedRowToDelete] = useState();
  const [relatedObjectToEdit, setRelatedObjectToEdit] = useState();

  const constructLink = (data) => {
    if (prefix) {
      return constructPathForIpam(
        `/ipam/prefixes/${encodeURIComponent(prefix)}/${encodeURIComponent(data?.address?.value)}`
      );
    }

    return constructPathForIpam(`/ipam/ip-addresses/${encodeURIComponent(data?.address?.value)}`);
  };

  const { loading, error, data, refetch } = useQuery(GET_IP_ADDRESSES, {
    variables: { prefix: prefix },
  });

  const columns = [
    { name: "address", label: "Address" },
    { name: "description", label: "Description" },
    { name: "interface", label: "Interface" },
    { name: "ip_namespace", label: "Ip Namespace" },
    { name: "ip_prefix", label: "Ip Prefix" },
  ];

  const rows =
    data &&
    data[IPAM_IP_ADDRESS_OBJECT]?.edges.map((edge) => ({
      id: edge?.node?.id,
      __typename: edge?.node?.__typename,
      values: {
        address: edge?.node?.address?.value,
        description: edge?.node?.description?.value,
        interface: edge?.node?.interface?.node?.display_label,
        ip_namespace: edge?.node?.ip_namespace?.node?.display_label,
        ip_prefix: edge?.node?.ip_prefix?.node?.display_label,
      },
      link: constructLink(edge?.node),
    }));

  const handleUpdate = (data) => {
    setRelatedObjectToEdit(data);
  };

  const handleDelete = (data) => {
    console.log("data: ", data);
    setRelatedRowToDelete(data);
  };

  const handleDeleteObject = async () => {
    console.log("relatedRowToDelete: ", relatedRowToDelete);
    if (!relatedRowToDelete?.id) {
      return;
    }

    setIsLoading(true);

    try {
      const mutationString = deleteObject({
        kind: relatedRowToDelete?.__typename,
        data: stringifyWithoutQuotes({
          id: relatedRowToDelete?.id,
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

      setRelatedRowToDelete(undefined);

      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={`Address ${relatedRowToDelete?.values?.address} deleted`}
        />
      );
    } catch (error) {
      console.error("Error while deleting address: ", error);
    }

    setIsLoading(false);
  };

  if (error) {
    return <ErrorScreen message="An error occured while retrieving prefixes" />;
  }

  return (
    <div>
      {prefix && (
        <div className="flex items-center mb-2">
          <span className="mr-2">Prefix:</span>
          <Link
            to={constructPathForIpam(
              `/ipam/prefixes/${encodeURIComponent(prefix)}?${IPAM_QSP}=${IPAM_TABS.PREFIX_DETAILS}`
            )}>
            {prefix}
          </Link>
        </div>
      )}

      {loading && <LoadingScreen hideText />}

      {data && (
        <Table rows={rows} columns={columns} onDelete={handleDelete} onUpdate={handleUpdate} />
      )}

      {relatedRowToDelete && (
        <ModalDelete
          title="Delete"
          description={
            <>
              Are you sure you want to delete the IP address:{" "}
              <b>{relatedRowToDelete?.values?.address}</b>
            </>
          }
          onCancel={() => setRelatedRowToDelete(undefined)}
          onDelete={handleDeleteObject}
          open={!!relatedRowToDelete}
          setOpen={() => setRelatedRowToDelete(undefined)}
          isLoading={isLoading}
        />
      )}

      {relatedObjectToEdit && (
        <SlideOver
          title={
            <>
              {
                <div className="space-y-2">
                  <div className="flex items-center w-full">
                    <span className="text-lg font-semibold mr-3">
                      {relatedObjectToEdit?.values?.address}
                    </span>
                    <div className="flex-1"></div>
                    <div className="flex items-center">
                      <Icon icon={"mdi:layers-triple"} />
                      <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
                    </div>
                  </div>
                  <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20 mr-2">
                    <svg
                      className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                      viewBox="0 0 6 6"
                      aria-hidden="true">
                      <circle cx={3} cy={3} r={3} />
                    </svg>
                    {relatedObjectToEdit?.__typename}
                  </span>
                </div>
              }
            </>
          }
          open={!!relatedObjectToEdit}
          setOpen={() => setRelatedObjectToEdit(undefined)}>
          <ObjectItemEditComponent
            closeDrawer={() => {
              setRelatedObjectToEdit(undefined);
            }}
            onUpdateComplete={async () => {
              setRelatedObjectToEdit(undefined);
              if (refetch) {
                refetch();
              }
            }}
            objectid={relatedObjectToEdit.id}
            objectname={relatedObjectToEdit.__typename}
          />
        </SlideOver>
      )}

      <Pagination count={data && data[IPAM_IP_ADDRESS_OBJECT]?.count} />
    </div>
  );
}
