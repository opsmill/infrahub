# Grafana Dashboards

Rules for editing the bundled dashboards under `provisioning/dashboards/`.

- Reference only template variables the dashboard itself defines, and read its `templating` block
  rather than copying a reference across files: the names differ per dashboard. Every dashboard but
  `rabbitmq_instance_monitoring.json` defines `${datasource_prometheus}`; only the ones with Loki
  panels also define `${datasource_loki}` (`loki_monitoring.json`, despite the name, does not); and
  `rabbitmq_instance_monitoring.json` defines a plain `${datasource}`. Grafana resolves an
  undefined variable to nothing, and only when the panel or link is used, so the mistake survives a
  visual check.
- When changing a variable or metric, sweep every surface of the JSON, not just query targets:
  drill-down/data links and legend URLs carry `var-<name>=` references that break silently.
- These files are bind-mounted into `docker-compose-observability.yml`, and the standalone variant
  embeds them inline. After editing anything under `provisioning/`, regenerate
  `docker-compose-observability-standalone.yml` by running `python convert_compose_standalone.py`
  from `development/` (the script resolves its default input/output paths against the working
  directory).
