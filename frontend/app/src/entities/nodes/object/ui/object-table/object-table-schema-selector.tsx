import { QSP } from "@/config/qsp";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { ModelSchema } from "@/entities/schema/types";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";
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
import { Icon } from "@iconify-icon/react";
import React from "react";
import { StringParam, useQueryParam } from "use-query-params";

export function ObjectTableSchemaSelector() {
  const [isOpen, setIsOpen] = React.useState(false);
  const [_kind, setKindInQsp] = useQueryParam(QSP.KIND, StringParam);
  const { filters, setFilters, baseSchema, selectedSchema } = useObjectTableContext();

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
        className="w-auto min-h-8 py-0 whitespace-nowrap"
        data-testid="object-schema-schema-selector"
      >
        <RenderItem schema={selectedSchema ?? baseSchema} />
      </ComboboxTrigger>

      <ComboboxContent portal fitTriggerWidth={false}>
        <ComboboxList>
          <ComboboxItem
            value={baseSchema.hash}
            selectedValue={selectedSchema.hash}
            onSelect={() => {
              setKindInQsp(undefined);
              setFilters(removeFiltersNotInSchema(filters, baseSchema));
              setIsOpen(false);
            }}
          >
            <RenderItem schema={baseSchema} />
          </ComboboxItem>
          {items.map((schema) => {
            return (
              <ComboboxItem
                key={schema.hash}
                value={schema.hash}
                selectedValue={selectedSchema?.hash}
                onSelect={() => {
                  setKindInQsp(schema.kind);
                  setFilters(removeFiltersNotInSchema(filters, schema));
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
