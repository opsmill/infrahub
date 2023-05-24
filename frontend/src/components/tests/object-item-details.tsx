import { useAtom } from "jotai";
import { useParams } from "react-router-dom";
import { getObjectDetails } from "../../graphql/queries/objects/getObjectDetails";
import { schemaState } from "../../state/atoms/schema.atom";

export default function ObjectItemDetails() {
  const { objectname, objectid } = useParams();
  const [schemaList] = useAtom(schemaState);
  const schema = schemaList.filter((s) => s.name === objectname)[0];

  const relationships = schema?.relationships?.filter(
    (relationship) =>
      relationship.cardinality === "one" ||
      relationship.kind === "Attribute" ||
      relationship.kind === "Parent"
  );

  const queryString = getObjectDetails({
    ...schema,
    relationships,
    objectid,
  });

  return (
    <div>
      <div>Relationships: {JSON.stringify(relationships)}</div>
      <div>Query: {JSON.stringify(queryString)}</div>
    </div>
  );
}
