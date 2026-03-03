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
import { BadgeCopy } from "@/shared/components/ui/badge-copy";
import { Button } from "@/shared/components/ui/button";
import { Pagination } from "@/shared/components/ui/pagination";
import { SearchInput } from "@/shared/components/ui/search-input";
import { GLOBAL_PERMISSION_OBJECT } from "@/shared/config/constants";
import { useDebounce } from "@/shared/hooks/useDebounce";

import ModalDeleteObject from "@/entities/nodes/object/ui/modal-delete-object";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { useGetGlobalPermissions } from "@/entities/role-manager/ui/queries/get-global-permissions.query";
import { roleManagerQueryKeys } from "@/entities/role-manager/ui/queries/role-manager.query-keys";
import { schemaKindNameState } from "@/entities/schema/stores/schemaKindName.atom";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { globalDecisionOptions } from "../constants";

function GlobalPermissions() {
  const schemaKindName = useAtomValue(schemaKindNameState);
  const { schema } = useSchema(GLOBAL_PERMISSION_OBJECT);
  const [search, setSearch] = useState("");
  const searchDebounced = useDebounce(search, 300);

  const { isLoading, isFetching, data, error, refetch } = useGetGlobalPermissions({
    search: searchDebounced,
  });

  const [rowToDelete, setRowToDelete] = useState<Record<
    string,
    string | number | tRowValue
  > | null>(null);
  const [rowToUpdate, setRowToUpdate] = useState<Record<
    string,
    string | number | tRowValue
  > | null>(null);
  const [showDrawer, setShowDrawer] = useState(false);

  const permission = data?.permission;

  const columns = [
    {
      name: "identifier",
      label: "Identifier",
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

  const rows = data?.globalPermissions.map((item) => {
    return {
      values: {
        id: item.id,
        display_label: item.display_label,
        hfid: item.hfid,
        action: { value: item.action },
        decision: {
          display: globalDecisionOptions.find((decision) => decision.value === item.decision)
            ?.label,
          value: item.decision,
        },
        roles: {
          display: (
            <InlineDisplay
              items={item.roles.map((role) => getNodeLabel(role))}
              render={(item) => <Badge>{item}</Badge>}
            />
          ),
          value: { edges: item.roles.map((role) => ({ node: role })) },
        },
        identifier: {
          value: item.identifier,
          display: <BadgeCopy value={item.identifier} />,
        },
        __typename: item.__typename,
      },
    };
  });

  const globalRefetch = () => {
    queryClient.invalidateQueries({ queryKey: roleManagerQueryKeys.all });
    refetch();
  };

  if (error) {
    if ((error as any).networkError?.statusCode === 403) {
      const { message } = (error as any).networkError?.result?.errors?.[0] ?? {};

      return <UnauthorizedScreen message={message} />;
    }

    return <ErrorScreen message="An error occurred while retrieving the accounts." />;
  }

  if (isLoading) {
    return (
      <LoadingIndicator
        message="Retrieving global permissions..."
        className="h-[calc(100vh-13rem)]"
      />
    );
  }

  if (!permission?.view.isAllowed) {
    return <UnauthorizedScreen message={permission?.view?.message} />;
  }

  return (
    <>
      <div>
        <div className="flex items-center justify-between gap-2 border-gray-200 border-b p-2">
          <SearchInput
            loading={isFetching}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search global permissions"
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
          onDelete={(data) => setRowToDelete(data.values)}
          onUpdate={(row) => {
            setRowToUpdate(row.values);
            setShowDrawer(true);
          }}
          className="border-0"
          permission={permission}
        />

        <Pagination count={data?.count} />
      </div>

      <ModalDeleteObject
        label={schemaKindName[GLOBAL_PERMISSION_OBJECT]}
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
              currentObjectLabel={rowToUpdate?.identifier?.value ?? "New"}
              title={`${rowToUpdate ? "Update" : "Create"} ${schema.label}`}
              subtitle={schema.description}
            />
          }
          open={showDrawer}
          setOpen={(value) => setShowDrawer(value)}
          onClose={() => setRowToUpdate(null)}
        >
          <ObjectForm
            kind={GLOBAL_PERMISSION_OBJECT}
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
  return <GlobalPermissions />;
}
