import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { parseAsNativeArrayOf, parseAsString, useQueryState } from "nuqs";
import { useEffect, useRef, useState } from "react";
import * as R from "remeda";

import { QSP } from "@/config/qsp";

import Accordion from "@/shared/components/display/accordion";
import { Badge } from "@/shared/components/ui/badge";
import { SearchInput } from "@/shared/components/ui/search-input";
import { classNames } from "@/shared/utils/common";

import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";
import type { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";

type SchemaSelectorProps = {
  className?: string;
};
export const SchemaSelector = ({ className = "" }: SchemaSelectorProps) => {
  const [selectedKind, setKind] = useQueryState(QSP.KIND, parseAsNativeArrayOf(parseAsString));
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
    schemas,
    R.sortBy((schema) => schema.name),
    R.groupBy((schema) => schema.namespace)
  );

  return (
    <section className={classNames("space-y-2 bg-white p-4", className)}>
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
                const isSelectedLast = isSelected && selectedKind.at(-1)?.includes(schema.kind!);

                return (
                  <div
                    {...(isSelectedLast && { ref })}
                    key={schema.kind}
                    className={`relative flex h-24 cursor-pointer items-center overflow-hidden pr-2 pl-9 mix-blend-multiply hover:rounded-sm hover:bg-gray-100 ${isSelected ? "rounded-sm shadow-lg ring-1 ring-custom-blue-600" : ""}
                    `}
                    onClick={() => setKind([schema.kind!])}
                  >
                    {schema.icon && (
                      <div className="absolute left-2">
                        <Icon icon={schema.icon} className="text-custom-blue-700 text-xl" />
                      </div>
                    )}
                    <div className="grow">
                      <h2 className="flex items-start justify-between">
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

                      <p className="mt-1 pl-1 text-gray-600 text-xs">{schema.description}</p>
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
