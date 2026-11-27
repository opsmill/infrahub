import { Button } from "@infrahub/ui";

import { Row } from "@/shared/components/container";

export interface PoolAllocationsErrorProps {
  message: string;
  isRetrying: boolean;
  onRetry: () => void;
}

export function PoolAllocationsError({ message, isRetrying, onRetry }: PoolAllocationsErrorProps) {
  return (
    <Row role="alert" className="justify-between gap-3 border-t px-3 py-2 text-sm">
      <p className="text-foreground-muted">{message}</p>
      <Button variant="outline" size="sm" isPending={isRetrying} onPress={onRetry}>
        Retry
      </Button>
    </Row>
  );
}
