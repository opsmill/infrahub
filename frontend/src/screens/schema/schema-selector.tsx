import { useAtomValue } from "jotai";
import * as R from "ramda";
import { genericsState, IModelSchema, schemaState } from "../../state/atoms/schema.atom";
import { classNames, isGeneric } from "../../utils/common";
import { Badge } from "../../components/ui/badge";
import { Icon } from "@iconify-icon/react";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "../../config/qsp";
import Accordion from "../../components/display/accordion";

type SchemaSelectorProps = {
  className?: string;
};
export const SchemaSelector = ({ className = "" }: SchemaSelectorProps) => {
  const [selectedKind, setKind] = useQueryParam(QSP.KIND, StringParam);
  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);
  const schemas: IModelSchema[] = [...nodes, ...generics];
  const schemasPerNamespace = R.pipe(
    R.sortBy<IModelSchema>(R.prop("name")),
    R.groupBy(R.prop("namespace"))
  )(schemas);

  return (
    <section className={classNames("space-y-2 p-4 max-w-md bg-custom-white h-full", className)}>
      {Object.entries(schemasPerNamespace).map(([namespace, schemas]) => {
        return (
          <Accordion key={namespace} title={namespace} defaultOpen>
            <div className="divide-y px-4">
              {schemas.map((schema) => {
                return (
                  <div
                    key={schema.id}
                    className={`
                      pl-9 pr-2 py-6 cursor-pointer flex relative hover:bg-gray-100 mix-blend-multiply
                        ${
                          selectedKind === schema.kind
                            ? "shadow-lg ring-1 ring-custom-blue-600 rounded-md"
                            : ""
                        }
                    `}
                    onClick={() => setKind(schema.kind)}>
                    {schema.icon && (
                      <div className="absolute left-2">
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
                        <Badge className="self-baseline">
                          {isGeneric(schema) ? "Generic" : "Node"}
                        </Badge>
                      </h2>

                      <p className="pl-1 text-sm text-gray-600">{schema.description}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </Accordion>
        );
      })}
    </section>
  );
};
