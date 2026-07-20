from __future__ import annotations

from infrahub.core.constants import InfrahubKind
from infrahub.message_bus.types import ProposedChangeArtifactDefinition

GATHER_ARTIFACT_DEFINITIONS = """
query GatherArtifactDefinitions {
  CoreArtifactDefinition {
    edges {
      node {
        id
        name {
          value
        }
        artifact_name {
          value
        }
        content_type {
            value
        }
        targets {
          node {
            id
          }
        }
        transformation {
          node {
            __typename
            timeout {
                value
            }
            dependencies {
              value
            }
            dependencies_complete {
              value
            }
            query {
              node {
                id
                models {
                  value
                }
                name {
                  value
                }
                query {
                  value
                }
              }
            }
            ... on CoreTransformJinja2 {
              template_path {
                value
              }
            }
            ... on CoreTransformPython {
              class_name {
                value
              }
              file_path {
                value
              }
              convert_query_response {
                value
              }
            }
            repository {
              node {
                id
              }
            }
          }
        }
      }
    }
  }
}
"""


def parse_artifact_definitions(definitions: list[dict]) -> list[ProposedChangeArtifactDefinition]:
    """This function assumes that definitions is a list of the edges.

    The edge should be of type CoreArtifactDefinition from the query
    * GATHER_ARTIFACT_DEFINITIONS
    """
    parsed = []
    for definition in definitions:
        transformation = definition["node"]["transformation"]["node"]
        artifact_definition = ProposedChangeArtifactDefinition(
            definition_id=definition["node"]["id"],
            definition_name=definition["node"]["name"]["value"],
            artifact_name=definition["node"]["artifact_name"]["value"],
            content_type=definition["node"]["content_type"]["value"],
            timeout=transformation["timeout"]["value"],
            query_name=transformation["query"]["node"]["name"]["value"],
            query_id=transformation["query"]["node"]["id"],
            query_models=transformation["query"]["node"]["models"]["value"] or [],
            query_payload=transformation["query"]["node"]["query"]["value"],
            repository_id=transformation["repository"]["node"]["id"],
            transform_kind=transformation["__typename"],
            dependencies=transformation["dependencies"]["value"],
            dependencies_complete=transformation["dependencies_complete"]["value"],
        )
        if artifact_definition.transform_kind == InfrahubKind.TRANSFORMJINJA2:
            artifact_definition.template_path = transformation["template_path"]["value"]
        elif artifact_definition.transform_kind == InfrahubKind.TRANSFORMPYTHON:
            artifact_definition.class_name = transformation["class_name"]["value"]
            artifact_definition.file_path = transformation["file_path"]["value"]
            artifact_definition.convert_query_response = transformation["convert_query_response"]["value"]

        parsed.append(artifact_definition)

    return parsed
