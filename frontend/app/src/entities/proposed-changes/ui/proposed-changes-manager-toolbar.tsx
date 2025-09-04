import { Icon } from "@iconify-icon/react";
import { useNavigate } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";

import { ActiveObjectFilterTags } from "@/entities/nodes/object/ui/filters/active-object-filter-tags";
import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";
import ObjectHeader from "@/entities/nodes/object-header";
import { Permission } from "@/entities/permission/types";
import { ModelSchema } from "@/entities/schema/types";

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
      <ObjectHeader schema={schema} />

      <div className="flex items-center h-14 px-3 justify-between">
        <div className="flex items-center shrink-0 justify-between">
          <FilterSearchInput schema={schema} />

          <ActiveObjectFilterTags schema={schema} className="mx-2" />
        </div>

        <div className="flex gap-3 items-center">
          <ButtonWithTooltip
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
