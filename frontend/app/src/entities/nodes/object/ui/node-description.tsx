import { Icon } from "@iconify-icon/react";
import type { InputHTMLAttributes } from "react";
import { Link } from "react-router";

import { classNames } from "@/shared/utils/common";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeCore } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";

export interface ObjectInlineDisplayProps extends InputHTMLAttributes<HTMLDivElement> {
  node: NodeCore;
}

export function NodeDescription({ node, className, ...props }: ObjectInlineDisplayProps) {
  const { schema } = useSchema(node.__typename);
  const schemaLabel = schema?.label ?? schema?.name ?? node.__typename;

  return (
    <div className={classNames("flex flex-col text-sm", className)} {...props}>
      <div className="flex items-center gap-1">
        <Icon icon={getSchemaIcon(schema)} className="text-gray-400 text-xs" />
        {schemaLabel}
      </div>

      <Link
        to={getObjectDetailsUrl(node.__typename, node.id)}
        className="font-medium text-custom-blue-800 hover:underline dark:text-custom-blue-400"
      >
        {getNodeLabel(node)}
      </Link>
    </div>
  );
}
