import React from "react";

import { queryClient } from "@/shared/api/rest/client";
import { Col } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { ObjectCreateFormTrigger } from "@/shared/components/form/object-create-form-trigger";
import Content from "@/shared/components/layout/content";
import { Spinner } from "@/shared/components/ui/spinner";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import useFilters from "@/shared/hooks/useFilters";

import { IP_NAMESPACE_GENERIC } from "@/entities/ipam/constants";
import { useGetIpNamespaceList } from "@/entities/ipam/ip-namespaces/domain/get-ip-namespace-list.query";
import { IpNamespaceCard } from "@/entities/ipam/ip-namespaces/ui/ip-namespace-card";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import type { Permission } from "@/entities/permission/types";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import type { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

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
    <Content.Card className="flex h-full flex-col gap-0 overflow-hidden">
      <div className="flex h-14 shrink-0 items-center border-gray-200 border-b px-2">
        <FilterSearchInput schema={namespaceSchema} />

        <ObjectCreateFormTrigger
          schema={namespaceSchema}
          onSuccess={() => {
            queryClient.invalidateQueries({
              queryKey: objectQueryKeys.all,
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
            <div className="flex grow justify-center">
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
  const { schema } = useSchema(IP_NAMESPACE_GENERIC);

  if (!schema) {
    return <ErrorScreen message={`Schema ${IP_NAMESPACE_GENERIC} not found.`} />;
  }

  return (
    <RequireObjectPermissions objectKind={schema.kind!} loadingClassName="h-full">
      {({ permission }) => {
        return <IpamNamespaceListPage namespaceSchema={schema} permission={permission} />;
      }}
    </RequireObjectPermissions>
  );
};
