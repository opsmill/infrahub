import { Button, Menu, MenuItem, MenuSection, MenuTrigger, Popover } from "@infrahub/ui";
import { BookTextIcon, EllipsisVertical } from "lucide-react";

import TasksStatusIcon from "@/assets/icons/tasks-status.svg?react";

import { constructPath } from "@/shared/api/rest/fetch";
import { Icon } from "@/shared/components/display/icon";
import { CopyToClipboardMenuItem } from "@/shared/components/menu/copy-to-clipboard-menu-item";

import type { ArtifactObject } from "@/entities/artifacts/domain/model/artifact";
import { ARTIFACT_OBJECT } from "@/entities/artifacts/domain/model/artifact";
import {
  getDocumentationUrl,
  getObjectGraphqlSandboxUrl,
  getObjectTasksUrl,
} from "@/entities/nodes/object/ui/routing/object-urls";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface ArtifactDetailsMenuProps {
  artifact: ArtifactObject;
}

export function ArtifactDetailsMenu({ artifact }: ArtifactDetailsMenuProps) {
  const { schema } = useSchema(ARTIFACT_OBJECT);
  return (
    <MenuTrigger>
      <Button variant="ghost" size="sm" shape="square" data-testid="object-details-menu">
        <EllipsisVertical className="size-4" />
      </Button>

      <Popover placement="bottom end">
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
            <MenuItem href={getObjectTasksUrl(artifact.id)}>
              <TasksStatusIcon width="12" height="12" className="ml-0.5" />
              Tasks
            </MenuItem>
            <MenuItem
              href={constructPath("/schema", [{ name: "kind", value: artifact.__typename }])}
            >
              <Icon icon="mdi:code-json" />
              View Schema
            </MenuItem>
            <MenuItem href={getObjectGraphqlSandboxUrl(artifact.__typename, artifact.id)}>
              <Icon icon="mdi:graphql" />
              GraphQL sandbox
            </MenuItem>
            {schema?.documentation && (
              <MenuItem
                href={getDocumentationUrl(schema.documentation)}
                target="_blank"
                rel="noreferrer"
              >
                <BookTextIcon />
                Documentation
              </MenuItem>
            )}
          </MenuSection>
        </Menu>
      </Popover>
    </MenuTrigger>
  );
}
