import { Button } from "@infrahub/ui";

import { Row } from "@/shared/components/container";

export interface PoolLoadMoreErrorProps {
  itemsLabel: string;
  isRetrying: boolean;
  onRetry: () => void;
}

export function PoolLoadMoreError({ itemsLabel, isRetrying, onRetry }: PoolLoadMoreErrorProps) {
  return (
    <Row role="alert" className="justify-between gap-3 border-t px-3 py-2 text-sm">
      <p className="text-foreground-muted">More {itemsLabel} could not be loaded.</p>
      <Button variant="outline" size="sm" isPending={isRetrying} onPress={onRetry}>
        Retry
      </Button>
    </Row>
  );
}
