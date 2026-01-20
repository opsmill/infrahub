import { Icon } from "@iconify-icon/react";
import { Focusable } from "react-aria-components";

import { Tooltip } from "@/shared/components/aria/tooltip";
import { Col } from "@/shared/components/container";
import { Badge } from "@/shared/components/ui/badge";
import { Link } from "@/shared/components/ui/link";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeCore } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function ProfileSourceIcon({ source }: { source?: NodeCore | null }) {
  const { isProfile } = useSchema(source?.__typename);

  if (!isProfile || !source) {
    return <span className="size-3.5 shrink-0" />;
  }

  return (
    <Tooltip
      message={
        <Col className="max-w-60 gap-1">
          <p>This value is set by profile:</p>
          <Link to={getObjectDetailsUrl(source.__typename, source.id)} className="flex">
            <Badge variant="green" className="overflow-hidden font-normal hover:underline">
              <Icon icon="mdi:shape-plus-outline" className="mr-1 shrink-0" />
              <div className="truncate">{getNodeLabel(source)}</div>
            </Badge>
          </Link>
        </Col>
      }
    >
      <Focusable excludeFromTabOrder>
        <Icon
          icon="mdi:shape-plus-outline"
          className="size-3.5 shrink-0 text-green-600"
          role="img"
          aria-label="profile icon"
        />
      </Focusable>
    </Tooltip>
  );
}
