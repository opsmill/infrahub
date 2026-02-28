import { useAtomValue } from "jotai";
import { useState } from "react";

import { queryClient } from "@/shared/api/rest/client";
import { InlineDisplay } from "@/shared/components/display/inline-display";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import ObjectForm from "@/shared/components/form/object-form";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Table, type tRowValue } from "@/shared/components/table/table";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Pagination } from "@/shared/components/ui/pagination";
import { SearchInput } from "@/shared/components/ui/search-input";
import { ACCOUNT_GROUP_OBJECT } from "@/shared/config/constants";
import { useDebounce } from "@/shared/hooks/useDebounce";

import ModalDeleteObject from "@/entities/nodes/object/ui/modal-delete-object";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getPermission } from "@/entities/permission/utils";
import { useGetRoleManagerGroups } from "@/entities/role-manager/ui/queries/get-groups.query";
import { roleManagerQueryKeys } from "@/entities/role-manager/ui/queries/role-manager.query-keys";
import { schemaKindNameState } from "@/entities/schema/stores/schemaKindName.atom";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { GroupMembers } from "./group-member";

function Groups() {
  const [search, setSearch] = useState("");
  const searchDebounced = useDebounce(search, 300);

  const { isLoading, isFetching, data, error, refetch } = useGetRoleManagerGroups({
    search: searchDebounced,
  });

  const schemaKindName = useAtomValue(schemaKindNameState);
  const { schema } = useSchema(ACCOUNT_GROUP_OBJECT);
  const [rowToDelete, setRowToDelete] = useState<Record<
    string,
    string | number | tRowValue
  > | null>(null);
  const [rowToUpdate, setRowToUpdate] = useState<Record<
    string,
    string | number | tRowValue
  > | null>(null);
  const [showDrawer, setShowDrawer] = useState(false);

  const permission = getPermission(data?.[ACCOUNT_GROUP_OBJECT]?.permissions?.edges);

  const columns = [
    {
      name: "name",
      label: "Name",
    },
    {
      name: "description",
      label: "Description",
    },
    {
      name: "label",
      label: "Label",
    },
    {
      name: "group_type",
      label: "Type",
    },
    {
      name: "members",
      label: "Members",
    },
    {
      name: "roles",
      label: "Roles",
    },
  ];

  const rows =
    data &&
    data[ACCOUNT_GROUP_OBJECT]?.edges.map((edge) => ({
      id: edge?.node?.id,
      values: {
        id: edge?.node?.id,
        display_label: edge?.node?.display_label,
        hfid: edge?.node?.hfid,
        name: { value: edge?.node?.name?.value },
        description: { value: edge?.node?.description?.value },
        label: { value: edge?.node?.label?.value },
        group_type: { value: edge?.node?.group_type?.value },
        members: {
          value: { edges: edge?.node?.members?.edges },
          display: (
            <GroupMembers
              members={
                edge?.node?.members?.edges?.map((edge) =>
                  edge?.node ? getNodeLabel(edge.node) : ""
                ) ?? []
              }
            />
          ),
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
        __typename: edge?.node?.__typename,
      },
    }));

  if (error) {
    if ((error as any).networkError?.statusCode === 403) {
      const { message } = (error as any).networkError?.result?.errors?.[0] ?? {};

      return <UnauthorizedScreen message={message} />;
    }

    return <ErrorScreen message="An error occurred while retrieving the accounts." />;
  }

  if (isLoading) {
    return <LoadingIndicator message="Retrieving groups..." className="h-[calc(100vh-13rem)]" />;
  }

  if (!permission?.view.isAllowed) {
    return <UnauthorizedScreen message={permission?.view?.message} />;
  }

  const globalRefetch = () => {
    queryClient.invalidateQueries({ queryKey: roleManagerQueryKeys.all });
    refetch();
  };

  return (
    <>
      <div>
        <div className="flex items-center justify-between gap-2 border-gray-200 border-b p-2">
          <SearchInput
            loading={isFetching}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search groups"
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

        <Pagination count={data && data[ACCOUNT_GROUP_OBJECT]?.count} />
      </div>

      <ModalDeleteObject
        label={schemaKindName[ACCOUNT_GROUP_OBJECT]}
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
            kind={ACCOUNT_GROUP_OBJECT}
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
  return <Groups />;
}
