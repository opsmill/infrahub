import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { forwardRef, useImperativeHandle, useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import SlideOver from "../../../components/display/slide-over";
import ModalDelete from "../../../components/modals/modal-delete";
import ProgressBar from "../../../components/stats/progress-bar";
import { Table } from "../../../components/table/table";
import { ALERT_TYPES, Alert } from "../../../components/utils/alert";
import { Pagination } from "../../../components/utils/pagination";
import { DEFAULT_BRANCH_NAME, IPAM_PREFIX_OBJECT } from "../../../config/constants";
import graphqlClient from "../../../graphql/graphqlClientApollo";
import { deleteObject } from "../../../graphql/mutations/objects/deleteObject";
import { GET_PREFIXES } from "../../../graphql/queries/ipam/prefixes";
import useQuery from "../../../hooks/useQuery";
import { currentBranchAtom } from "../../../state/atoms/branches.atom";
import { datetimeAtom } from "../../../state/atoms/time.atom";
import { stringifyWithoutQuotes } from "../../../utils/string";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
import ObjectItemEditComponent from "../../object-item-edit/object-item-edit-paginated";
import { constructPathForIpam } from "../common/utils";

const IpamIPPrefixesSummaryList = forwardRef((props, ref) => {
  const { prefix } = useParams();
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [relatedRowToDelete, setRelatedRowToDelete] = useState();
  const [isLoading, setIsLoading] = useState(false);
  const [relatedObjectToEdit, setRelatedObjectToEdit] = useState();

  const constructLink = (data) => {
    switch (data.__typename) {
      case IPAM_PREFIX_OBJECT: {
        return constructPathForIpam(`/ipam/prefixes/${encodeURIComponent(data?.prefix?.value)}`);
      }
      default: {
        return constructPathForIpam(`/ipam/ip_address/${encodeURIComponent(data?.prefix?.value)}`);
      }
    }
  };

  const { loading, error, data, refetch } = useQuery(GET_PREFIXES, {
    variables: { prefix: prefix },
  });

  useImperativeHandle(ref, () => ({ refetch }));

  const columns = [
    { name: "prefix", label: "Prefix" },
    { name: "description", label: "Description" },
    { name: "member_type", label: "Member Type" },
    { name: "is_pool", label: "Is Pool" },
    { name: "is_top_level", label: "Is Top Level" },
    { name: "utilization", label: "Utilization" },
    { name: "ip_namespace", label: "Ip Namespace" },
    { name: "parent", label: "Parent" },
  ];

  const rows =
    data &&
    data[IPAM_PREFIX_OBJECT]?.edges.map((edge) => ({
      id: edge?.node?.id,
      __typename: edge?.node?.__typename,
      values: {
        prefix: edge?.node?.prefix?.value,
        description: edge?.node?.description?.value,
        member_type: edge?.node?.member_type?.value,
        is_pool: edge?.node?.is_pool?.value ? <Icon icon="mdi:check" /> : <Icon icon="mdi:close" />,
        is_top_level: edge?.node?.is_top_level?.value ? (
          <Icon icon="mdi:check" />
        ) : (
          <Icon icon="mdi:close" />
        ),
        utilization: <ProgressBar value={edge?.node?.utilization?.value} />,
        netmask: edge?.node?.netmask?.value,
        hostmask: edge?.node?.hostmask?.value,
        network_address: edge?.node?.network_address?.value,
        broadcast_address: edge?.node?.broadcast_address?.value,
        ip_namespace: edge?.node?.ip_namespace?.node?.display_label,
        parent: edge?.node?.parent?.node?.display_label,
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
          message={`Prefix ${relatedRowToDelete?.values?.prefix} deleted`}
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
      {loading && <LoadingScreen hideText />}

      {data && (
        <Table rows={rows} columns={columns} onDelete={handleDelete} onUpdate={handleUpdate} />
      )}

      {relatedRowToDelete && (
        <ModalDelete
          title="Delete"
          description={
            <>
              Are you sure you want to delete the Prefix:{" "}
              <b>{relatedRowToDelete?.values?.prefix}</b>
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
                      {relatedObjectToEdit?.values?.prefix}
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

      <Pagination count={data && data[IPAM_PREFIX_OBJECT]?.count} />
    </div>
  );
});

export default IpamIPPrefixesSummaryList;
