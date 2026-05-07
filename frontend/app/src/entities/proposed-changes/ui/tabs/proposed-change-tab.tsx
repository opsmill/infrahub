import { Spinner } from "@infrahub/ui";

import { LinkTab } from "@/shared/components/ui/link";

export interface ProposedChangeTabProps {
  to: string;
  label: string;
  count?: number;
  isCountLoading?: boolean;
}

export function ProposedChangeTab({ to, label, count, isCountLoading }: ProposedChangeTabProps) {
  return (
    <LinkTab href={to}>
      {label}
      {isCountLoading && <Spinner className="mx-1" />}
      {!isCountLoading && count !== undefined && (
        <div className="rounded-md bg-gray-100 px-2 py-0.5 text-xs">{count}</div>
      )}
    </LinkTab>
  );
}
