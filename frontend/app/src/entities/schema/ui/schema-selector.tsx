import { Button, Tooltip } from "@infrahub/ui";
import { useAtomValue } from "jotai";
import { ListChevronsDownUpIcon, ListChevronsUpDown } from "lucide-react";
import { parseAsNativeArrayOf, parseAsString, useQueryState } from "nuqs";
import { useEffect, useRef, useState } from "react";
import * as R from "remeda";

import { Col, Row } from "@/shared/components/container";
import Accordion from "@/shared/components/display/accordion";
import { Icon } from "@/shared/components/display/icon";
import { SearchInput } from "@/shared/components/inputs/search-input";
import { Badge } from "@/shared/components/ui/badge";
import { QSP } from "@/shared/config/qsp";
import { classNames } from "@/shared/utils/common";

import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isGenericSchema } from "@/entities/schema/domain/rules/is-generic-schema";
import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";

interface SchemaSelectorProps {
  className?: string;
}

export function SchemaSelector({ className }: SchemaSelectorProps) {
  const [selectedKind, setKind] = useQueryState(QSP.KIND, parseAsNativeArrayOf(parseAsString));
  const nodes = useAtomValue(nodeSchemasAtom);
  const generics = useAtomValue(genericSchemasAtom);
  const profiles = useAtomValue(profileSchemasAtom);
  const templates = useAtomValue(templateSchemasAtom);
  const [search, setSearch] = useState("");
  const [openByNamespace, setOpenByNamespace] = useState<Record<string, boolean>>({});
  const preSearchStateRef = useRef<Record<string, boolean> | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [selectedKind?.length]);

  const allSchemas: ModelSchema[] = [...nodes, ...generics, ...profiles, ...templates];

  const schemas = allSchemas.filter(({ kind }) =>
    kind?.toLowerCase().includes(search.toLowerCase())
  );

  const schemasPerNamespace = R.pipe(
    schemas,
    R.sortBy((schema) => schema.name),
    R.groupBy((schema) => schema.namespace)
  );

  const visibleNamespaces = Object.keys(schemasPerNamespace);
  const anyOpen = visibleNamespaces.some((ns) => openByNamespace[ns] ?? true);

  const handleSearchChange = (value: string) => {
    const wasSearching = search.length > 0;
    const isNowSearching = value.length > 0;

    if (!wasSearching && isNowSearching) {
      preSearchStateRef.current = openByNamespace;
      const matchingNamespaces = new Set(
        allSchemas
          .filter((s) => s.kind?.toLowerCase().includes(value.toLowerCase()))
          .map((s) => s.namespace)
      );
      setOpenByNamespace((prev) => ({
        ...prev,
        ...Object.fromEntries([...matchingNamespaces].map((ns) => [ns, true])),
      }));
    } else if (wasSearching && !isNowSearching && preSearchStateRef.current) {
      setOpenByNamespace(preSearchStateRef.current);
      preSearchStateRef.current = null;
    }

    setSearch(value);
  };

  const toggleAll = () => {
    preSearchStateRef.current = null;
    const allNamespaces = new Set(allSchemas.map((s) => s.namespace));
    setOpenByNamespace((prev) => ({
      ...prev,
      ...Object.fromEntries([...allNamespaces].map((ns) => [ns, !anyOpen])),
    }));
  };

  return (
    <Col className={classNames("bg-background", className)}>
      <Row className="sticky top-0 z-1 border-b bg-background p-4">
        <SearchInput placeholder="Search schema" value={search} onChange={handleSearchChange} />
        <Tooltip message={anyOpen ? "Collapse all" : "Expand all"}>
          <Button
            shape="square"
            variant="outline"
            className="size-10 rounded-md border-border-strong"
            onPress={toggleAll}
            aria-label={anyOpen ? "Collapse all" : "Expand all"}
          >
            {anyOpen ? (
              <ListChevronsDownUpIcon className="size-4" />
            ) : (
              <ListChevronsUpDown className="size-4" />
            )}
          </Button>
        </Tooltip>
      </Row>

      {Object.entries(schemasPerNamespace).map(([namespace, schemas]) => {
        const open = openByNamespace[namespace] ?? true;

        return (
          <Accordion
            key={namespace}
            title={namespace}
            open={open}
            onOpenChange={(next) => {
              setOpenByNamespace((prev) => ({ ...prev, [namespace]: next }));
            }}
          >
            <div className="divide-y px-4">
              {schemas.map((schema) => {
                const isSelected =
                  selectedKind && schema.kind && selectedKind.includes(schema.kind);
                const isSelectedLast = isSelected && selectedKind.at(-1)?.includes(schema.kind!);

                return (
                  <div
                    ref={isSelectedLast ? scrollRef : undefined}
                    key={schema.kind}
                    className={classNames(
                      "relative flex h-24 cursor-pointer items-center overflow-hidden pr-2 pl-9 hover:rounded-sm hover:bg-highlight",
                      isSelected &&
                        "rounded-sm bg-selected text-selected-foreground shadow-selected ring-1 ring-ring"
                    )}
                    onClick={() => setKind([schema.kind!])}
                  >
                    {schema.icon && (
                      <div className="absolute left-2">
                        <Icon icon={schema.icon} className="text-accent text-xl" />
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

                      <p className="mt-1 pl-1 text-foreground-muted text-xs">
                        {schema.description}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </Accordion>
        );
      })}
    </Col>
  );
}
