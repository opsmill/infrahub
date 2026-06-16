import { Icon } from "@iconify-icon/react";
import { Button, Tooltip } from "@infrahub/ui";
import { useNavigate } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Row } from "@/shared/components/container";

import { ActiveObjectFilterTags } from "@/entities/nodes/object/ui/filters/active-object-filter-tags";
import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";
import { ObjectItemsHeader } from "@/entities/nodes/object/ui/object-items-header";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

export interface ProposedChangesManagerToolbarProps {
  schema: ModelSchema;
  permission: Permission;
}

export function ProposedChangesManagerToolbar({
  schema,
  permission,
}: ProposedChangesManagerToolbarProps) {
  const navigate = useNavigate();

  return (
    <>
      <ObjectItemsHeader schema={schema} />

      <Row className="p-2">
        <FilterSearchInput schema={schema} />

        <ActiveObjectFilterTags schema={schema} className="p-0" />

        <Tooltip
          message={
            !permission.create.isAllowed ? (permission.create.message ?? undefined) : undefined
          }
        >
          <Button
            size="sm"
            isDisabledAndFocusable={!permission.create.isAllowed}
            onPress={() => navigate(constructPath("/proposed-changes/new"))}
            data-testid="add-proposed-changes-button"
            className="ml-auto"
          >
            <Icon icon="mdi:plus" className="text-sm" />
            New proposed change
          </Button>
        </Tooltip>
      </Row>
    </>
  );
}
