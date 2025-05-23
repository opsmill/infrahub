import { DEFAULT_BRANCH_NAME } from "@/config/constants";
import { currentBranchAtom } from "@/entities/branches/stores";
import { GET_PREFIXES } from "@/entities/ipam/api/prefixes";
import { constructPathForIpam } from "@/entities/ipam/common/utils";
import { IPAM_ROUTE, IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import { reloadIpamTreeAtom } from "@/entities/ipam/ipam-tree/ipam-tree.state";
import { useCurrentIpNamespace } from "@/entities/ipam/namespaces/ui/ip-namespace-provider";
import { deleteObject } from "@/entities/nodes/api/deleteObject";
import ObjectItemEditComponent from "@/entities/nodes/object-item-edit/object-item-edit-paginated";
import { getPermission } from "@/entities/permission/utils";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import useQuery from "@/shared/api/graphql/useQuery";
import SlideOver from "@/shared/components/display/slide-over";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import ModalDelete from "@/shared/components/modals/modal-delete";
import ProgressBarChart from "@/shared/components/stats/progress-bar-chart";
import { Table } from "@/shared/components/table/table";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Pagination } from "@/shared/components/ui/pagination";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { stringifyWithoutQuotes } from "@/shared/utils/string";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue, useSetAtom } from "jotai";
import { forwardRef, useImperativeHandle, useState } from "react";
import { useParams } from "react-router";
import { toast } from "react-toastify";

const IpamIPPrefixesSummaryList = forwardRef((_, ref) => {
  const { prefix } = useParams();
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const { currentIpNamespace } = useCurrentIpNamespace();
  const [relatedRowToDelete, setRelatedRowToDelete] = useState();
  const [isLoading, setIsLoading] = useState(false);
  const [relatedObjectToEdit, setRelatedObjectToEdit] = useState();
  const reloadIpamTree = useSetAtom(reloadIpamTreeAtom);

  const { loading, error, data, refetch } = useQuery(GET_PREFIXES, {
    variables: { namespaces: currentIpNamespace.id },
  });

  useImperativeHandle(ref, () => ({ refetch }));

  const permission = getPermission(data?.[IP_PREFIX_GENERIC]?.permissions?.edges);

  const columns = [
    { name: "prefix", label: "Prefix" },
    { name: "description", label: "Description" },
    { name: "member_type", label: "Member Type" },
    { name: "is_pool", label: "Is Pool" },
    { name: "is_top_level", label: "Is Top Level" },
    { name: "utilization", label: "Utilization" },
    { name: "ip_namespace", label: "IP Namespace" },
    { name: "parent", label: "Parent" },
  ];

  const rows =
    data &&
    data[IP_PREFIX_GENERIC]?.edges.map((edge) => ({
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
        utilization: <ProgressBarChart value={edge?.node?.utilization?.value} />,
        netmask: edge?.node?.netmask?.value,
        hostmask: edge?.node?.hostmask?.value,
        network_address: edge?.node?.network_address?.value,
        broadcast_address: edge?.node?.broadcast_address?.value,
        ip_namespace: edge?.node?.ip_namespace?.node?.display_label,
        parent: edge?.node?.parent?.node?.display_label,
      },
      link: constructPathForIpam(`${IPAM_ROUTE.PREFIXES}/${edge?.node?.id}`),
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

      if (currentIpNamespace) {
        reloadIpamTree(currentIpNamespace.id, prefix);
      }

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
    return <ErrorScreen message="An error occurred while retrieving prefixes" />;
  }

  return (
    <div className="w-full">
      {loading && <LoadingIndicator />}

      {data && (
        <Table
          rows={rows}
          columns={columns}
          onDelete={handleDelete}
          onUpdate={handleUpdate}
          permission={permission}
        />
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
                      aria-hidden="true"
                    >
                      <circle cx={3} cy={3} r={3} />
                    </svg>
                    {relatedObjectToEdit?.__typename}
                  </span>
                </div>
              }
            </>
          }
          open={!!relatedObjectToEdit}
          setOpen={() => setRelatedObjectToEdit(undefined)}
        >
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

      <Pagination count={data && data[IP_PREFIX_GENERIC]?.count} />
    </div>
  );
});

export default IpamIPPrefixesSummaryList;
