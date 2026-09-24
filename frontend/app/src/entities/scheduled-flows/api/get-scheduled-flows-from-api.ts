import { graphql, graphqlClient } from "@/shared/api/graphql/client";

export const GET_SCHEDULED_FLOWS = graphql(`
  query GET_SCHEDULED_FLOWS {
    InfrahubScheduledFlows {
      count
      catalogue_only
      edges {
        node {
          deployment_id
          name
          workflow_type
          cron
          timezone
          interval_seconds
          next_run_at
          active
          concurrency_limit
          collision_strategy
          health
          deployment_created_at
          latest_run {
            id
            state
            state_name
            expected_start_time
            start_time
            end_time
          }
          recent_outcomes {
            window_hours
            total
            counts {
              state
              count
            }
          }
        }
      }
    }
  }
`);

export function getScheduledFlowsFromApi() {
  return graphqlClient.query({
    query: GET_SCHEDULED_FLOWS,
  });
}
