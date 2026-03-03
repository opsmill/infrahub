import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { type ReactNode, useState } from "react";

import { queryClient } from "@/shared/api/rest/client";
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

import ModalDeleteObject from "@/entities/nodes/object/ui/modal-delete-object";

import { useGetObjectPermissions } from "@/entities/role-manager/ui/queries/get-object-permissions.query";
import { roleManagerQueryKeys } from "@/entities/role-manager/ui/queries/role-manager.query-keys";
import { schemaKindNameState } from "@/entities/schema/stores/schemaKindName.atom";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

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

  const { isLoading, isFetching, data, error, refetch } = useGetObjectPermissions({
    search: searchDebounced,
  });

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

  const permission = data?.permission;

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

  const rows = data?.objectPermissions.map((item) => {
    const icon = icons[item.decision as string];
    const label = item.display_label || item.id;

    return {
      values: {
        id: item.id,
        display_label: item.display_label,
        hfid: item.hfid,
        display: {
          value: label,
          display: (
            <div className="flex items-center gap-2">
              {icon} {label}
            </div>
          ),
        },
        namespace: {
          value: item.namespace,
        },
        name: {
          value: item.name,
        },
        action: {
          value: item.action,
        },
        decision: {
          display: objectDecisionOptions.find((decision) => decision.value === item.decision)
            ?.label,
          value: item.decision,
        },
        roles: {
          value: { edges: item.roles.map((role) => ({ node: role })) },
          display: (
            <InlineDisplay
              items={item.roles.map((role) => role.display_label || role.id)}
              render={(item) => <Badge>{item}</Badge>}
            />
          ),
        },
        identifier: {
          value: item.identifier,
          display: <BadgeCopy value={item.identifier} />,
        },
      },
    };
  });

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
        message="Retrieving object permissions..."
        className="h-[calc(100vh-13rem)]"
      />
    );
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

        <Pagination count={data?.count} />
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
