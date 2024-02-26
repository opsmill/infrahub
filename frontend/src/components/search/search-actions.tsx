import { useMemo } from "react";
import { useAtomValue } from "jotai";
import {
  genericsState,
  iGenericSchema,
  iNodeSchema,
  schemaState,
} from "../../state/atoms/schema.atom";
import { Icon } from "@iconify-icon/react";
import { SearchGroup, SearchGroupTitle, SearchResultItem } from "./search-modal";

type SearchProps = {
  query: string;
};
export const SearchActions = ({ query }: SearchProps) => {
  const schemas = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);

  const schemasInMenu = useMemo(() => {
    return [...schemas, ...generics].filter((s) => s.include_in_menu);
  }, [schemas.length, generics.length]);

  const results = schemasInMenu.filter(({ kind, label, name }) =>
    (label || kind || name).toLowerCase().includes(query.toLowerCase())
  );

  if (results.length === 0) return null;

  const firstThreeMatches = results.slice(0, 3);
  return (
    <SearchGroup>
      <SearchGroupTitle>Go to</SearchGroupTitle>

      {firstThreeMatches.map((s) => (
        <ActionResult key={s.id} schema={s} />
      ))}
    </SearchGroup>
  );
};

type ActionResultProps = {
  schema: iNodeSchema | iGenericSchema;
};

const ActionResult = ({ schema }: ActionResultProps) => {
  const { kind, label, name } = schema;

  return (
    <SearchResultItem to={`/objects/${kind}`}>
      <span>Objects</span>
      <Icon icon="mdi:chevron-right" />
      <span className="font-medium">{label || kind || name}</span>
      <Icon icon="mdi:chevron-right" />
      <span className="font-semibold text-custom-blue-700">View</span>
    </SearchResultItem>
  );
};
