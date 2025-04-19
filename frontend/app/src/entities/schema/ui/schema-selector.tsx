import { QSP } from "@/config/qsp";
import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";
import { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";
import Accordion from "@/shared/components/display/accordion";
import { Badge } from "@/shared/components/ui/badge";
import { SearchInput } from "@/shared/components/ui/search-input";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import * as R from "ramda";
import { useEffect, useRef, useState } from "react";
import { ArrayParam, useQueryParam } from "use-query-params";

type SchemaSelectorProps = {
  className?: string;
};
export const SchemaSelector = ({ className = "" }: SchemaSelectorProps) => {
  const [selectedKind, setKind] = useQueryParam(QSP.KIND, ArrayParam);
  const nodes = useAtomValue(nodeSchemasAtom);
  const generics = useAtomValue(genericSchemasAtom);
  const profiles = useAtomValue(profileSchemasAtom);
  const templates = useAtomValue(templateSchemasAtom);
  const [search, setSearch] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;

    ref.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [selectedKind?.length]);

  const schemas: ModelSchema[] = [...nodes, ...generics, ...profiles, ...templates].filter(
    ({ kind }) => kind?.toLowerCase().includes(search.toLowerCase())
  );

  const schemasPerNamespace = R.pipe(
    R.sortBy<ModelSchema>(R.prop("name")),
    R.groupBy(R.prop("namespace"))
  )(schemas);

  return (
    <section className={classNames("space-y-2 p-4 bg-white", className)}>
      <SearchInput
        className="mb-4"
        placeholder="Search schema"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      {Object.entries(schemasPerNamespace).map(([namespace, schemas]) => {
        return (
          <Accordion key={namespace} title={namespace} defaultOpen>
            <div className="divide-y divide-gray-200 px-4">
              {schemas.map((schema) => {
                const isSelected =
                  selectedKind && schema.kind && selectedKind.includes(schema.kind);
                const isSelectedLast =
                  isSelected && selectedKind[selectedKind.length - 1]?.includes(schema.kind!);

                return (
                  <div
                    {...(isSelectedLast && { ref })}
                    key={schema.kind}
                    className={`
                      h-24 overflow-hidden pl-9 pr-2 cursor-pointer flex items-center relative hover:bg-gray-100 mix-blend-multiply
                      hover:rounded-sm
                        ${isSelected ? "shadow-lg ring-1 ring-custom-blue-600 rounded-sm" : ""}
                    `}
                    onClick={() => setKind([schema.kind!])}
                  >
                    {schema.icon && (
                      <div className="absolute left-2">
                        <Icon icon={schema.icon} className="text-xl text-custom-blue-700" />
                      </div>
                    )}
                    <div className="grow">
                      <h2 className="flex justify-between items-start">
                        <div className="flex items-center gap-1">
                          <Badge variant="blue" className="self-baseline">
                            {schema.namespace}
                          </Badge>
                          {schema.label}
                        </div>
                        <Badge className="self-baseline">
                          {isGenericSchema(schema) ? "Generic" : "Node"}
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
