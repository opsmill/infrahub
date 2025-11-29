import { NetworkStatus } from "@apollo/client";
import { useAtomValue } from "jotai";
import { useState } from "react";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import useQuery from "@/shared/api/graphql/useQuery";
import { Button } from "@/shared/components/buttons/button-primitive";
import { ColorDisplay } from "@/shared/components/display/color-display";
import { InlineDisplay } from "@/shared/components/display/inline-display";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import ObjectForm from "@/shared/components/form/object-form";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import ModalDeleteObject from "@/shared/components/modals/modal-delete-object";
import { Table, type tRowValue } from "@/shared/components/table/table";
import { Badge } from "@/shared/components/ui/badge";
import { Pagination } from "@/shared/components/ui/pagination";
import { SearchInput } from "@/shared/components/ui/search-input";
import { ACCOUNT_GENERIC_OBJECT, ACCOUNT_OBJECT } from "@/shared/config/constants";
import { useDebounce } from "@/shared/hooks/useDebounce";
import usePagination from "@/shared/hooks/usePagination";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { GET_ROLE_MANAGEMENT_ACCOUNTS } from "@/entities/role-manager/api/getAccounts";
import { schemaKindNameState } from "@/entities/schema/stores/schemaKindName.atom";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { getPermission } from "../../permission/utils";

function Accounts() {
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
  } = useQuery(GET_ROLE_MANAGEMENT_ACCOUNTS, {
    variables: { search: searchDebounced, offset, limit },
    notifyOnNetworkStatusChange: true,
  });
  const data = latestData || previousData;
  const schemaKindName = useAtomValue(schemaKindNameState);
  const { schema } = useSchema(ACCOUNT_GENERIC_OBJECT);

  const [rowToDelete, setRowToDelete] = useState<Record<
    string,
    string | number | tRowValue
  > | null>(null);
  const [rowToUpdate, setRowToUpdate] = useState<Record<
    string,
    string | number | tRowValue
  > | null>(null);
  const [showDrawer, setShowDrawer] = useState(false);

  const permission = getPermission(data?.[ACCOUNT_GENERIC_OBJECT]?.permissions?.edges);

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
      name: "account_type",
      label: "Type",
    },
    {
      name: "status",
      label: "Status",
    },
    {
      name: "member_of_groups",
      label: "Groups",
    },
  ];

  const rows =
    data &&
    data[ACCOUNT_GENERIC_OBJECT]?.edges.map((edge) => ({
      values: {
        id: edge?.node?.id,
        display_label: edge?.node?.display_label,
        hfid: edge?.node?.hfid,
        name: { value: edge?.node?.name?.value },
        description: { value: edge?.node?.description?.value },
        account_type: { value: edge?.node?.account_type?.value },
        status: {
          value: edge?.node?.status?.value,
          display: (
            <ColorDisplay
              color={edge?.node?.status?.color}
              value={edge?.node?.status?.value}
              description={edge?.node?.status?.description}
            />
          ),
        },
        member_of_groups: {
          value: { edges: edge?.node?.member_of_groups?.edges },
          display: (
            <InlineDisplay
              items={edge?.node?.member_of_groups?.edges?.map((edge) =>
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
    if (error.networkError?.statusCode === 403) {
      const { message } = error.networkError?.result?.errors?.[0] ?? {};

      return <UnauthorizedScreen message={message} />;
    }

    return <ErrorScreen message="An error occurred while retrieving the accounts." />;
  }

  if (networkStatus === NetworkStatus.loading) {
    return <LoadingIndicator message="Retrieving accounts..." className="h-[calc(100vh-13rem)]" />;
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
            placeholder="Search accounts"
            className="border-none focus-visible:ring-0"
            containerClassName="grow"
          />

          <Button
            variant={"primary"}
            onClick={() => setShowDrawer(true)}
            disabled={!schema || !permission?.create.isAllowed}
            data-testid="create-object-button"
          >
            Create {schema?.label}
          </Button>
        </div>

        <Table
          columns={columns}
          rows={rows ?? []}
          className="border-0"
          onDelete={(row) => setRowToDelete(row.values)}
          onUpdate={(row) => {
            setRowToUpdate(row.values);
            setShowDrawer(true);
          }}
          permission={permission}
        />

        <Pagination count={data && data[ACCOUNT_GENERIC_OBJECT]?.count} />
      </div>

      <ModalDeleteObject
        label={schemaKindName[ACCOUNT_GENERIC_OBJECT]}
        rowToDelete={rowToDelete}
        open={!!rowToDelete}
        close={() => {
          setRowToDelete(null);
        }}
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
            kind={ACCOUNT_OBJECT}
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
  return <Accounts />;
}
