import { LockIcon } from "lucide-react";
import type React from "react";

import MetaDetailsTooltip from "@/shared/components/display/meta-details-tooltips";
import { classNames } from "@/shared/utils/common";

import type {
  NodeAttributeMetadata,
  NodeRelationshipMetadata,
} from "@/entities/nodes/object/domain/model/node";

interface ObjectFieldMetadataProps {
  metadata: NodeAttributeMetadata | NodeRelationshipMetadata;
  header?: React.ReactNode;
  hoverScope?: "row" | "edge";
}

export function ObjectFieldMetadata({
  metadata,
  header,
  hoverScope = "row",
}: ObjectFieldMetadataProps) {
  return (
    <>
      {metadata.is_protected && <LockIcon className="size-3.5 text-foreground-muted" />}

      <MetaDetailsTooltip
        updatedAt={metadata.updated_at}
        source={metadata.source}
        owner={metadata.owner}
        isProtected={metadata.is_protected}
        header={header}
        triggerClassName={classNames(
          "opacity-0 transition-opacity focus-visible:opacity-100",
          hoverScope === "edge" ? "group-hover/edge:opacity-100" : "group-hover:opacity-100"
        )}
      />
    </>
  );
}
