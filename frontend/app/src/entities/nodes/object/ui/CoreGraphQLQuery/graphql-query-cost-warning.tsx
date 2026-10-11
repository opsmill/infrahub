import { Card, CardHeader } from "@infrahub/ui";
import { ExternalLinkIcon, TriangleAlertIcon } from "lucide-react";
import React from "react";

import { Row } from "@/shared/components/container";
import { DateDisplay } from "@/shared/components/display/date-display";
import { DetailRow } from "@/shared/components/display/detail-row";
import { Link } from "@/shared/components/ui/link";
import { INFRAHUB_DOC_LOCAL } from "@/shared/config/config";
import { classNames } from "@/shared/utils/common";
import { formatNumberDisplay } from "@/shared/utils/number";

import {
  GRAPHQL_QUERY_HIGH_COST_LEVEL,
  type GraphqlQueryCostEstimate,
  GraphqlQueryCostEstimateSchema,
} from "@/entities/nodes/object/domain/model/graphql-query-cost";

const COST_LEVEL_DOCUMENTATION_URL = `${INFRAHUB_DOC_LOCAL}/development-resources/graphql/query-cost#view-the-cost-level-of-a-stored-query`;

interface GraphqlQueryCostWarningProps {
  /** Value of the `cost_level` attribute of the stored query. */
  costLevel: unknown;
  /** Value of the `cost_estimate` attribute of the stored query, validated here because it is free-form JSON. */
  costEstimate: unknown;
  className?: string;
}

export function GraphqlQueryCostWarning({
  costLevel,
  costEstimate,
  className,
}: GraphqlQueryCostWarningProps) {
  const titleId = React.useId();

  if (costLevel !== GRAPHQL_QUERY_HIGH_COST_LEVEL) {
    return null;
  }

  const estimate = GraphqlQueryCostEstimateSchema.safeParse(costEstimate);

  return (
    <Card
      role="region"
      aria-labelledby={titleId}
      className={classNames("border-amber-300", className)}
      data-testid="graphql-query-cost-warning"
    >
      <CardHeader className="flex items-center gap-2 border-b-amber-200 from-amber-100 to-amber-50 text-amber-900">
        <TriangleAlertIcon className="size-4 shrink-0 text-amber-600" aria-hidden="true" />
        <span id={titleId}>High estimated cost</span>
      </CardHeader>

      <p className="px-3 py-2 text-sm">
        One run of this query is estimated to read more database rows than the configured limit.
      </p>

      {estimate.success && <GraphqlQueryCostFigures estimate={estimate.data} />}

      <Row className="border-neutral-200 border-t px-3 py-2 text-sm">
        <Link to={COST_LEVEL_DOCUMENTATION_URL} target="_blank" rel="noreferrer">
          How the cost level is estimated
        </Link>
        <ExternalLinkIcon className="size-3.5 text-gray-500" aria-hidden="true" />
      </Row>
    </Card>
  );
}

function GraphqlQueryCostFigures({ estimate }: { estimate: GraphqlQueryCostEstimate }) {
  return (
    <div className="divide-y divide-gray-200 border-neutral-200 border-t">
      <DetailRow label="Worst case">
        <span>{formatDatabaseRows(estimate.worst_case.database_rows)}</span>
        <span className="text-gray-500 text-xs">For the nodes with the most peers</span>
      </DetailRow>

      <DetailRow label="Expected">
        <span>{formatDatabaseRows(estimate.expected.database_rows)}</span>
        <span className="text-gray-500 text-xs">For nodes with the average number of peers</span>
      </DetailRow>

      <DetailRow label="Limit">{formatDatabaseRows(estimate.high_cost_database_rows)}</DetailRow>

      {estimate.statistics_computed_at && (
        <DetailRow label="Statistics computed">
          <DateDisplay date={estimate.statistics_computed_at} />
        </DetailRow>
      )}

      {estimate.costliest_fields.length > 0 && (
        <DetailRow label="Fields with the most worst-case rows">
          <ul className="space-y-1">
            {estimate.costliest_fields.map((field) => (
              <li key={field.path}>
                <code className="break-all">{field.path}</code>:{" "}
                {formatDatabaseRows(field.worst_case_database_rows)}
              </li>
            ))}
          </ul>
        </DetailRow>
      )}

      {estimate.fields_without_estimate > 0 && (
        <p className="px-3 py-2 text-gray-500 text-xs">
          {estimate.fields_without_estimate === 1
            ? "1 field of the query has no estimate and is not counted in these figures."
            : `${estimate.fields_without_estimate} fields of the query have no estimate and are not counted in these figures.`}
        </p>
      )}
    </div>
  );
}

function formatDatabaseRows(rows: number): string {
  return `${formatNumberDisplay(rows)} database rows`;
}
