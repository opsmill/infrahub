import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "../../config/constants";
import getObjectRelationshipDetails from "../../graphql/queries/objects/objectRelationshipDetails";
import { branchState } from "../../state/atoms/branch.atom";
import { iNodeSchema, schemaState } from "../../state/atoms/schema.atom";
import { timeState } from "../../state/atoms/time.atom";
import RelationshipDetails from "./relationship-details";

interface Props {
  parentSchema: iNodeSchema;
  refreshObject: Function;
}

export default function RelationshipsDetails(props: Props) {
  const { objectname, objectid } = useParams();
  const [qspTab] = useQueryParam(QSP.TAB, StringParam);

  const [schemaList] = useAtom(schemaState);
  const schema = schemaList.filter((s) => s.name === objectname)[0];
  const relationshipSchema = schema?.relationships?.find((r) => r?.name === qspTab);
  const [date] = useAtom(timeState);
  const [branch] = useAtom(branchState);

  const [
    // isLoading
    ,setIsLoading
  ] = useState(true);
  const [
    // hasError
    ,setHasError
  ] = useState(false);
  const [relationships, setRelationships] = useState([]);

  const fetchRelationshipDetails = useCallback(
    async () => {
      try {
        if (!qspTab) {
          return;
        }

        setIsLoading(true);

        const data = await getObjectRelationshipDetails(schema, objectid!, qspTab);

        setRelationships(data);
      } catch(err) {
        setHasError(true);
      }

      setIsLoading(false);
    },
    [objectid, schema, qspTab]
  );

  useEffect(
    () => {
      if(schema) {
        fetchRelationshipDetails();
      }
    },
    [fetchRelationshipDetails, schema, date, branch]
  );

  if (!qspTab) {
    return null;
  }

  return (
    <div className="border-t border-gray-200 flex-1 flex">
      <RelationshipDetails parentSchema={schema} refreshObject={props.refreshObject} relationshipsData={relationships} relationshipSchema={relationshipSchema} />
    </div>
  );
};