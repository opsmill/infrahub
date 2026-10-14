import { Card, LinkButton } from "@infrahub/ui";
import { LinkIcon } from "lucide-react";

import { Col } from "@/shared/components/container";
import { pluralize } from "@/shared/utils/string";

import type { AllocationScopeField } from "@/entities/resource-manager/ui/hooks/use-allocation-scope-fields";
import type { NumberPoolDivisionInvalidCause } from "@/entities/resource-manager/ui/hooks/use-number-pool-division";
import { getNumberPoolDivisionsUrl } from "@/entities/resource-manager/ui/routing/number-pool-urls";

const fieldList = new Intl.ListFormat("en", { style: "long", type: "conjunction" });

const describeCause = (cause: NumberPoolDivisionInvalidCause, fields: AllocationScopeField[]) => {
  if (cause.reason === "unreadable") {
    return "The allocation scope in this link cannot be read. The link may be incomplete or edited by hand.";
  }

  const given = cause.count === 0 ? "no value" : pluralize(cause.count, "value");
  const fieldLabels = fieldList.format(fields.map((field) => field.label));
  return `This link gives ${given}, but this pool divides its numbers by ${pluralize(fields.length, "field")}: ${fieldLabels}. The link may have been edited, or copied from another pool.`;
};

export interface NumberPoolDivisionInvalidProps {
  poolId: string;
  fields: AllocationScopeField[];
  cause: NumberPoolDivisionInvalidCause;
}

export function NumberPoolDivisionInvalid({
  poolId,
  fields,
  cause,
}: NumberPoolDivisionInvalidProps) {
  return (
    <Card>
      <Col className="items-center gap-4 px-6 py-16 text-center">
        <span className="flex size-10 items-center justify-center rounded-xl bg-content-muted text-foreground-muted">
          <LinkIcon className="size-5" aria-hidden />
        </span>
        <Col className="items-center gap-1">
          <h2 className="font-medium">Cannot open this allocation scope</h2>
          <p className="max-w-md text-pretty text-foreground-muted text-sm">
            {describeCause(cause, fields)}
          </p>
        </Col>
        <LinkButton variant="outline" size="sm" href={getNumberPoolDivisionsUrl(poolId)}>
          View all allocation scopes
        </LinkButton>
      </Col>
    </Card>
  );
}
