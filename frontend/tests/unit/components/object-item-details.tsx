import { useAtom } from "jotai";
import { useParams } from "react-router-dom";
import { getObjectDetailsPaginated } from "../../../src/graphql/queries/objects/getObjectDetails";
import { schemaState } from "../../../src/state/atoms/schema.atom";
import { cleanTabsAndNewLines } from "../../../src/utils/string";

export default function ObjectItemDetails() {
  const { objectname, objectid } = useParams();
  const [schemaList] = useAtom(schemaState);
  const schema = schemaList.find((s) => s.kind === objectname);

  const relationships = schema?.relationships?.filter(
    (relationship) =>
      relationship.cardinality === "one" ||
      relationship.kind === "Attribute" ||
      relationship.kind === "Parent"
  );

  const queryString = getObjectDetailsPaginated({
    ...schema,
    relationships,
    objectid,
  });

  return (
    <div>
      <div>Query: {cleanTabsAndNewLines(queryString)}</div>
    </div>
  );
}
