import { Button } from "@/components/buttons/button-primitive";
import { Pill } from "@/components/display/pill";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import ObjectForm from "@/components/form/object-form";
import ModalDeleteObject from "@/components/modals/modal-delete-object";
import { Table, tRowValue } from "@/components/table/table";
import { BadgeCopy } from "@/components/ui/badge-copy";
import { Pagination } from "@/components/ui/pagination";
import { GLOBAL_PERMISSION_OBJECT } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { GET_ROLE_MANAGEMENT_GLOBAL_PERMISSIONS } from "@/graphql/queries/role-management/getGlobalPermissions";
import useQuery from "@/hooks/useQuery";
import { useSchema } from "@/hooks/useSchema";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";
import { useAtomValue } from "jotai";
import { useState } from "react";
import ErrorScreen from "../errors/error-screen";
import UnauthorizedScreen from "../errors/unauthorized-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import { getPermission } from "../permission/utils";
import { globalDecisionOptions } from "./contants";

function GlobalPermissions() {
  const schemaKindName = useAtomValue(schemaKindNameState);
  const { schema } = useSchema(GLOBAL_PERMISSION_OBJECT);
  const { loading, data, error, refetch } = useQuery(GET_ROLE_MANAGEMENT_GLOBAL_PERMISSIONS);
  const [rowToDelete, setRowToDelete] = useState<Record<
    string,
    string | number | tRowValue
  > | null>(null);
  const [rowToUpdate, setRowToUpdate] = useState<Record<
    string,
    string | number | tRowValue
  > | null>(null);
  const [showDrawer, setShowDrawer] = useState(false);

  const permission = getPermission(data?.[GLOBAL_PERMISSION_OBJECT]?.permissions?.edges);

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

  const rows =
    data &&
    data[GLOBAL_PERMISSION_OBJECT]?.edges.map((edge) => {
      return {
        values: {
          id: { value: edge?.node?.id },
          display_label: { value: edge?.node?.display_label },
          action: { value: edge?.node?.action?.value },
          decision: {
            display: globalDecisionOptions.find(
              (decision) => decision.value === edge?.node?.decision?.value
            )?.label,
            value: edge?.node?.decision?.value,
          },
          roles: {
            display: <Pill>{edge?.node?.roles?.count}</Pill>,
            value: { edges: edge?.node?.roles?.edges },
          },
          identifier: { display: <BadgeCopy value={edge?.node?.identifier?.value} /> },
        },
      };
    });

  const globalRefetch = () => {
    graphqlClient.refetchQueries({ include: ["GET_ROLE_MANAGEMENT_COUNTS"] });
    refetch();
  };

  if (error) {
    if (error.networkError?.statusCode === 403) {
      const { message } = error.networkError?.result?.errors?.[0] ?? {};

      return <UnauthorizedScreen message={message} />;
    }

    return <ErrorScreen message="An error occured while retrieving the accounts." />;
  }

  if (loading) {
    return <LoadingScreen message="Retrieving global permissions..." />;
  }

  if (!permission?.view.isAllowed) {
    return <UnauthorizedScreen message={permission?.view?.message} />;
  }

  return (
    <>
      <div>
        <div className="flex items-center justify-between p-2">
          <div>{/* Search input + filter button */}</div>

          <div>
            <Button
              variant={"primary"}
              onClick={() => setShowDrawer(true)}
              disabled={!schema || !permission?.create.isAllowed}
            >
              Create {schema?.label}
            </Button>
          </div>
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

        <Pagination count={data && data[GLOBAL_PERMISSION_OBJECT]?.count} />
      </div>

      <ModalDeleteObject
        label={schemaKindName[GLOBAL_PERMISSION_OBJECT]}
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
            kind={GLOBAL_PERMISSION_OBJECT}
            currentObject={rowToUpdate}
            onCancel={() => setShowDrawer(false)}
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
  return <GlobalPermissions />;
}
