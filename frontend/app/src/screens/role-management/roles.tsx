import ModalDeleteObject from "@/components/modals/modal-delete-object";
import { Table, tRowValue } from "@/components/table/table";
import { Pagination } from "@/components/ui/pagination";
import { ACCOUNT_ROLE_OBJECT } from "@/config/constants";
import { GET_ROLE_MANAGEMENT_ROLES } from "@/graphql/queries/role-management/getRoles";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";
import { useAtomValue } from "jotai";
import { useState } from "react";
import ErrorScreen from "../errors/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";

import { Button } from "@/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import ObjectForm from "@/components/form/object-form";
import { SearchInput } from "@/components/ui/search-input";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { useDebounce } from "@/hooks/useDebounce";
import useQuery from "@/hooks/useQuery";
import { useSchema } from "@/hooks/useSchema";
import { NetworkStatus } from "@apollo/client";
import UnauthorizedScreen from "../errors/unauthorized-screen";
import { getPermission } from "../permission/utils";
import { RelationshipDisplay } from "./relationship-display";

function Roles() {
  const [search, setSearch] = useState("");
  const searchDebounced = useDebounce(search, 300);
  const {
    loading,
    networkStatus,
    data: latestData,
    previousData,
    error,
    refetch,
  } = useQuery(GET_ROLE_MANAGEMENT_ROLES, {
    variables: { search: searchDebounced },
    notifyOnNetworkStatusChange: true,
  });
  const data = latestData || previousData;
  const schemaKindName = useAtomValue(schemaKindNameState);
  const { schema } = useSchema(ACCOUNT_ROLE_OBJECT);
  const [rowToDelete, setRowToDelete] = useState<Record<
    string,
    string | number | tRowValue
  > | null>(null);
  const [rowToUpdate, setRowToUpdate] = useState<Record<
    string,
    string | number | tRowValue
  > | null>(null);
  const [showDrawer, setShowDrawer] = useState(false);

  const permission = getPermission(data?.[ACCOUNT_ROLE_OBJECT]?.permissions?.edges);

  const columns = [
    {
      name: "name",
      label: "Name",
    },
    {
      name: "groups",
      label: "Groups",
    },
    {
      name: "permissions",
      label: "Permissions",
    },
  ];

  const rows =
    data &&
    data[ACCOUNT_ROLE_OBJECT]?.edges.map((edge) => ({
      values: {
        id: edge?.node?.id,
        name: { value: edge?.node?.name.value },
        description: { value: edge?.node?.description?.value },
        groups: {
          value: { edges: edge?.node?.groups?.edges },
          display: (
            <RelationshipDisplay
              items={edge?.node?.groups?.edges?.map((edge) => edge?.node?.display_label)}
            />
          ),
        },
        permissions: {
          value: { edges: edge?.node?.permissions?.edges },
          display: (
            <RelationshipDisplay
              items={edge?.node?.permissions?.edges?.map((edge) => edge?.node?.identifier?.value)}
            />
          ),
        },
        __typename: edge?.node?.__typename,
      },
    }));

  if (error) {
    if (error.networkError?.statusCode === 403) {
      const { message } = error.networkError?.result?.errors?.[0] ?? {};

      return <UnauthorizedScreen message={message} />;
    }

    return <ErrorScreen message="An error occured while retrieving the accounts." />;
  }

  if (networkStatus === NetworkStatus.loading) {
    return <LoadingScreen message="Retrieving roles..." />;
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
            placeholder="Search roles"
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

        <Pagination count={data && data[ACCOUNT_ROLE_OBJECT]?.count} />
      </div>

      <ModalDeleteObject
        label={schemaKindName[ACCOUNT_ROLE_OBJECT]}
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
            kind={ACCOUNT_ROLE_OBJECT}
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
  return <Roles />;
}
