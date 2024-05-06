import { useAtomValue } from "jotai";
import * as R from "ramda";
import {
  genericsState,
  IModelSchema,
  profilesAtom,
  schemaState,
} from "../../state/atoms/schema.atom";
import { classNames, isGeneric } from "../../utils/common";
import { Badge } from "../../components/ui/badge";
import { Icon } from "@iconify-icon/react";
import { ArrayParam, useQueryParam } from "use-query-params";
import { QSP } from "../../config/qsp";
import Accordion from "../../components/display/accordion";
import { useEffect, useRef } from "react";

type SchemaSelectorProps = {
  className?: string;
};
export const SchemaSelector = ({ className = "" }: SchemaSelectorProps) => {
  const [selectedKind, setKind] = useQueryParam(QSP.KIND, ArrayParam);
  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);
  const profiles = useAtomValue(profilesAtom);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;

    ref.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [selectedKind?.length]);

  const schemas: IModelSchema[] = [...nodes, ...generics, ...profiles];
  const schemasPerNamespace = R.pipe(
    R.sortBy<IModelSchema>(R.prop("name")),
    R.groupBy(R.prop("namespace"))
  )(schemas);

  return (
    <section className={classNames("space-y-2 p-4 bg-custom-white", className)}>
      {Object.entries(schemasPerNamespace).map(([namespace, schemas]) => {
        return (
          <Accordion key={namespace} title={namespace} defaultOpen>
            <div className="divide-y px-4">
              {schemas.map((schema) => {
                const isSelected =
                  selectedKind && schema.kind && selectedKind.includes(schema.kind);
                const isSelectedLast =
                  isSelected && selectedKind[selectedKind.length - 1]?.includes(schema.kind!);

                return (
                  <div
                    {...(isSelectedLast && { ref })}
                    key={schema.id}
                    className={`
                      h-24 overflow-hidden pl-9 pr-2 cursor-pointer flex items-center relative hover:bg-gray-100 mix-blend-multiply
                      hover:rounded
                        ${isSelected ? "shadow-lg ring-1 ring-custom-blue-600 rounded" : ""}
                    `}
                    onClick={() => setKind([schema.kind!])}>
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

                      <p className="pl-1 text-xs text-gray-600 mt-1">{schema.description}</p>
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
