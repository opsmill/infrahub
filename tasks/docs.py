import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from invoke import Context, task
from pydantic_settings import EnvSettingsSource

from .utils import ESCAPED_REPO_PATH, check_if_command_available

if TYPE_CHECKING:
    from pydantic import BaseModel

CURRENT_DIRECTORY = Path(__file__).parent.resolve()
DOCUMENTATION_DIRECTORY = CURRENT_DIRECTORY.parent / "docs"


@task
def build(context: Context) -> None:
    """Build documentation website."""
    exec_cmd = "npm run build"

    with context.cd(DOCUMENTATION_DIRECTORY):
        output = context.run(exec_cmd)

    if output.exited != 0:
        sys.exit(-1)


@task
def generate(context: Context) -> None:
    """Generate all documentation output from code."""
    _generate(context=context)


@task
def generate_schema(context: Context) -> None:  # noqa: ARG001
    """Generate documentation for the schema."""
    _generate_infrahub_schema_documentation()
    _generate_infrahub_schema_attribute_kind_parameters_snippet()


@task
def generate_config(context: Context) -> None:  # noqa: ARG001
    _generate_infrahub_config_documentation()


@task
def generate_infrahub_cli(context: Context) -> None:
    """Generate documentation for the infrahub cli."""
    _generate_infrahub_cli_documentation(context=context)


# @task
# def generate_infrahubctl(context: Context) -> None:
#    """Generate documentation for the infrahubctl cli."""
#    _generate_infrahubctl_documentation(context=context)


@task
def generate_repository(context: Context) -> None:  # noqa: ARG001
    """Generate documentation for the repository configuration file."""
    _generate_infrahub_repository_configuration_documentation()


# @task
# def generate_python_sdk(context: Context) -> None:
#    """Generate documentation for the Python SDK."""
#    _generate_infrahub_sdk_configuration_documentation(context=context)


@task
def generate_bus_events(context: Context) -> None:  # noqa: ARG001
    """Generate documentation for Infrahub Bus events."""
    _generate_infrahub_bus_events_documentation()


@task
def generate_infrahub_events(context: Context) -> None:  # noqa: ARG001
    """Generate documentation for Infrahub events."""
    _generate_infrahub_events_documentation()


@task
def install(context: Context) -> None:
    """Install documentation dependencies."""
    exec_cmd = "npm install"

    with context.cd(DOCUMENTATION_DIRECTORY):
        output = context.run(exec_cmd)

    if output.exited != 0:
        sys.exit(-1)


@task
def validate(context: Context) -> None:
    """Validate that the generated documentation is committed to Git."""
    _generate(context=context)
    exec_cmd = "git diff --exit-code docs"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def serve(context: Context) -> None:
    """Run documentation server in development mode."""

    exec_cmd = "npm run serve"

    with context.cd(DOCUMENTATION_DIRECTORY):
        context.run(exec_cmd)


@task
def vale(context: Context) -> None:
    """Run vale to validate the documentation."""
    has_vale = check_if_command_available(context=context, command_name="vale")

    if not has_vale:
        print("Warning, Vale is not installed")
        return

    exec_cmd = "vale $(find ./docs -type f \\( -name '*.mdx' -o -name '*.md' \\) -not -path './docs/node_modules/*')"
    print(" - [docs] Lint docs with vale")
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def markdownlint(context: Context) -> None:
    """Lint markdown files with markdownlint-cli2.

    Uses .markdownlint-cli2.yaml for configuration and ignore patterns.
    """
    has_markdownlint = check_if_command_available(context=context, command_name="markdownlint-cli2")

    if not has_markdownlint:
        print("Warning, markdownlint-cli2 is not installed")
        return
    exec_cmd = "markdownlint-cli2 '**/*.{md,mdx}'"
    print(" - [docs] Lint docs with markdownlint-cli2")
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def format_markdownlint(context: Context) -> None:
    """Run markdownlint-cli2 to format all .md/mdx files.

    Uses .markdownlint-cli2.yaml for configuration and ignore patterns.
    """
    print(" - [docs] Format code with markdownlint-cli2")
    exec_cmd = "markdownlint-cli2 '**/*.{md,mdx}' --fix"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def format(context: Context) -> None:
    """This will run all formatter."""
    format_markdownlint(context)


@task
def lint(context: Context) -> None:
    """This will run all linter."""
    markdownlint(context)
    vale(context)


def _generate_infrahub_cli_documentation(context: Context) -> None:
    """Generate the documentation for infrahub cli using typer-cli."""

    CLI_COMMANDS = (
        ("infrahub.cli.db", "infrahub db", "infrahub-db"),
        ("infrahub.cli.server", "infrahub server", "infrahub-server"),
        ("infrahub.cli.dev", "infrahub dev", "infrahub-dev"),
        ("infrahub.cli.upgrade", "infrahub upgrade", "infrahub-upgrade"),
    )

    print(" - Generate Infrahub CLI documentation")
    with context.cd(ESCAPED_REPO_PATH):
        for command in CLI_COMMANDS:
            exec_cmd = f'uv run typer {command[0]} utils docs --name "{command[1]}" --output docs/docs/reference/infrahub-cli/{command[2]}.mdx'
            context.run(exec_cmd)


def _generate(context: Context) -> None:
    """Generate documentation output from code."""
    _generate_infrahub_cli_documentation(context=context)
    _generate_infrahub_schema_documentation()
    _generate_infrahub_repository_configuration_documentation()
    _generate_infrahub_bus_events_documentation()
    _generate_infrahub_events_documentation()
    _generate_infrahub_config_documentation()


def _generate_infrahub_schema_attribute_kind_parameters_snippet() -> None:
    """Generate documentation for any attributes that have parameters defined to be defined by users."""
    import jinja2

    from infrahub.core.schema.attribute_schema import attribute_schema_class_by_kind

    kind_ap_parameters: dict[str, dict] = {}
    for kind, schema_cls in attribute_schema_class_by_kind.items():
        # If the schema has a parameters class, add it to the list
        init_schema = schema_cls(name="ignore", kind=kind)
        if hasattr(init_schema, "parameters") and init_schema.parameters is not None:
            params = {
                param: info
                for param, info in init_schema.parameters.__class__.model_fields.items()
                if info.json_schema_extra and info.json_schema_extra.get("update") == "validate_constraint"
            }
            kind_ap_parameters[kind] = params
    # for _, obj in inspect.getmembers(ap):
    #     if inspect.isclass(obj) and issubclass(obj, ap.AttributeParameters) and obj is not ap.AttributeParameters:
    #         kind_ap_parameters.append(obj)

    template_file = Path(DOCUMENTATION_DIRECTORY) / "_templates" / "schema" / "attribute_kind_params.j2"
    output_file = Path(DOCUMENTATION_DIRECTORY) / "docs" / "snippets" / "attribute-kind-params.mdx"
    output_label = "docs/docs/snippets/attribute-kind-params.mdx"
    if not template_file.exists():
        print(f"Unable to find the template file at {template_file}")
        sys.exit(-1)

    template_text = template_file.read_text(encoding="utf-8")

    environment = jinja2.Environment()
    template = environment.from_string(template_text)
    rendered_file = template.render(kinds=kind_ap_parameters)

    output_file.write_text(rendered_file, encoding="utf-8")
    print(f"Docs saved to: {output_label}")


def _generate_infrahub_schema_documentation() -> None:
    """Generate documentation for the schema"""
    import jinja2

    from infrahub.core.schema import internal, internal_schema

    schemas_to_generate = {
        "node": internal_schema,
        "attribute": internal_schema,
        "relationship": internal_schema,
        "generic": internal_schema,
        "validator-migration": internal,
    }
    print(" - Generate Infrahub schema documentation")
    for schema_name, schema in schemas_to_generate.items():
        template_file = Path(DOCUMENTATION_DIRECTORY) / "_templates" / "schema" / f"{schema_name}.j2"
        output_file = Path(DOCUMENTATION_DIRECTORY) / "docs" / "reference" / "schema" / f"{schema_name}.mdx"
        output_label = f"docs/docs/reference/schema/{schema_name}.mdx"
        if not template_file.exists():
            print(f"Unable to find the template file at {template_file}")
            sys.exit(-1)

        template_text = template_file.read_text(encoding="utf-8")

        environment = jinja2.Environment()
        template = environment.from_string(template_text)
        rendered_file = template.render(schema=schema)

        output_file.write_text(rendered_file, encoding="utf-8")
        print(f"Docs saved to: {output_label}")


def _extract_nested_parameters(
    prop_schema: dict,
    model_fields: dict,
    env_source: EnvSettingsSource,
    defs: dict[str, object],
    parent_default: dict | None = None,
    env_prefix: str | None = None,
) -> list["ConfigurationSectionParameter"]:
    """
    Recursively extract nested parameters for object-type config fields.

    Args:
        prop_schema: The property schema dictionary.
        model_fields: The model fields for the parent section.
        env_source: The environment settings source.
        defs: The schema definitions.
        parent_default: The default value for the parent property, if any.
        env_prefix: The environment variable prefix.

    Returns:
        List of ConfigurationSectionParameter objects for nested fields.
    """
    from infrahub import config

    nested_params: list[ConfigurationSectionParameter] = []

    # Resolve $ref at the top level if present
    if "$ref" in prop_schema:
        ref_name = prop_schema["$ref"].split("/")[-1]
        prop_schema = defs[ref_name]

    for nested_name, orig_nested_schema in prop_schema.get("properties", {}).items():
        nested_schema = orig_nested_schema

        # Handle anyOf for optional nested objects
        if "anyOf" in nested_schema:
            for option in nested_schema["anyOf"]:
                if "$ref" in option:
                    ref_name = option["$ref"].split("/")[-1]
                    ref_schema = defs[ref_name]
                    section_class = getattr(config, ref_name)
                    env_prefix = section_class.model_config.get("env_prefix")
                    env_source = EnvSettingsSource(section_class, env_prefix=env_prefix)
                    nested_schema = ref_schema
                    break
            else:
                continue

        # Resolve $ref inside the property if present
        nested_type = nested_schema.get("type")
        if "$ref" in nested_schema:
            ref_name = nested_schema["$ref"].split("/")[-1]
            nested_schema = defs[ref_name]
            nested_type = nested_schema.get("type")

        # If the nested type is object, flatten by recursing into _process_section_parameters
        if nested_type == "object":
            nested_params.extend(
                _process_section_parameters(
                    section_schema=nested_schema,
                    model_fields={},
                    env_source=env_source,
                    defs=defs,
                    env_prefix=env_prefix,
                )
            )
            continue

        # Determine environment variable(s) for this field
        env = None
        if nested_name in model_fields:
            env_names = [
                e.upper() for _, e, _ in env_source._extract_field_info(model_fields[nested_name], nested_name)
            ]
            if env_names:
                env = " | ".join(sorted(set(env_names)))

        # Determine default value for this field
        if parent_default and nested_name in parent_default:
            default_value = parent_default[nested_name]
        else:
            default_value = nested_schema.get("default")

        param = ConfigurationSectionParameter(
            name=nested_schema.get("title", nested_name).lower(),
            description=nested_schema.get("description"),
            default=default_value,
            type=nested_type,
            env=env,
        )

        # Recursively extract deeper nesting for arrays of objects
        if nested_type == "array" and nested_schema.get("items", {}).get("type") == "object":
            param.nested_parameters = _process_section_parameters(
                section_schema=nested_schema["items"],
                model_fields={},
                env_source=env_source,
                defs=defs,
                env_prefix=None,
            )

        nested_params.append(param)
    return nested_params


def _process_section_parameters(
    section_schema: dict,
    model_fields: dict,
    env_source: EnvSettingsSource,
    defs: dict[str, Any],
    env_prefix: str | None,
) -> list["ConfigurationSectionParameter"]:
    """Process and extract parameters for a configuration section.

    Args:
        section_schema: The JSON schema for the section.
        model_fields: The model fields for the section class.
        env_source: The environment settings source.
        defs: The schema definitions.
        env_prefix: The environment variable prefix.

    Returns:
        List of ConfigurationSectionParameter objects.
    """
    parameters = []
    for param_name, param_schema in section_schema["properties"].items():
        param_type = param_schema.get("type")
        if param_type == "array":
            array_type = param_schema.get("items", {}).get("type")
            if array_type:
                param_type = f"array[{array_type}]"

        env = f"{env_prefix}{param_name}".upper() if env_prefix else None

        nested_parameters = []
        default = param_schema.get("default")
        ref = param_schema.get("$ref")
        definition = None

        if "properties" in param_schema or ref:
            if ref:
                definition = defs.get(ref.split("/")[-1])
            else:
                definition = param_schema
            if definition and definition.get("type") == "object":
                param_type = "object"
                default = "Check nested parameters"
                nested_parameters = _extract_nested_parameters(
                    definition, model_fields, env_source, defs, parent_default=definition.get("default")
                )
            elif definition:
                param_type = definition.get("type")
                if "enum" in definition:
                    param_type += " (" + ", ".join([str(e) for e in definition["enum"]]) + ")"

        parameters.append(
            ConfigurationSectionParameter(
                name=param_schema.get("title", param_name).lower(),
                description=param_schema.get("description"),
                default=default,
                type=param_type,
                env=env,
                nested_parameters=nested_parameters,
            )
        )
    return parameters


def _generate_infrahub_config_documentation() -> None:
    """Generate documentation for Infrahub configuration sections.

    This function introspects the config.Settings model, extracts all configuration
    sections and their parameters, and renders documentation using a Jinja2 template.
    """
    import jinja2
    from pydantic_settings import EnvSettingsSource

    from infrahub import config

    sections: list[ConfigurationSection] = []
    schema = config.Settings.model_json_schema()
    defs = schema.get("$defs", {})

    print("Rendering doc for Infrahub config...")

    for section_name, section_prop in schema["properties"].items():
        if section_name == "logging":
            continue  # Skip logging as it is unused for remote logging to Sentry

        section_ref = section_prop["$ref"]
        section_class_name = section_ref.split("/")[-1]
        section_class: type[BaseModel] = getattr(config, section_class_name)
        section_schema = section_class.model_json_schema()
        env_prefix = section_class.model_config.get("env_prefix")
        env_source = EnvSettingsSource(section_class, env_prefix=env_prefix)
        model_fields = getattr(section_class, "model_fields", {})

        parameters = _process_section_parameters(
            section_schema=section_schema,
            model_fields=model_fields,
            env_source=env_source,
            defs=defs,
            env_prefix=env_prefix,
        )

        section = ConfigurationSection(
            name=section_name,
            description=section_class.__doc__ or "",
            parameters=parameters,
        )
        sections.append(section)

    # Render the template
    template_file = Path(DOCUMENTATION_DIRECTORY) / "_templates" / "infrahub_config.j2"
    output_label = "docs/reference/configuration.mdx"
    output_file = Path(DOCUMENTATION_DIRECTORY) / output_label

    if not template_file.exists():
        print(f"Unable to find the template file at {template_file}")
        sys.exit(-1)

    template_text = Path(template_file).read_text(encoding="utf-8")
    environment = jinja2.Environment(trim_blocks=True)
    template = environment.from_string(template_text)
    rendered_file = template.render(sections=sections)

    Path(output_file).write_text(rendered_file, encoding="utf-8")
    print(f"Docs saved to: {output_label}")


def _get_env_vars() -> dict[str, str]:
    from infrahub_sdk.config import ConfigBase

    env_vars: dict[str, list[str]] = defaultdict(list[str])
    settings = ConfigBase()
    env_settings = EnvSettingsSource(settings.__class__, env_prefix=settings.model_config.get("env_prefix"))

    for field_name, model_field in settings.__class__.model_fields.items():
        for field_key, field_env_name, _ in env_settings._extract_field_info(model_field, field_name):
            env_vars[field_key].append(field_env_name.upper())

    return env_vars


def _generate_infrahub_sdk_configuration_documentation() -> None:
    """Generate documentation for the Infrahub SDK configuration"""
    import jinja2
    from infrahub_sdk.config import ConfigBase

    schema = ConfigBase.model_json_schema()
    env_vars = _get_env_vars()
    definitions = schema["$defs"]

    properties = []
    for name, prop in schema["properties"].items():
        choices: list[dict[str, Any]] = []
        kind = ""
        composed_type = ""
        if "allOf" in prop:
            choices = definitions[prop["allOf"][0]["$ref"].split("/")[-1]].get("enum", [])
            kind = definitions[prop["allOf"][0]["$ref"].split("/")[-1]].get("type", "")
        if "anyOf" in prop:
            composed_type = ", ".join(i["type"] for i in prop.get("anyOf", []) if "type" in i and i["type"] != "null")
        properties.append(
            {
                "name": name,
                "description": prop.get("description", ""),
                "type": prop.get("type", kind) or composed_type or "object",
                "choices": choices,
                "default": prop.get("default", ""),
                "env_vars": env_vars[name],
            }
        )

    print(" - Generate Infrahub SDK configuration documentation")

    template_file = Path(DOCUMENTATION_DIRECTORY) / "_templates" / "sdk_config.j2"
    output_file = Path(DOCUMENTATION_DIRECTORY) / "docs" / "python-sdk" / "reference" / "config.mdx"
    output_label = "docs/docs/python-sdk/reference/config.mdx"

    if not template_file.exists():
        print(f"Unable to find the template file at {template_file}")
        sys.exit(-1)

    template_text = template_file.read_text(encoding="utf-8")

    environment = jinja2.Environment(trim_blocks=True)
    template = environment.from_string(template_text)
    rendered_file = template.render(properties=properties)

    output_file.write_text(rendered_file, encoding="utf-8")
    print(f"Docs saved to: {output_label}")


def _generate_infrahub_repository_configuration_documentation() -> None:
    """Generate documentation for the Infrahub repository configuration file"""
    from copy import deepcopy

    import jinja2
    from infrahub_sdk.schema.repository import InfrahubRepositoryConfig

    schema = InfrahubRepositoryConfig.model_json_schema()

    properties = [
        {
            "name": name,
            "description": property["description"],
            "title": property["title"],
            "type": property["type"],
            "items_type": property["items"]["$ref"].split("/")[-1]
            if "$ref" in property["items"]
            else property["items"]["type"],
            "items_format": property["items"]["format"] if "format" in property["items"] else None,
        }
        for name, property in schema["properties"].items()
    ]
    definitions = deepcopy(schema["$defs"])

    for name, definition in schema["$defs"].items():
        for property, value in definition["properties"].items():
            definitions[name]["properties"][property]["required"] = property in definition["required"]
            if "anyOf" in value:
                definitions[name]["properties"][property]["type"] = ", ".join(
                    [i["type"] for i in value["anyOf"] if i["type"] != "null"]
                )

    print(" - Generate Infrahub repository configuration documentation")

    template_file = Path(DOCUMENTATION_DIRECTORY) / "_templates" / "dotinfrahub.j2"
    output_file = Path(DOCUMENTATION_DIRECTORY) / "docs" / "reference" / "dotinfrahub.mdx"
    output_label = "docs/docs/reference/dotinfrahub.mdx"
    if not template_file.exists():
        print(f"Unable to find the template file at {template_file}")
        sys.exit(-1)

    template_text = template_file.read_text(encoding="utf-8")

    environment = jinja2.Environment()
    template = environment.from_string(template_text)
    rendered_file = template.render(properties=properties, definitions=definitions)

    output_file.write_text(rendered_file, encoding="utf-8")
    print(f"Docs saved to: {output_label}")


def _generate_infrahub_bus_events_documentation() -> None:
    """
    Generate documentation for all classes in the event system into a single file
    using a Jinja2 template. Accessible via `invoke generate_infrahub_events_documentation`.
    """
    from infrahub.message_bus import InfrahubMessage, InfrahubResponse

    def group_classes_by_category(
        classes: dict[str, type[InfrahubMessage | InfrahubResponse]],
        priority_map: dict[str, int] | None = None,
    ) -> dict[str, dict[str, list[dict[str, any]]]]:
        """
        Group classes into a nested dictionary by primary and secondary categories, including priority.
        """
        grouped = defaultdict(lambda: defaultdict(list))
        for event_name, cls in classes.items():
            parts = event_name.split(".")
            primary, secondary = parts[0], ".".join(parts[:2])
            priority = priority_map.get(event_name, 3) if priority_map else -1
            description = cls.__doc__.strip() if cls.__doc__ else None

            # Retrieve the model schema and expand fields if necessary
            schema = cls.model_json_schema().get("properties", {})
            fields = []
            for prop, details in schema.items():
                # For a nested "data" field, expand its inner properties if available.
                if prop == "data" and hasattr(cls, "__annotations__") and "data" in cls.__annotations__:
                    data_type = cls.__annotations__["data"]
                    if hasattr(data_type, "model_json_schema"):
                        data_schema = data_type.model_json_schema().get("properties", {})
                        for dprop, ddetails in data_schema.items():
                            fields.append(
                                {
                                    "name": f"data.{dprop}",
                                    "type": ddetails.get("type", "N/A"),
                                    "description": ddetails.get("description", "N/A"),
                                    "default": ddetails.get("default", "None"),
                                }
                            )
                    else:
                        fields.append(
                            {
                                "name": prop,
                                "type": details.get("type", "N/A"),
                                "description": details.get("description", "N/A"),
                                "default": details.get("default", "None"),
                            }
                        )
                else:
                    fields.append(
                        {
                            "name": prop,
                            "type": details.get("type", "N/A"),
                            "description": details.get("description", "N/A"),
                            "default": details.get("default", "None"),
                        }
                    )
            event_info = {
                "event_name": event_name,
                "description": description,
                "priority": priority,
                "fields": fields,
            }
            grouped[primary][secondary].append(event_info)
        return grouped

    template_file = DOCUMENTATION_DIRECTORY / "_templates" / "message-bus-events.j2"
    output_file = DOCUMENTATION_DIRECTORY / "docs" / "reference" / "message-bus-events.mdx"

    print(" - Generate Infrahub Bus Events documentation")

    if not template_file.exists():
        print(f"Unable to find the template file at {template_file}")
        sys.exit(-1)

    import jinja2

    from infrahub.message_bus.messages import MESSAGE_MAP, PRIORITY_MAP, RESPONSE_MAP

    template_text = template_file.read_text(encoding="utf-8")
    environment = jinja2.Environment()
    template = environment.from_string(template_text)

    message_classes = group_classes_by_category(classes=MESSAGE_MAP, priority_map=PRIORITY_MAP)
    response_classes = group_classes_by_category(classes=RESPONSE_MAP, priority_map=PRIORITY_MAP)

    rendered_doc = template.render(message_classes=message_classes, response_classes=response_classes)

    output_file.parent.mkdir(exist_ok=True)
    output_file.write_text(rendered_doc, encoding="utf-8")
    print(f"Docs saved to: {output_file}")


@dataclass
class ConfigurationSectionParameter:
    name: str
    description: str
    default: Any | None = None
    type: str | None = None
    env: str | None = None
    nested_parameters: list["ConfigurationSectionParameter"] = field(default_factory=list)


@dataclass
class ConfigurationSection:
    """Represents a configuration section for documentation.

    Args:
        name: The name of the configuration section.
        description: The section's description.
        parameters: The list of parameters in this section.
    """

    name: str
    description: str
    parameters: list["ConfigurationSectionParameter"] = field(default_factory=list)


def _generate_infrahub_events_documentation() -> None:
    """
    Generate documentation for all Infrahub events into a single MDX file
    using a Jinja2 template. Accessible via `invoke generate_infrahub_event_documentation`.

    Note: Ensure all event classes (like GroupMutatedEvent, CommitUpdatedEvent, etc.) are imported
    so that they appear in the introspection.
    """
    import re
    from importlib import import_module
    from pkgutil import walk_packages

    import jinja2

    import infrahub.events
    from infrahub.events.models import EventMeta
    from infrahub.events.utils import get_all_events

    def load_all_event_modules(package: Any) -> None:  # noqa: ANN401
        """Recursively load all modules in the given package."""
        for _, modname, _ in walk_packages(package.__path__, package.__name__ + "."):
            import_module(modname)

    def format_event_name(raw_name: str) -> str:
        """
        Insert spaces before capitals and remove a trailing "Event", if present.
        For example: "NodeCreatedEvent" becomes "Node Created Event".
        """
        formatted = re.sub(r"(?<!^)(?=[A-Z])", " ", raw_name)
        return formatted.strip()

    def group_events_by_category(event_classes: list[type]) -> dict[str, list[dict[str, Any]]]:
        grouped = defaultdict(list)
        for cls in event_classes:
            # Extract the primary category from the class name (like "Node", "Group", "Commit")
            category = re.match(r"([A-Z][a-z]+)", cls.__name__)
            if not category:
                continue
            primary = category.group(1)
            description = cls.__doc__.strip() if cls.__doc__ else ""
            # Use helper functions to produce a friendly event name and an event type
            event_name_formatted = format_event_name(cls.__name__)
            event_type = cls.event_name

            schema = cls.model_json_schema().get("properties", {})
            fields = []
            for prop, details in schema.items():
                # Expand the "meta" field using the EventMeta model.
                if prop == "meta":
                    meta_schema = EventMeta.model_json_schema().get("properties", {})
                    for mprop, mdetails in meta_schema.items():
                        fields.append(
                            {
                                "name": f"meta.{mprop}",
                                "description": mdetails.get("description", "N/A"),
                            }
                        )
                    continue
                fields.append(
                    {
                        "name": prop,
                        "description": details.get("description", "N/A"),
                    }
                )

            event_info = {
                "event_name": event_name_formatted,
                "infrahub_node_kind_event": cls.infrahub_node_kind_event,
                "event_type": event_type,
                "description": description,
                "fields": fields,
            }
            grouped[primary].append(event_info)

        for primary, events in grouped.items():
            grouped[primary] = sorted(events, key=lambda x: x["event_name"])

        return grouped

    template_file = DOCUMENTATION_DIRECTORY / "_templates" / "infrahub-events.j2"
    output_file = DOCUMENTATION_DIRECTORY / "docs" / "reference" / "infrahub-events.mdx"

    print(" - Generating Infrahub Events documentation")

    if not template_file.exists():
        print(f"Unable to find the template file at {template_file}")
        sys.exit(-1)

    template_text = template_file.read_text(encoding="utf-8")
    environment = jinja2.Environment(trim_blocks=True)
    template = environment.from_string(template_text)

    # IMPORTANT: Ensure all event classes are imported so that they are found by introspection.
    load_all_event_modules(package=infrahub.events)
    all_event_classes = get_all_events()
    event_groups = group_events_by_category(event_classes=all_event_classes)

    rendered_doc = template.render(event_groups=event_groups)

    output_file.parent.mkdir(exist_ok=True, parents=True)
    output_file.write_text(rendered_doc, encoding="utf-8")
    print(f"Docs saved to: {output_file}")
