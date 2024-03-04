import { useAtomValue } from "jotai";
import { genericsState, IModelSchema, schemaState } from "../../state/atoms/schema.atom";
import { classNames, isGeneric } from "../../utils/common";
import { Badge } from "../../components/ui/badge";
import { Icon } from "@iconify-icon/react";

type SchemaSelectorProps = {
  selectedSchema?: IModelSchema;
  onClick: (node: IModelSchema) => void;
  className?: string;
};
export const SchemaSelector = ({
  selectedSchema,
  onClick,
  className = "",
}: SchemaSelectorProps) => {
  const nodeSchemas = useAtomValue(schemaState);
  const genericSchemas = useAtomValue(genericsState);

  return (
    <section className={classNames("space-y-2 max-w-md", className)}>
      {[...nodeSchemas, ...genericSchemas].map((schema) => {
        return (
          <div
            key={schema.id}
            className={`
              p-4 shadow-lg cursor-pointer flex relative pl-10
              bg-custom-white rounded-md border border-gray-200
              ring-custom-blue-600 hover:ring-1 ${
                selectedSchema?.name === schema.name ? "!ring-2 " : ""
              }
            `}
            onClick={() => onClick(schema)}>
            {schema.icon && (
              <div className="absolute left-3">
                <Icon icon={schema.icon} className="text-xl text-custom-blue-700" />
              </div>
            )}
            <div className="flex-grow">
              <h2 className="flex justify-between items-start">
                <div className="flex items-center gap-1">
                  <Badge variant="blue" className="self-baseline">
                    {schema.namespace}
                  </Badge>
                  {schema.label}
                </div>
                <Badge className="self-baseline">{isGeneric(schema) ? "Generic" : "Node"}</Badge>
              </h2>

              <p className="pl-1 text-sm text-gray-600">{schema.description}</p>
            </div>
          </div>
        );
      })}
    </section>
  );
};
