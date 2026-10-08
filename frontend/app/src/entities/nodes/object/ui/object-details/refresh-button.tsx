import { Button, type ButtonProps, Tooltip } from "@infrahub/ui";
import { matchQuery, type Query, type QueryKey } from "@tanstack/react-query";
import { CheckIcon, RefreshCwIcon } from "lucide-react";
import React from "react";

import { queryClient } from "@/shared/api/rest/client";
import { useFormatDate } from "@/shared/context/date-preferences-context";
import { classNames } from "@/shared/utils/common";

import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

export interface RefreshButtonProps extends ButtonProps {
  queryKeys?: ReadonlyArray<QueryKey>;
}

const DEFAULT_QUERY_KEYS = [objectQueryKeys.all];

const isWatched = (queryKeys: ReadonlyArray<QueryKey>, query: Query) =>
  queryKeys.some((queryKey) => matchQuery({ queryKey }, query));

function getLastUpdateTime(queryKeys: ReadonlyArray<QueryKey>) {
  const queries = queryClient
    .getQueryCache()
    .findAll({ type: "active", predicate: (query) => isWatched(queryKeys, query) });
  if (queries.length === 0) return null;
  return Math.max(...queries.map((q) => q.state.dataUpdatedAt));
}

const subscribeToQueryCache = (onChange: () => void) =>
  queryClient.getQueryCache().subscribe(onChange);

export function RefreshButton({ queryKeys = DEFAULT_QUERY_KEYS, ...props }: RefreshButtonProps) {
  // Busy only for the refresh the user asked for, not for background polls under the same keys.
  const [isRefetching, setIsRefetching] = React.useState(false);
  const [isRefreshSuccess, setIsRefreshSuccess] = React.useState(false);
  const dataUpdatedAt = React.useSyncExternalStore(subscribeToQueryCache, () =>
    getLastUpdateTime(queryKeys)
  );
  const { formatDate } = useFormatDate();

  const handleRefresh = async () => {
    setIsRefetching(true);
    try {
      await Promise.all(queryKeys.map((queryKey) => queryClient.invalidateQueries({ queryKey })));
    } finally {
      setIsRefetching(false);
    }
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
