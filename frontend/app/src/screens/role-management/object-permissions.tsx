import { Button } from "@/components/buttons/button-primitive";
import { Pill } from "@/components/display/pill";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import ObjectForm from "@/components/form/object-form";
import ModalDeleteObject from "@/components/modals/modal-delete-object";
import { Table, tRowValue } from "@/components/table/table";
import { BadgeCopy } from "@/components/ui/badge-copy";
import { Pagination } from "@/components/ui/pagination";
import { OBJECT_PERMISSION_OBJECT } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { GET_ROLE_MANAGEMENT_OBJECT_PERMISSIONS } from "@/graphql/queries/role-management/getObjectPermissions";
import useQuery from "@/hooks/useQuery";
import { useSchema } from "@/hooks/useSchema";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { ReactNode, useState } from "react";
import ErrorScreen from "../errors/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";

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
  const [rowToDelete, setRowToDelete] = useState<Record<
    string,
    string | number | tRowValue
  > | null>(null);
  const [rowToUpdate, setRowToUpdate] = useState<Record<
    string,
    string | number | tRowValue
  > | null>(null);
  const [showDrawer, setShowDrawer] = useState(false);

  const columns = [
    {
      name: "display",
      label: "Name",
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
            value: edge?.node?.decision?.value,
          },
          roles: {
            value: { edges: edge?.node?.roles?.edges },
            display: <Pill>{edge?.node?.roles?.count}</Pill>,
          },
          identifier: {
            value: edge?.node?.identifier?.value,
            display: <BadgeCopy value={edge?.node?.identifier?.value} />,
          },
          __typename: edge?.node?.__typename,
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
          <div>{/* Search input + filter button */}</div>

          <div>
            <Button variant={"primary"} onClick={() => setShowDrawer(true)} disabled={!schema}>
              Create {schema?.label}
            </Button>
          </div>
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
        >
          <ObjectForm
            kind={OBJECT_PERMISSION_OBJECT}
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
  return <Permissions />;
}
