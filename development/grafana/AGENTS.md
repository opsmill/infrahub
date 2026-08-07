# Grafana Dashboards

Rules for editing the bundled dashboards under `provisioning/dashboards/`.

- Reference only template variables the dashboard itself defines — `${datasource_prometheus}` or
  `${datasource_loki}`, never a generic `$datasource`. Grafana resolves an undefined variable to
  nothing, and only when the panel or link is used, so the mistake survives a visual check.
- When changing a variable or metric, sweep every surface of the JSON, not just query targets:
  drill-down/data links and legend URLs carry `var-<name>=` references that break silently.
- These files are bind-mounted into `docker-compose-observability.yml`, and the standalone variant
  embeds them inline. After editing anything under `provisioning/`, regenerate
  `docker-compose-observability-standalone.yml` with `python development/convert_compose_standalone.py`.
