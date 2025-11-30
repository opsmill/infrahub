import { keepPreviousData } from "@tanstack/react-query";
import { useLocation, useParams } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbItemError,
  BreadcrumbItemLoading,
  Breadcrumbs,
} from "@/shared/components/aria/breadcrumbs";
import { MenuTrigger } from "@/shared/components/aria/menu";
import { Popover } from "@/shared/components/aria/popover";
import { PROPOSED_CHANGES_OBJECT } from "@/shared/config/constants";

import { BreadcrumbSelectorTrigger } from "@/entities/breadcrumbs/ui/items/breadcrumb-selector-trigger";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { ObjectAutocomplete } from "@/entities/nodes/object/ui/object-autocomplete";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function BreadcrumbProposedChanges() {
  const { proposedChangeId } = useParams();
  const { pathname } = useLocation();
  const isNewPage = pathname.endsWith("/new");

  return (
    <Breadcrumbs data-testid="breadcrumb-proposed-changes">
      <BreadcrumbItem href={constructPath("/proposed-changes")}>Proposed changes</BreadcrumbItem>
      {isNewPage && (
        <BreadcrumbItem href={constructPath("/proposed-changes/new")}>new</BreadcrumbItem>
      )}
      {proposedChangeId && <BreadcrumbProposedChangeSelector proposedChangeId={proposedChangeId} />}
    </Breadcrumbs>
  );
}

function BreadcrumbProposedChangeSelector({ proposedChangeId }: { proposedChangeId: string }) {
  const { schema } = useSchema(PROPOSED_CHANGES_OBJECT);
  const { data, isPending, error } = useGetObject(
    {
      objectSchema: schema!,
      objectId: proposedChangeId,
    },
    {
      placeholderData: keepPreviousData,
      enabled: !!schema,
    }
  );

  if (isPending || !schema) {
    return <BreadcrumbItemLoading />;
  }

  if (error) {
    return <BreadcrumbItemError error={error} />;
  }

  return (
    <Breadcrumb>
      <MenuTrigger>
        <BreadcrumbSelectorTrigger>{getNodeLabel(data)}</BreadcrumbSelectorTrigger>

        <Popover className="bg-stone-100/50 backdrop-blur">
          <ObjectAutocomplete className="max-h-58" objectKind={PROPOSED_CHANGES_OBJECT} />
        </Popover>
      </MenuTrigger>
    </Breadcrumb>
  );
}
