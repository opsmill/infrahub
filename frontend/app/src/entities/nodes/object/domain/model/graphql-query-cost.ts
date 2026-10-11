import * as z from "zod";

export const GRAPHQL_QUERY_HIGH_COST_LEVEL = "high";

/** The parts of the `cost_estimate` attribute of a stored GraphQL query that the web UI shows, once the query has an estimate. */
export const GraphqlQueryCostEstimateSchema = z.object({
  high_cost_database_rows: z.number(),
  statistics_computed_at: z.string().nullable(),
  expected: z.object({ database_rows: z.number() }),
  worst_case: z.object({ database_rows: z.number() }),
  fields_without_estimate: z.number(),
  costliest_fields: z.array(
    z.object({
      path: z.string(),
      worst_case_database_rows: z.number(),
    })
  ),
});

export type GraphqlQueryCostEstimate = z.infer<typeof GraphqlQueryCostEstimateSchema>;
