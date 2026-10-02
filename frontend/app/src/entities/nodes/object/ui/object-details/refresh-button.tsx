import { Button, type ButtonProps, Tooltip } from "@infrahub/ui";
import { matchQuery, type Query, useIsFetching } from "@tanstack/react-query";
import { CheckIcon, RefreshCwIcon } from "lucide-react";
import React from "react";

import { queryClient } from "@/shared/api/rest/client";
import { useFormatDate } from "@/shared/context/date-preferences-context";
import { classNames } from "@/shared/utils/common";

import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

type QueryKeyPrefix = readonly unknown[];

export interface RefreshButtonProps extends ButtonProps {
  queryKeys?: ReadonlyArray<QueryKeyPrefix>;
}

const DEFAULT_QUERY_KEYS = [objectQueryKeys.all];

const isWatched = (queryKeys: ReadonlyArray<QueryKeyPrefix>, query: Query) =>
  queryKeys.some((queryKey) => matchQuery({ queryKey }, query));

function getLastUpdateTime(queryKeys: ReadonlyArray<QueryKeyPrefix>) {
  const queries = queryClient
    .getQueryCache()
    .findAll({ type: "active", predicate: (query) => isWatched(queryKeys, query) });
  if (queries.length === 0) return null;
  return Math.max(...queries.map((q) => q.state.dataUpdatedAt));
}

export function RefreshButton({ queryKeys = DEFAULT_QUERY_KEYS, ...props }: RefreshButtonProps) {
  const [isRefreshSuccess, setIsRefreshSuccess] = React.useState(false);
  const [dataUpdatedAt, setDataUpdatedAt] = React.useState(() => getLastUpdateTime(queryKeys));
  const isFetching = useIsFetching({ predicate: (query) => isWatched(queryKeys, query) });
  const isRefetching = isFetching > 0;
  const { formatDate } = useFormatDate();

  React.useEffect(() => {
    if (isFetching > 0) return;
    const lastUpdateTime = getLastUpdateTime(queryKeys);
    if (lastUpdateTime !== null) setDataUpdatedAt(lastUpdateTime);
  }, [isFetching, queryKeys]);

  const handleRefresh = async () => {
    await Promise.all(queryKeys.map((queryKey) => queryClient.invalidateQueries({ queryKey })));
    setIsRefreshSuccess(true);
    setTimeout(() => setIsRefreshSuccess(false), 2000);
  };

  return (
    <Tooltip
      message={
        dataUpdatedAt ? (
          <>
            <div>Last data refresh</div>
            <div className="text-neutral-200">{formatDate(dataUpdatedAt, "datetime")}</div>
          </>
        ) : (
          "Refresh"
        )
      }
    >
      <Button
        variant="outline"
        size="sm"
        shape="square"
        isDisabledAndFocusable={isRefetching}
        onPress={handleRefresh}
        aria-label="Refresh data"
        {...props}
      >
        {isRefreshSuccess ? (
          <CheckIcon className="size-3.5 text-green-600" />
        ) : (
          <RefreshCwIcon className={classNames("size-3.5", isRefetching && "animate-spin")} />
        )}
      </Button>
    </Tooltip>
  );
}
