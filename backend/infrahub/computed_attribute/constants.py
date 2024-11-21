PROCESS_JINJA2_AUTOMATION_NAME_PREFIX = "Computed-attribute-process-jinja2"
PROCESS_PYTHON_AUTOMATION_NAME_PREFIX = "Computed-attribute-process-python"

PROCESS_AUTOMATION_NAME_PREFIX = "Computed-attribute-process"
QUERY_AUTOMATION_NAME_PREFIX = "Computed-attribute-query"

PROCESS_AUTOMATION_NAME = "{prefix}::{identifier}::{scope}"
QUERY_AUTOMATION_NAME = QUERY_AUTOMATION_NAME_PREFIX + "::{identifier}::{scope}"

VALID_KINDS = ["Text", "URL"]
