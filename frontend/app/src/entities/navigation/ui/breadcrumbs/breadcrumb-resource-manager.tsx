import { ChevronsUpDownIcon } from "lucide-react";
import { Pressable } from "react-aria-components";
import { Link, useParams } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Autocomplete } from "@/shared/components/aria/autocomplete";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbItemError,
  BreadcrumbItemLoading,
  Breadcrumbs,
} from "@/shared/components/aria/breadcrumbs";
import { ListBox, ListBoxItem } from "@/shared/components/aria/list-box";
import { MenuTrigger } from "@/shared/components/aria/menu";
import { Popover, PopoverDialog } from "@/shared/components/aria/popover";
import { Button } from "@/shared/components/buttons/button-primitive";
import { Col, Row } from "@/shared/components/container";

import { BreadcrumbObjectDetails } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-object-details";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
import { useGetPoolUtilization } from "@/entities/resource-manager/domain/get-pool-utilization.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function BreadcrumbResourceManager() {
  const { resourcePoolId, resourceId } = useParams();
  const { schema } = useSchema(RESOURCE_GENERIC_KIND);

  return (
    <Breadcrumbs data-testid="breadcrumb-resource-manager">
      <BreadcrumbItem href={constructPath("/resource-manager")}>Resource manager</BreadcrumbItem>
      {schema && resourcePoolId && (
        <BreadcrumbObjectDetails
          objectSchema={schema}
          objectId={resourcePoolId}
          autocompleteObjectKind={schema.kind!}
        />
      )}
      {resourceId && resourcePoolId && (
        <ResourceSelector resourceId={resourceId} resourcePoolId={resourcePoolId} />
      )}
    </Breadcrumbs>
  );
}

function ResourceSelector({
  resourceId,
  resourcePoolId,
}: {
  resourceId: string;
  resourcePoolId: string;
}) {
  const { data, isPending, error } = useGetPoolUtilization(
    { poolId: resourcePoolId },
    { enabled: false } // to get cached data from details page
  );

  if (isPending) {
    return <BreadcrumbItemLoading />;
  }

  if (error) {
    return <BreadcrumbItemError error={error} />;
  }

  const resources = data.edges.map(({ node }) => node);
  const currentResource = resources.find((resource) => resource.id === resourceId);

  if (!currentResource) return null;

  return (
    <Breadcrumb>
      <Row className="items-end gap-0.5 pr-1 pl-2">
        <Col className="gap-0 py-0.5">
          <div className="truncate text-neutral-600 text-xs leading-3.5">Resources</div>

          <Link
            to={constructPath(`/resource-manager/${resourcePoolId}/resources/${resourceId}`)}
            className="truncate font-medium text-sm leading-4 hover:underline"
          >
            {currentResource.display_label}
          </Link>
        </Col>

        <MenuTrigger>
          <Pressable>
            <Button variant="ghost" className="size-5 p-0" aria-label="Select a different resource">
              <ChevronsUpDownIcon className="size-3.5" />
            </Button>
          </Pressable>

          <Popover className="bg-stone-100/50 backdrop-blur">
            <PopoverDialog>
              {({ close }) => (
                <Autocomplete>
                  <ListBox items={resources} onAction={close}>
                    {(resource) => (
                      <ListBoxItem
                        href={constructPath(
                          `/resource-manager/${resourcePoolId}/resources/${resource.id}`
                        )}
                      >
                        {resource.display_label}
                      </ListBoxItem>
                    )}
                  </ListBox>
                </Autocomplete>
              )}
            </PopoverDialog>
          </Popover>
        </MenuTrigger>
      </Row>
    </Breadcrumb>
  );
}
