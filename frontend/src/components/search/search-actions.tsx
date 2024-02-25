import { useAtomValue } from "jotai/index";
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

  const schemaInMenu = [...schemas, ...generics].filter((s) => s.include_in_menu);
  const results = schemaInMenu.filter(({ name }) =>
    name.toLowerCase().includes(query.toLowerCase())
  );

  if (results.length === 0) return null;

  return (
    <SearchGroup>
      <SearchGroupTitle>GO TO</SearchGroupTitle>

      {results.map((s) => (
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
      <Icon icon="mdi:arrow-right-thin" />
      <span>Objects</span>
      <Icon icon="mdi:chevron-right" />
      <span className="font-medium">{label || name || kind}</span>
      <Icon icon="mdi:chevron-right" />
      <span className="font-semibold text-custom-blue-700">View</span>
    </SearchResultItem>
  );
};
