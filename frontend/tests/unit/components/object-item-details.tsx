import { useAtom } from "jotai";
import { useParams } from "react-router-dom";
import { getObjectDetailsPaginated } from "../../../src/graphql/queries/objects/getObjectDetails";
import { schemaState } from "../../../src/state/atoms/schema.atom";
import { getSchemaObjectColumns } from "../../../src/utils/getSchemaObjectColumns";
import { cleanTabsAndNewLines } from "../../../src/utils/string";

export default function ObjectItemDetails() {
  const { objectname, objectid } = useParams();
  const [schemaList] = useAtom(schemaState);
  const schema = schemaList.find((s) => s.kind === objectname);

  const columns = getSchemaObjectColumns(schema);

  const queryString = getObjectDetailsPaginated({
    kind: schema?.kind,
    columns,
    objectid,
  });

  return (
    <div>
      <div>Query: {cleanTabsAndNewLines(queryString)}</div>
    </div>
  );
}
