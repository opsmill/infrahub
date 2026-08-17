import { Spinner } from "@infrahub/ui";

import { Badge } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";

export interface ProposedChangeTabProps {
  to: string;
  label: string;
  count?: number;
  isCountLoading?: boolean;
}

export function ProposedChangeTab({ to, label, count, isCountLoading }: ProposedChangeTabProps) {
  return (
    <LinkTab to={to}>
      {label}
      {isCountLoading && <Spinner className="mx-1" />}
      {!isCountLoading && count !== undefined && (
        <Badge className="rounded-full font-medium text-gray-80">{count}</Badge>
      )}
    </LinkTab>
  );
}
