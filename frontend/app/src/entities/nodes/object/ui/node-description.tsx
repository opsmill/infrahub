import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { NodeCore } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { InputHTMLAttributes } from "react";
import { Link } from "react-router";

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
        className="text-custom-blue-800 font-medium hover:underline"
      >
        {getNodeLabel(node)}
      </Link>
    </div>
  );
}
