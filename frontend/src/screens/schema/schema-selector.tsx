import { useAtomValue } from "jotai";
import { iNodeSchema, schemaState } from "../../state/atoms/schema.atom";
import { classNames, pluralize } from "../../utils/common";
import { Badge } from "../../components/ui/badge";

type SchemaSelectorProps = {
  selectedSchema?: iNodeSchema;
  onClick: (node: iNodeSchema) => void;
  className?: string;
};
export const SchemaSelector = ({
  selectedSchema,
  onClick,
  className = "",
}: SchemaSelectorProps) => {
  const nodeSchemas = useAtomValue(schemaState);

  return (
    <section className={classNames("space-y-2 max-w-lg", className)}>
      {nodeSchemas.map((schema) => {
        return (
          <div
            key={schema.id}
            className={`
              p-4 shadow-lg cursor-pointer
              bg-custom-white rounded-md border border-gray-200
              ring-custom-blue-600 hover:ring-1 ${
                selectedSchema?.name === schema.name ? "!ring-2 " : ""
              }
            `}
            onClick={() => onClick(schema)}>
            <h2 className="flex items-center gap-1">
              <Badge variant="blue" className="self-baseline">
                {schema.namespace}
              </Badge>
              {schema.label}
            </h2>

            <p className="pl-1 text-sm text-gray-600">
              {pluralize(schema.attributes?.length!, "attribute")},{" "}
              {pluralize(schema.relationships?.length!, "relationship")}
            </p>
          </div>
        );
      })}
    </section>
  );
};
