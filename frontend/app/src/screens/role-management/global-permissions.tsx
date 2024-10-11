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
import { useSchema } from "@/hooks/useSchema";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";
import { useQuery } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useState } from "react";
import ErrorScreen from "../errors/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";

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

  const columns = [
    {
      name: "name",
      label: "Name",
    },
    {
      name: "action",
      label: "Action",
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
    data[GLOBAL_PERMISSION_OBJECT]?.edges.map((edge) => {
      return {
        values: {
          id: { value: edge?.node?.id },
          display_label: { value: edge?.node?.display_label },
          name: {
            display: (
              <div className="flex items-center gap-2">
                <Pill className="flex items-center justify-center w-6 h-6 bg-custom-blue-500/20">
                  <Icon icon={"mdi:lock-outline"} className="text-custom-blue-900" />
                </Pill>

                {edge?.node?.display_label}
              </div>
            ),
          },
          description: { value: edge?.node?.description?.value },
          roles: { display: <Pill>{edge?.node?.roles?.count}</Pill> },
          identifier: { display: <BadgeCopy value={edge?.node?.identifier?.value} /> },
        },
      };
    });

  const globalRefetch = () => {
    graphqlClient.refetchQueries({ include: ["GET_ROLE_MANAGEMENT_COUNTS"] });
    refetch();
  };

  if (error) return <ErrorScreen message="An error occured while retrieving the accounts." />;

  if (loading) return <LoadingScreen message="Retrieving accounts..." />;

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

        <Table columns={columns} rows={rows ?? []} className="border-0" />

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
