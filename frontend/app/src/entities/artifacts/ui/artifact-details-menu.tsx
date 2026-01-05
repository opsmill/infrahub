import { Icon } from "@iconify-icon/react";
import { jsonToGraphQLQuery } from "json-to-graphql-query";
import { BookTextIcon, EllipsisVertical } from "lucide-react";
import { Pressable } from "react-aria-components";

import TasksStatusIcon from "@/assets/icons/tasks-status.svg?react";

import { constructPath } from "@/shared/api/rest/fetch";
import {
  CopyToClipboardMenuItem,
  Menu,
  MenuItem,
  MenuPopover,
  MenuSection,
  MenuTrigger,
} from "@/shared/components/aria/menu";
import { Button } from "@/shared/components/buttons/button-primitive";
import { INFRAHUB_DOC_LOCAL } from "@/shared/config/config";
import { ARTIFACT_OBJECT } from "@/shared/config/constants";
import { QSP } from "@/shared/config/qsp";

import type { ArtifactObject } from "@/entities/artifacts/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface ArtifactDetailsMenuProps {
  artifact: ArtifactObject;
}

export function ArtifactDetailsMenu({ artifact }: ArtifactDetailsMenuProps) {
  const { schema } = useSchema(ARTIFACT_OBJECT);
  return (
    <MenuTrigger>
      <Pressable>
        <Button variant="ghost" size="square" data-testid="object-details-menu">
          <EllipsisVertical className="size-4" />
        </Button>
      </Pressable>

      <MenuPopover placement="bottom end">
        <Menu>
          <MenuSection title="Actions">
            <CopyToClipboardMenuItem textToCopy={artifact.id}>Copy ID</CopyToClipboardMenuItem>
            {artifact.hfid && (
              <CopyToClipboardMenuItem textToCopy={artifact.hfid.toString()}>
                Copy HFID
              </CopyToClipboardMenuItem>
            )}
            {artifact?.checksum?.value && (
              <CopyToClipboardMenuItem textToCopy={artifact?.checksum?.value}>
                Copy Checksum
              </CopyToClipboardMenuItem>
            )}

            {artifact?.storage_id?.value && (
              <CopyToClipboardMenuItem textToCopy={artifact?.storage_id?.value}>
                Copy Storage ID
              </CopyToClipboardMenuItem>
            )}
          </MenuSection>
          <MenuSection title="Go to">
            <MenuItem
              href={constructPath(
                `/tasks?${QSP.FILTER}=[{"name":"node__value","value":"${artifact.id}"}]`
              )}
            >
              <TasksStatusIcon width="12" height="12" className="ml-0.5" />
              Tasks
            </MenuItem>
            <MenuItem
              href={constructPath("/schema", [{ name: "kind", value: artifact.__typename }])}
            >
              <Icon icon="mdi:code-json" />
              View Schema
            </MenuItem>
            <MenuItem
              href={constructPath("/graphql", [
                {
                  name: "query",
                  value: jsonToGraphQLQuery(
                    {
                      query: {
                        [artifact.__typename]: {
                          __args: {
                            ids: [artifact.id],
                          },
                          edges: {
                            node: {
                              id: true,
                              hfid: true,
                              display_label: true,
                            },
                          },
                        },
                      },
                    },
                    {
                      pretty: true,
                    }
                  ),
                },
              ])}
            >
              <Icon icon="mdi:graphql" />
              GraphQL sandbox
            </MenuItem>
            {schema?.documentation && (
              <MenuItem
                href={
                  schema.documentation.startsWith("http")
                    ? schema.documentation
                    : `${INFRAHUB_DOC_LOCAL}${schema.documentation}`
                }
                target="_blank"
                rel="noreferrer"
              >
                <BookTextIcon className="size-3.5" />
                Documentation
              </MenuItem>
            )}
          </MenuSection>
        </Menu>
      </MenuPopover>
    </MenuTrigger>
  );
}
