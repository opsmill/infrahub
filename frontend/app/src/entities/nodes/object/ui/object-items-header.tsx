import { Icon } from "@iconify-icon/react";
import { BookTextIcon } from "lucide-react";

import { constructPath } from "@/shared/api/rest/fetch";
import { LinkButton } from "@/shared/components/ui/button";
import { INFRAHUB_DOC_LOCAL } from "@/shared/config/config";

import { HeaderContainer } from "@/entities/nodes/object/ui/object-details/object-details-header";
import { RefreshButton } from "@/entities/nodes/object/ui/object-details/refresh-button";
import type { ModelSchema } from "@/entities/schema/types";

interface ObjectItemsHeaderProps {
  schema: ModelSchema;
}

export function ObjectItemsHeader({ schema }: ObjectItemsHeaderProps) {
  return (
    <HeaderContainer className="items-start">
      <div>
        <h1 className="truncate font-bold text-xl">{schema.label}</h1>
        <div className="text-sm">{schema.description}</div>
      </div>

      <RefreshButton className="ml-auto" />
      <LinkButton
        variant="outline"
        size="sm"
        to={constructPath("/schema", [{ name: "kind", value: schema.kind }])}
      >
        <Icon icon="mdi:code-json" className="mr-1" />
        Schema
      </LinkButton>
      {schema.documentation && (
        <LinkButton
          variant="outline"
          size="sm"
          to={
            schema.documentation.startsWith("http")
              ? INFRAHUB_DOC_LOCAL
              : INFRAHUB_DOC_LOCAL + schema.documentation
          }
          className="gap-1"
          target="_blank"
          rel="noreferrer"
        >
          <BookTextIcon className="size-3.5" />
          Docs
        </LinkButton>
      )}
    </HeaderContainer>
  );
}
