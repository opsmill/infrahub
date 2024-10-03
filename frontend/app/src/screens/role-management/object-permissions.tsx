import { useQuery } from "@apollo/client";
import { Table } from "@/components/table/table";
import LoadingScreen from "../loading-screen/loading-screen";
import { OBJECT_PERMISSION_OBJECT } from "@/config/constants";
import ErrorScreen from "../errors/error-screen";
import { Pagination } from "@/components/ui/pagination";
import { Pill } from "@/components/display/pill";
import { ReactNode, useState } from "react";
import { Icon } from "@iconify-icon/react";
import { BadgeCopy } from "@/components/ui/badge-copy";
import ModalDeleteObject from "@/components/modals/modal-delete-object";
import { useAtomValue } from "jotai";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";
import { GET_ROLE_MANAGEMENT_OBJECT_PERMISSIONS } from "@/graphql/queries/role-management/getObjectPermissions";
import { Button } from "@/components/buttons/button-primitive";
import { useSchema } from "@/hooks/useSchema";
import graphqlClient from "@/graphql/graphqlClientApollo";
import ObjectForm from "@/components/form/object-form";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";

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
  const { loading, data, error, refetch } = useQuery(GET_ROLE_MANAGEMENT_OBJECT_PERMISSIONS);
  const schemaKindName = useAtomValue(schemaKindNameState);
  const { schema } = useSchema(OBJECT_PERMISSION_OBJECT);
  const [rowToDelete, setRowToDelete] = useState(null);
  const [showCreateDrawer, setShowCreateDrawer] = useState(false);

  const columns = [
    {
      name: "display_label",
      label: "Name",
    },
    {
      name: "branch",
      label: "Branch",
    },
    {
      name: "namespace",
      label: "Namespace",
    },
    {
      name: "name",
      label: "Node",
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
    {
      name: "identifier",
      label: "Identifier",
    },
  ];

  const rows =
    data &&
    data[OBJECT_PERMISSION_OBJECT]?.edges.map((edge) => {
      const iconKey = edge?.node?.decision?.value;
      const icon = icons[iconKey];

      return {
        id: edge?.node?.id,
        values: {
          display_label: (
            <div className="flex items-center gap-2">
              {icon} {edge?.node?.display_label}
            </div>
          ),
          branch: edge?.node?.branch?.value,
          namespace: edge?.node?.namespace?.value,
          name: edge?.node?.name?.value,
          action: edge?.node?.action?.value,
          decision: edge?.node?.decision?.value,
          roles: <Pill>{edge?.node?.roles?.count}</Pill>,
          identifier: <BadgeCopy value={edge?.node?.identifier?.value} />,
        },
      };
    });

  if (error) return <ErrorScreen message="An error occured while retrieving the accounts." />;

  if (loading) return <LoadingScreen message="Retrieving accounts..." />;

  const globalRefetch = () => {
    graphqlClient.refetchQueries({ include: ["GET_ROLE_MANAGEMENT_COUNTS"] });
    refetch();
  };

  return (
    <>
      <div>
        <div className="flex items-center justify-between p-2">
          <div>SEARCH + FILTERS</div>

          <div>
            <Button
              variant={"primary"}
              onClick={() => setShowCreateDrawer(true)}
              disabled={!schema}>
              Create {schema?.label}
            </Button>
          </div>
        </div>

        <Table
          columns={columns}
          rows={rows ?? []}
          className="border-0"
          onDelete={(data) => setRowToDelete(data.values)}
        />

        <Pagination count={data && data[OBJECT_PERMISSION_OBJECT]?.count} />
      </div>

      <ModalDeleteObject
        label={schemaKindName[OBJECT_PERMISSION_OBJECT]}
        rowToDelete={rowToDelete}
        open={!!rowToDelete}
        close={() => setRowToDelete(null)}
        onDelete={refetch}
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
          open={showCreateDrawer}
          setOpen={(value) => setShowCreateDrawer(value)}>
          <ObjectForm
            kind={OBJECT_PERMISSION_OBJECT}
            onSuccess={() => {
              setShowCreateDrawer(false);
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
