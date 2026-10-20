import { LinkButton } from "@infrahub/ui";
import { BookTextIcon } from "lucide-react";

import { constructPath } from "@/shared/api/rest/fetch";
import { RefreshButton } from "@/shared/components/buttons/refresh-button";
import { Icon } from "@/shared/components/display/icon";
import { HeaderContainer } from "@/shared/components/layout/header-container";
import { INFRAHUB_DOC_LOCAL } from "@/shared/config/config";

import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

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

      <RefreshButton className="ml-auto" queryKeys={[objectQueryKeys.all]} />
      <LinkButton
        variant="outline"
        size="sm"
        href={constructPath("/schema", [{ name: "kind", value: schema.kind }])}
      >
        <Icon icon="mdi:code-json" />
        Schema
      </LinkButton>
      {schema.documentation && (
        <LinkButton
          variant="outline"
          size="sm"
          href={
            schema.documentation.startsWith("http")
              ? schema.documentation
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
