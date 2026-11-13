import { CopyToClipboardButton } from "@/shared/components/buttons/copy-to-clipboard-button";
import { Row } from "@/shared/components/container";
import { classNames } from "@/shared/utils/common";

export interface PoolIdProps {
  id: string;
  className?: string;
}

export function PoolId({ id, className }: PoolIdProps) {
  return (
    <Row className={classNames("min-w-0 gap-1 text-sm", className)}>
      <span className="shrink-0">ID</span>
      <span className="min-w-0 truncate font-mono text-foreground-muted text-xs">{id}</span>
      <CopyToClipboardButton data={id} aria-label="Copy ID" />
    </Row>
  );
}
