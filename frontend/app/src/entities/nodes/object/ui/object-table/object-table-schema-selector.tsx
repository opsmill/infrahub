import { Icon } from "@iconify-icon/react";
import { parseAsJson, parseAsString, useQueryStates } from "nuqs";
import React from "react";

import { QSP } from "@/config/qsp";

import { Row } from "@/shared/components/container";
import { removeFiltersNotInSchema } from "@/shared/components/filters/utils/remove-filters-not-in-schema";
import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import { FilterSchema } from "@/shared/hooks/useFilters";

import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { getSchema } from "@/entities/schema/domain/get-schema";
import type { ModelSchema } from "@/entities/schema/types";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";

export function ObjectTableSchemaSelector() {
  const [isOpen, setIsOpen] = React.useState(false);
  const [{ filters }, setObjectTableQueryParams] = useQueryStates(
    {
      [QSP.KIND]: parseAsString,
      [QSP.FILTER]: parseAsJson(FilterSchema).withDefault([]),
    },
    { history: "push" }
  );

  const { baseSchema, selectedSchema } = useObjectTableContext();
  const items = React.useMemo<ModelSchema[]>(() => {
    if (!isGenericSchema(baseSchema)) return [];
    const inheritingKind = baseSchema.used_by ?? [];

    return inheritingKind
      .map((kind) => {
        const { schema } = getSchema(kind);
        return schema;
      })
      .filter((n) => !!n);
  }, [baseSchema.hash]);

  return (
    <Combobox open={isOpen} onOpenChange={setIsOpen}>
      <ComboboxTrigger
        className="min-h-8 w-auto whitespace-nowrap py-0"
        data-testid="object-schema-schema-selector"
      >
        <RenderItem schema={selectedSchema ?? baseSchema} />
      </ComboboxTrigger>

      <ComboboxContent
        portal
        fitTriggerWidth={false}
        data-testid="object-schema-schema-selector-popover"
      >
        <ComboboxList shouldFilter>
          <ComboboxItem
            value={baseSchema.hash}
            selectedValue={selectedSchema.hash}
            onSelect={() => {
              const pruned = removeFiltersNotInSchema(filters, baseSchema);
              setObjectTableQueryParams({
                kind: null,
                filters: pruned,
              });
              setIsOpen(false);
            }}
          >
            <RenderItem schema={baseSchema} />
          </ComboboxItem>
          {items.map((schema) => {
            return (
              <ComboboxItem
                keywords={[schema.label!, schema.kind!]}
                key={schema.hash}
                value={schema.hash}
                selectedValue={selectedSchema.hash}
                onSelect={() => {
                  const pruned = removeFiltersNotInSchema(filters, schema);
                  setObjectTableQueryParams({
                    kind: schema.kind,
                    filters: pruned,
                  });
                  setIsOpen(false);
                }}
              >
                <RenderItem schema={schema} />
              </ComboboxItem>
            );
          })}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}

export function RenderItem({ schema }: { schema: ModelSchema }) {
  return (
    <Row className="w-full">
      <Icon icon={getSchemaIcon(schema)} />
      {isGenericSchema(schema) ? (
        <span>All {schema.label}</span>
      ) : (
        <>
          <span>{schema.label}</span>
          <Badge className="ml-auto font-medium">{schema.namespace}</Badge>
        </>
      )}
    </Row>
  );
}
