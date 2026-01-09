import { Icon } from "@iconify-icon/react";
import { useNavigate } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";

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

      <div className="flex h-14 items-center justify-between p-3">
        <div className="flex shrink-0 items-center justify-between">
          <FilterSearchInput schema={schema} />

          <ActiveObjectFilterTags schema={schema} className="mx-2" />
        </div>

        <div className="flex items-center gap-3">
          <ButtonWithTooltip
            size="sm"
            disabled={!permission.create.isAllowed}
            tooltipEnabled={!permission.create.isAllowed}
            tooltipContent={permission.create.message ?? undefined}
            onClick={() => navigate(constructPath("/proposed-changes/new"))}
            data-testid="add-proposed-changes-button"
          >
            <Icon icon="mdi:plus" className="text-sm" />
            New proposed change
          </ButtonWithTooltip>
        </div>
      </div>
    </>
  );
}
