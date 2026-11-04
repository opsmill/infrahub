# Contract: Report of the diagnostic skill

**Requirements**: FR-013 to FR-015, FR-017a, FR-021 (1.13); FR-017, FR-018 (later release of story
4) | **Research**: R6, R7

The skill `infrahub-diagnosing-performance` writes this report at the end of each run. The graders in
`infrahub-skills` check these sections.

## Sections, in this order

1. **Instance.** Infrahub version from `infrahub_info{version}`, and the time window read. When the
   version is before 1.13, the report has only this section and says that the operator must upgrade to
   1.13 or later.
2. **Data sources.** The Prometheus, Tempo and Loki data sources found, by name and type. For each one
   that is missing: the checks that did not run.
3. **Slow component.** One of: Neo4j, the API server, the task workers, the code of a generator, or
   "not found".
4. **Findings.** One entry per finding, each with:
   - what was found, in one sentence;
   - its evidence: the metric query and its value, the trace ID, or the log line with its time;
   - the data source it came from.
5. **Not checked.** Each check that did not run, with the reason and the next step. For example:
   - no trace was sampled in the window. Next step: a super admin raises the sampling ratio for a
     limited time without a restart (`PUT /api/troubleshooting/trace-sample-ratio` or `infrahubctl`,
     from INFP-742), and the operator asks again after the slowness happens;
   - the trace is older than 24 hours, so Loki has no log lines for it.
6. **Missing panels.** In 1.13: for each question that the shipped dashboards do not answer, the
   query, the panel type and the data source, so that the operator can add it in Grafana by hand.
   The skill changes nothing in Grafana (FR-017a). From the release of story 4: each dashboard built or
   changed, with its UID, and whether the user chose to contribute it.

## Order of the checks

| Step | Reads | Stops the run when |
|------|-------|--------------------|
| 1. Version | `infrahub_info{version}` | The version is before 1.13 |
| 2. Data sources | Data source list, by type | No Prometheus data source |
| 3. Durations | Request, GraphQL and flow run durations | Never |
| 4. Component | Database, lock, connection pool, task worker and admission metrics | Never |
| 5. Trace | A slow trace in Tempo for the component found | Never; "Not checked" when no trace is found |
| 6. Logs | Loki lines with that `trace_id` | Never; "Not checked" when no line is found |

## Contribution of a dashboard (later release of story 4)

Not in 1.13. The skill asks the user before it creates a GitHub issue or pull request. Without a yes, nothing is
sent to GitHub (FR-018). The proposal targets `development/grafana` in `opsmill/infrahub` and contains
the dashboard JSON.
