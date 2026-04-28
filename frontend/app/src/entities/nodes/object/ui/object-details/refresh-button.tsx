import { Button, type ButtonProps } from "@infrahub/ui";
import { useIsFetching } from "@tanstack/react-query";
import { CheckIcon, RefreshCwIcon } from "lucide-react";
import React from "react";

import { queryClient } from "@/shared/api/rest/client";
import { Tooltip } from "@/shared/components/aria/tooltip";
import { classNames } from "@/shared/utils/common";
import { formatFullDate } from "@/shared/utils/date";

import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

export interface RefreshButtonProps extends ButtonProps {
  queryKey?: readonly unknown[];
}

function getLastUpdateTime() {
  const queries = queryClient.getQueryCache().findAll({ type: "active" });
  if (queries.length === 0) return null;
  return Math.max(...queries.map((q) => q.state.dataUpdatedAt));
}

export function RefreshButton({ queryKey, ...props }: RefreshButtonProps) {
  const watchedQueryKey = queryKey ?? objectQueryKeys.all;
  const [isRefreshSuccess, setIsRefreshSuccess] = React.useState(false);
  const [dataUpdatedAt, setDataUpdatedAt] = React.useState(getLastUpdateTime());
  const isFetching = useIsFetching({ queryKey: watchedQueryKey });
  const isRefetching = isFetching > 0;

  React.useEffect(() => {
    if (isFetching > 0) return;
    const lastUpdateTime = getLastUpdateTime();
    if (lastUpdateTime !== null) setDataUpdatedAt(lastUpdateTime);
  }, [isFetching]);

  const handleRefresh = async () => {
    await queryClient.invalidateQueries({ queryKey: watchedQueryKey });
    setIsRefreshSuccess(true);
    setTimeout(() => setIsRefreshSuccess(false), 2000);
  };

  return (
    <Tooltip
      message={
        dataUpdatedAt ? (
          <>
            <div>Last data refresh</div>
            <div className="text-neutral-200">{formatFullDate(dataUpdatedAt)}</div>
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
