import ObjectHeader from "@/entities/nodes/object-header";
import { ActiveFilterTags } from "@/entities/nodes/object/ui/filters/active-filter-tags";
import { FilterResetButton } from "@/entities/nodes/object/ui/filters/filter-reset-button";
import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";
import { Permission } from "@/entities/permission/types";
import { ModelSchema } from "@/entities/schema/types";
import { constructPath } from "@/shared/api/rest/fetch";
import { ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import useFilters from "@/shared/hooks/useFilters";
import { Icon } from "@iconify-icon/react";
import { useNavigate } from "react-router";

export interface ProposedChangesManagerToolbarProps {
  schema: ModelSchema;
  permission: Permission;
}

export function ProposedChangesManagerToolbar({
  schema,
  permission,
}: ProposedChangesManagerToolbarProps) {
  const navigate = useNavigate();
  const [filters] = useFilters();

  return (
    <>
      <ObjectHeader schema={schema} />

      <div className="flex items-center h-14 px-3 justify-between">
        <div className="flex items-center shrink-0 justify-between">
          <FilterSearchInput schema={schema} />

          {filters.length > 0 && (
            <>
              <ScrollArea scrollX>
                <ActiveFilterTags schema={schema} className="mx-2" />
              </ScrollArea>
              <FilterResetButton />
            </>
          )}
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
