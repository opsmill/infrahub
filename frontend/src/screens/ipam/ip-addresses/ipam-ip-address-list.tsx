import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { forwardRef, useImperativeHandle, useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import SlideOver from "../../../components/display/slide-over";
import ModalDelete from "../../../components/modals/modal-delete";
import { Table } from "../../../components/table/table";
import { ALERT_TYPES, Alert } from "../../../components/utils/alert";
import { Link } from "../../../components/utils/link";
import { Pagination } from "../../../components/utils/pagination";
import { DEFAULT_BRANCH_NAME } from "../../../config/constants";
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
import { constructPathForIpam } from "../common/utils";
import {
  IPAM_QSP,
  IPAM_ROUTE,
  IPAM_TABS,
  IP_ADDRESS_GENERIC,
  IP_PREFIX_GENERIC,
} from "../constants";
import { GET_PREFIX_KIND } from "../../../graphql/queries/ipam/prefixes";

const IpamIPAddressesList = forwardRef((props, ref) => {
  const { prefix } = useParams();
  const [isLoading, setIsLoading] = useState(false);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [relatedRowToDelete, setRelatedRowToDelete] = useState();
  const [relatedObjectToEdit, setRelatedObjectToEdit] = useState();

  const constructLink = (data) => {
    if (prefix) {
      return constructPathForIpam(`${IPAM_ROUTE.PREFIXES}/${prefix}/${data?.id}`);
    }

    return constructPathForIpam(`${IPAM_ROUTE.ADDRESSES}/${data?.id}`);
  };

  const { loading, error, data, refetch } = useQuery(GET_IP_ADDRESSES, {
    variables: { prefixIds: prefix ? [prefix] : null },
  });

  const { data: getPrefixKindData } = useQuery(GET_PREFIX_KIND, {
    variables: { ids: [prefix] },
    skip: !prefix,
  });

  const prefixData = getPrefixKindData?.[IP_PREFIX_GENERIC]?.edges?.[0]?.node;

  // Provide refetch function to parent
  useImperativeHandle(ref, () => ({ refetch }));

  const columns = [
    { name: "address", label: "Address" },
    { name: "description", label: "Description" },
    { name: "ip_namespace", label: "IP Namespace" },
    // Display prefix column only in main list
    !prefix && { name: "ip_prefix", label: "IP Prefix" },
  ].filter(Boolean);

  const rows =
    data &&
    data[IP_ADDRESS_GENERIC]?.edges.map((edge) => ({
      id: edge?.node?.id,
      __typename: edge?.node?.__typename,
      values: {
        address: edge?.node?.address?.value,
        description: edge?.node?.description?.value,
        ip_namespace: edge?.node?.ip_namespace?.node?.display_label,
        ip_prefix: edge?.node?.ip_prefix?.node?.display_label,
      },
      link: constructLink(edge?.node),
    }));

  const handleUpdate = (data) => {
    setRelatedObjectToEdit(data);
  };

  const handleDelete = (data) => {
    setRelatedRowToDelete(data);
  };

  const handleDeleteObject = async () => {
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
    return <ErrorScreen message="An error occurred while retrieving prefixes" />;
  }

  return (
    <div>
      {prefixData && (
        <div className="flex items-center mb-2">
          <Link
            to={constructPathForIpam(`${IPAM_ROUTE.PREFIXES}/${prefixData.id}`, [
              { name: IPAM_QSP, value: IPAM_TABS.PREFIX_DETAILS },
            ])}>
            {prefixData.display_label}
          </Link>

          <Icon icon="mdi:chevron-right" />

          <span>IP Addresses</span>
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

      <Pagination count={data && data[IP_ADDRESS_GENERIC]?.count} />
    </div>
  );
});

export default IpamIPAddressesList;
