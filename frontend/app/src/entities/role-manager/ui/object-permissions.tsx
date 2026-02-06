import { NetworkStatus } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { type ReactNode, useState } from "react";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import useQuery from "@/shared/api/graphql/useQuery";
import { InlineDisplay } from "@/shared/components/display/inline-display";
import { Pill } from "@/shared/components/display/pill";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import ObjectForm from "@/shared/components/form/object-form";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Table, type tRowValue } from "@/shared/components/table/table";
import { Badge } from "@/shared/components/ui/badge";
import { BadgeCopy } from "@/shared/components/ui/badge-copy";
import { Button } from "@/shared/components/ui/button";
import { Pagination } from "@/shared/components/ui/pagination";
import { SearchInput } from "@/shared/components/ui/search-input";
import { OBJECT_PERMISSION_OBJECT } from "@/shared/config/constants";
import { useDebounce } from "@/shared/hooks/useDebounce";
import usePagination from "@/shared/hooks/usePagination";

import ModalDeleteObject from "@/entities/nodes/object/ui/modal-delete-object";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { GET_ROLE_MANAGEMENT_OBJECT_PERMISSIONS } from "@/entities/role-manager/api/getObjectPermissions";
import { schemaKindNameState } from "@/entities/schema/stores/schemaKindName.atom";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { getPermission } from "../../permission/utils";
import { objectDecisionOptions } from "../constants";

const icons: Record<string, ReactNode> = {
  allow: (
    <Pill className="flex h-6 w-6 items-center justify-center bg-green-500/40">
      <Icon icon={"mdi:lock-open-check-outline"} className="text-green-900" />
    </Pill>
  ),
  deny: (
    <Pill className="flex h-6 w-6 items-center justify-center bg-red-500/40">
      <Icon icon={"mdi:lock-remove-outline"} className="text-red-900" />
    </Pill>
  ),
};

function Permissions() {
  const [search, setSearch] = useState("");
  const searchDebounced = useDebounce(search, 300);
  const [{ offset, limit }] = usePagination();

  const {
    loading,
    networkStatus,
    data: latestData,
    previousData,
    error,
    refetch,
  } = useQuery(GET_ROLE_MANAGEMENT_OBJECT_PERMISSIONS, {
    variables: { search: searchDebounced, offset, limit },
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
      name: "display_label",
      label: "Label",
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
          hfid: edge?.node?.hfid,
          display: {
            value: edge?.node ? getNodeLabel(edge.node) : undefined,
            display: (
              <div className="flex items-center gap-2">
                {icon} {edge?.node ? getNodeLabel(edge.node) : ""}
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
              <InlineDisplay
                items={edge?.node?.roles?.edges?.map((edge) =>
                  edge?.node ? getNodeLabel(edge.node) : ""
                )}
                render={(item) => <Badge>{item}</Badge>}
              />
            ),
          },
          display_label: {
            value: edge?.node?.display_label,
            display: <BadgeCopy value={edge?.node?.display_label} />,
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

    return <ErrorScreen message="An error occurred while retrieving the accounts." />;
  }

  if (networkStatus === NetworkStatus.loading) {
    return (
      <LoadingIndicator
        message="Retrieving object permissions..."
        className="h-[calc(100vh-13rem)]"
      />
    );
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
        <div className="flex items-center justify-between gap-2 border-gray-200 border-b p-2">
          <SearchInput
            loading={loading}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search object permissions"
            className="border-none focus-visible:ring-0"
            containerClassName="grow"
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
        isOpen={!!rowToDelete}
        onOpenChange={(open) => !open && setRowToDelete(null)}
        onDelete={() => globalRefetch()}
      />

      {schema && (
        <SlideOver
          title={
            <SlideOverTitle
              schema={schema}
              currentObjectLabel={rowToUpdate?.name?.value ?? "New"}
              title={`${rowToUpdate ? "Update" : "Create"} ${schema.label}`}
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
              setRowToUpdate(null);
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
