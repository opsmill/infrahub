import { Button } from "@/components/buttons/button-primitive";
import { Pill } from "@/components/display/pill";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import ObjectForm from "@/components/form/object-form";
import ModalDeleteObject from "@/components/modals/modal-delete-object";
import { Table, tRowValue } from "@/components/table/table";
import { BadgeCopy } from "@/components/ui/badge-copy";
import { Pagination } from "@/components/ui/pagination";
import { SearchInput } from "@/components/ui/search-input";
import { OBJECT_PERMISSION_OBJECT } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { GET_ROLE_MANAGEMENT_OBJECT_PERMISSIONS } from "@/graphql/queries/role-management/getObjectPermissions";
import { useDebounce } from "@/hooks/useDebounce";
import useQuery from "@/hooks/useQuery";
import { useSchema } from "@/hooks/useSchema";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";
import { NetworkStatus } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { ReactNode, useState } from "react";
import ErrorScreen from "../errors/error-screen";
import UnauthorizedScreen from "../errors/unauthorized-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import { getPermission } from "../permission/utils";
import { objectDecisionOptions } from "./constants";
import { RelationshipDisplay } from "./relationship-display";

const icons: Record<string, ReactNode> = {
  allow: (
    <Pill className="flex items-center justify-center w-6 h-6 bg-green-500/40">
      <Icon icon={"mdi:lock-open-check-outline"} className="text-green-900" />
    </Pill>
  ),
  deny: (
    <Pill className="flex items-center justify-center w-6 h-6 bg-red-500/40">
      <Icon icon={"mdi:lock-remove-outline"} className="text-red-900" />
    </Pill>
  ),
};

function Permissions() {
  const [search, setSearch] = useState("");
  const searchDebounced = useDebounce(search, 300);
  const {
    loading,
    networkStatus,
    data: latestData,
    previousData,
    error,
    refetch,
  } = useQuery(GET_ROLE_MANAGEMENT_OBJECT_PERMISSIONS, {
    variables: { search: searchDebounced },
    notifyOnNetworkStatusChange: true,
  });
  const data = latestData || previousData;
  const schemaKindName = useAtomValue(schemaKindNameState);
  const { schema } = useSchema(OBJECT_PERMISSION_OBJECT);
  const [rowToDelete, setRowToDelete] = useState<Record<
    string,
    string | number | tRowValue
  > | null>(null);
  const [rowToUpdate, setRowToUpdate] = useState<Record<
    string,
    string | number | tRowValue
  > | null>(null);
  const [showDrawer, setShowDrawer] = useState(false);

  const permission = getPermission(data?.[OBJECT_PERMISSION_OBJECT]?.permissions?.edges);

  const columns = [
    {
      name: "identifier",
      label: "Identifier",
    },
    {
      name: "namespace",
      label: "Namespace",
    },
    {
      name: "name",
      label: "Name",
    },
    {
      name: "action",
      label: "Action",
    },
    {
      name: "decision",
      label: "Decision",
    },
    {
      name: "roles",
      label: "Roles",
    },
  ];

  const rows =
    data &&
    data[OBJECT_PERMISSION_OBJECT]?.edges.map((edge) => {
      const iconKey = edge?.node?.decision?.value;
      const icon = icons[iconKey];

      return {
        values: {
          id: edge?.node?.id,
          display_label: edge?.node?.display_label,
          display: {
            value: edge?.node?.display_label,
            display: (
              <div className="flex items-center gap-2">
                {icon} {edge?.node?.display_label}
              </div>
            ),
          },
          namespace: {
            value: edge?.node?.namespace?.value,
          },
          name: {
            value: edge?.node?.name?.value,
          },
          action: {
            value: edge?.node?.action?.value,
          },
          decision: {
            display: objectDecisionOptions.find(
              (decision) => decision.value === edge?.node?.decision?.value
            )?.label,
            value: edge?.node?.decision?.value,
          },
          roles: {
            value: { edges: edge?.node?.roles?.edges },
            display: (
              <RelationshipDisplay
                items={edge?.node?.roles?.edges?.map((edge) => edge?.node?.display_label)}
              />
            ),
          },
          identifier: {
            value: edge?.node?.identifier?.value,
            display: <BadgeCopy value={edge?.node?.identifier?.value} />,
          },
          __typename: edge?.node?.__typename,
        },
      };
    });

  if (error) {
    if (error.networkError?.statusCode === 403) {
      const { message } = error.networkError?.result?.errors?.[0] ?? {};

      return <UnauthorizedScreen message={message} />;
    }

    return <ErrorScreen message="An error occured while retrieving the accounts." />;
  }

  if (networkStatus === NetworkStatus.loading) {
    return <LoadingScreen message="Retrieving object permissions..." />;
  }

  if (!permission?.view.isAllowed) {
    return <UnauthorizedScreen message={permission?.view?.message} />;
  }

  const globalRefetch = () => {
    graphqlClient.refetchQueries({ include: ["GET_ROLE_MANAGEMENT_COUNTS"] });
    refetch();
  };

  return (
    <>
      <div>
        <div className="flex items-center justify-between gap-2 p-2 border-b">
          <SearchInput
            loading={loading}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search object permissions"
            className="border-none focus-visible:ring-0"
            containerClassName="flex-grow"
          />

          <Button
            variant={"primary"}
            onClick={() => setShowDrawer(true)}
            disabled={!schema || !permission?.create.isAllowed}
          >
            Create {schema?.label}
          </Button>
        </div>

        <Table
          columns={columns}
          rows={rows ?? []}
          className="border-0"
          onDelete={(data) => setRowToDelete(data.values)}
          onUpdate={(row) => {
            setRowToUpdate(row.values);
            setShowDrawer(true);
          }}
          permission={permission}
        />

        <Pagination count={data && data[OBJECT_PERMISSION_OBJECT]?.count} />
      </div>

      <ModalDeleteObject
        label={schemaKindName[OBJECT_PERMISSION_OBJECT]}
        rowToDelete={rowToDelete}
        open={!!rowToDelete}
        close={() => setRowToDelete(null)}
        onDelete={() => globalRefetch()}
      />

      {schema && (
        <SlideOver
          title={
            <SlideOverTitle
              schema={schema}
              currentObjectLabel="New"
              title={`Create ${schema.label}`}
              subtitle={schema.description}
            />
          }
          open={showDrawer}
          setOpen={(value) => setShowDrawer(value)}
          onClose={() => setRowToUpdate(null)}
        >
          <ObjectForm
            kind={OBJECT_PERMISSION_OBJECT}
            currentObject={rowToUpdate}
            onCancel={() => {
              setRowToUpdate(null);
              setShowDrawer(false);
            }}
            onSuccess={() => {
              setShowDrawer(false);
              globalRefetch();
            }}
          />
        </SlideOver>
      )}
    </>
  );
}

export function Component() {
  return <Permissions />;
}
