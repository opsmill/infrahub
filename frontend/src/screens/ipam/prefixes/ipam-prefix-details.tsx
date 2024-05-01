import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { forwardRef, useImperativeHandle, useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import SlideOver from "../../../components/display/slide-over";
import ModalDelete from "../../../components/modals/modal-delete";
import ProgressBarChart from "../../../components/stats/progress-bar-chart";
import { Table } from "../../../components/table/table";
import { Tooltip } from "../../../components/ui/tooltip";
import { ALERT_TYPES, Alert } from "../../../components/utils/alert";
import { Link } from "../../../components/utils/link";
import { Pagination } from "../../../components/utils/pagination";
import { DEFAULT_BRANCH_NAME } from "../../../config/constants";
import graphqlClient from "../../../graphql/graphqlClientApollo";
import { deleteObject } from "../../../graphql/mutations/objects/deleteObject";
import { GET_PREFIX } from "../../../graphql/queries/ipam/prefixes";
import useQuery from "../../../hooks/useQuery";
import { currentBranchAtom } from "../../../state/atoms/branches.atom";
import { genericsState } from "../../../state/atoms/schema.atom";
import { datetimeAtom } from "../../../state/atoms/time.atom";
import { stringifyWithoutQuotes } from "../../../utils/string";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
import ObjectItemEditComponent from "../../object-item-edit/object-item-edit-paginated";
import { constructPathForIpam } from "../common/utils";
import { IPAM_ROUTE, IP_ADDRESS_GENERIC, IP_PREFIX_GENERIC } from "../constants";

const IpamIPPrefixDetails = forwardRef((props, ref) => {
  const { prefix } = useParams();
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [relatedRowToDelete, setRelatedRowToDelete] = useState();
  const [relatedObjectToEdit, setRelatedObjectToEdit] = useState();
  const [isLoading, setIsLoading] = useState(false);
  const generics = useAtomValue(genericsState);

  const prefixSchema = generics.find(({ kind }) => kind === IP_PREFIX_GENERIC);
  const adressSchema = generics.find(({ kind }) => kind === IP_ADDRESS_GENERIC);

  const { loading, error, data, refetch } = useQuery(GET_PREFIX, {
    variables: { prefix: prefix },
  });

  useImperativeHandle(ref, () => ({ refetch }));

  if (!prefix) {
    return <div>Select a Prefix in the Tree to the left to see details</div>;
  }

  const parent = data && data[IP_PREFIX_GENERIC]?.edges[0]?.node?.parent?.node;

  const children = data && data[IP_PREFIX_GENERIC]?.edges[0]?.node?.children;

  const memberIcons: Record<string, any> = {
    address: prefixSchema?.icon ? (
      <Tooltip content="Prefix" enabled>
        <Icon icon={prefixSchema.icon as string} />
      </Tooltip>
    ) : (
      ""
    ),
    prefix: adressSchema?.icon ? (
      <Tooltip content="IP Adress" enabled>
        <Icon icon={adressSchema.icon as string} />
      </Tooltip>
    ) : (
      ""
    ),
  };

  const columns = [
    { name: "prefix", label: "Prefix" },
    { name: "description", label: "Description" },
    { name: "member_type", label: "Member Type" },
    { name: "is_pool", label: "Is Pool" },
    { name: "utilization", label: "Utilization" },
    { name: "ip_namespace", label: "IP Namespace" },
  ];

  const rows = children?.edges?.map((child) => ({
    id: child?.node?.id,
    __typename: child?.node?.__typename,
    values: {
      prefix: child?.node?.prefix?.value,
      description: child?.node?.description?.value,
      member_type:
        child?.node?.member_type?.value && memberIcons[child?.node?.member_type?.value]
          ? memberIcons[child?.node?.member_type?.value]
          : child?.node?.member_type?.value ?? "-",
      is_pool: child?.node?.is_pool?.value ? <Icon icon="mdi:check" /> : <Icon icon="mdi:close" />,
      utilization: <ProgressBarChart value={child?.node?.utilization?.value} />,
      netmask: child?.node?.netmask?.value,
      hostmask: child?.node?.hostmask?.value,
      network_address: child?.node?.network_address?.value,
      broadcast_address: child?.node?.broadcast_address?.value,
      ip_namespace: child?.node?.ip_namespace?.node?.display_label,
    },
    link: constructPathForIpam(
      `${IPAM_ROUTE.PREFIXES}/${encodeURIComponent(child?.node?.prefix?.value)}`
    ),
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
      <div className="flex items-center mb-2">
        {parent?.prefix?.value && (
          <>
            <Link
              to={constructPathForIpam(
                `${IPAM_ROUTE.PREFIXES}/${encodeURIComponent(parent.prefix.value)}`
              )}>
              {parent?.display_label}
            </Link>
            <Icon icon={"mdi:chevron-right"} />
          </>
        )}
        <span className="font-semibold">{prefix}</span>
      </div>

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

      <Pagination count={children?.count} />
    </div>
  );
});

export default IpamIPPrefixDetails;
