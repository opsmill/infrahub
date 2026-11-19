import type { Elevation, ElevationItem } from "@/entities/rack-elevation/domain/model/elevation";
import {
  HIDDEN_LABEL,
  type LabelChoices,
  type LabelOption,
} from "@/entities/rack-elevation/domain/model/label-choice";
import type { NodeStore, Schema } from "@/entities/rack-elevation/domain/model/schema";
import { getFacetValues } from "@/entities/rack-elevation/domain/rules/filter-items";

type FieldValues = ReturnType<typeof getFacetValues>;

function pick(choice: string, values: FieldValues): string | null {
  return values[choice]?.value ?? null;
}

export function buildLabelOptions(valuesList: FieldValues[]): LabelOption[] {
  const options = new Map<string, LabelOption>();
  for (const values of valuesList) {
    for (const [key, { label }] of Object.entries(values)) {
      const option = options.get(key) ?? { key, label, count: 0 };
      option.count += 1;
      options.set(key, option);
    }
  }
  return [...options.values()].sort((a, b) => a.label.localeCompare(b.label));
}

/** Replaces the mapped labels with the chosen fields; an object without the field keeps its mapped label. */
export function applyLabelChoices(
  elevation: Elevation,
  choices: LabelChoices,
  store: NodeStore,
  schema: Schema
): Elevation {
  const relabel = (item: ElevationItem): ElevationItem => {
    const values = getFacetValues(item.node, elevation.rack.id, store, schema);
    return {
      ...item,
      label: pick(choices.item, values) ?? item.label,
      subtitle:
        choices.subtitle === HIDDEN_LABEL
          ? null
          : (pick(choices.subtitle, values) ?? item.subtitle),
    };
  };
  const rackValues = getFacetValues(elevation.rack, "", store, schema);

  return {
    ...elevation,
    label: pick(choices.rack, rackValues) ?? elevation.label,
    placed: elevation.placed.map(relabel),
    unplaced: elevation.unplaced.map(relabel),
  };
}

export function getLabelOptions(elevation: Elevation, store: NodeStore, schema: Schema) {
  const items = [...elevation.placed, ...elevation.unplaced];
  return {
    rack: buildLabelOptions([getFacetValues(elevation.rack, "", store, schema)]),
    item: buildLabelOptions(
      items.map((item) => getFacetValues(item.node, elevation.rack.id, store, schema))
    ),
    itemCount: items.length,
  };
}
