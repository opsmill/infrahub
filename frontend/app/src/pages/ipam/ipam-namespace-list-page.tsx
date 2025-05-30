import { NAMESPACE_GENERIC } from "@/entities/ipam/constants";
import { useGetIpNamespaceList } from "@/entities/ipam/ip-namespaces/domain/get-ip-namespace-list.query";
import { IpNamespaceCard } from "@/entities/ipam/ip-namespaces/ui/ip-namespace-card";
import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { Permission } from "@/entities/permission/types";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { queryClient } from "@/shared/api/rest/client";
import { Col } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { ObjectCreateFormTrigger } from "@/shared/components/form/object-create-form-trigger";
import Content from "@/shared/components/layout/content";
import { Spinner } from "@/shared/components/ui/spinner";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import useFilters from "@/shared/hooks/useFilters";
import React from "react";

interface IpNamespaceListPageProps {
  namespaceSchema: ModelSchema;
  permission: Permission;
}

function IpamNamespaceListPage({ namespaceSchema, permission }: IpNamespaceListPageProps) {
  const [filters] = useFilters();
  const { isPending, data, fetchNextPage, isFetchingNextPage, hasNextPage } = useGetIpNamespaceList(
    {
      filters,
    }
  );

  const flatData = React.useMemo(() => data?.pages?.flat() ?? [], [data]);

  const isLoading = isPending || isFetchingNextPage;

  return (
    <Content.Card className="flex flex-col overflow-hidden h-full gap-0">
      <div className="flex items-center h-14 shrink-0 border-b px-2 border-gray-200">
        <FilterSearchInput schema={namespaceSchema} />

        <ObjectCreateFormTrigger
          schema={namespaceSchema}
          onSuccess={() => {
            queryClient.invalidateQueries({
              predicate: (query) => query.queryKey.includes("objects"),
            });
          }}
          permission={permission}
          className="ml-auto"
        />
      </div>

      <InfiniteScroll hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
        <Col className="p-2">
          {flatData.map((item) => {
            return <IpNamespaceCard key={item.id} ipNamespace={item} />;
          })}

          {isLoading && (
            <div className="flex justify-center grow">
              <Spinner />
            </div>
          )}

          {!isLoading && flatData.length === 0 && <ObjectTableEmpty schema={namespaceSchema} />}
        </Col>
      </InfiniteScroll>
    </Content.Card>
  );
}

export const Component = () => {
  const { schema } = useSchema(NAMESPACE_GENERIC);

  if (!schema) {
    return <ErrorScreen message={`Schema ${NAMESPACE_GENERIC} not found.`} />;
  }

  return (
    <RequireObjectPermissions objectKind={NAMESPACE_GENERIC}>
      {({ permission }) => {
        return <IpamNamespaceListPage namespaceSchema={schema} permission={permission} />;
      }}
    </RequireObjectPermissions>
  );
};
