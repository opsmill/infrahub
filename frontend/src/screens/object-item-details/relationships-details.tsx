import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "../../config/qsp";
import getObjectRelationshipsDetails from "../../graphql/queries/objects/objectRelationshipDetails";
import { branchState } from "../../state/atoms/branch.atom";
import { genericsState, iNodeSchema, schemaState } from "../../state/atoms/schema.atom";
import { timeState } from "../../state/atoms/time.atom";
import RelationshipDetails from "./relationship-details";

interface Props {
  parentNode: any;
  parentSchema: iNodeSchema;
}

export default function RelationshipsDetails(props: Props) {
  const { objectname, objectid } = useParams();
  const [qspTab] = useQueryParam(QSP.TAB, StringParam);

  const [schemaList] = useAtom(schemaState);
  const [generics] = useAtom(genericsState);
  const schema = schemaList.filter((s) => s.name === objectname)[0];
  const relationshipSchema = schema?.relationships?.find((r) => r?.name === qspTab);
  const [date] = useAtom(timeState);
  const [branch] = useAtom(branchState);

  const [
    ,
    // isLoading
    setIsLoading,
  ] = useState(true);
  const [
    ,
    // hasError
    setHasError,
  ] = useState(false);
  const [relationships, setRelationships] = useState();

  const fetchRelationshipDetails = useCallback(async () => {
    setRelationships(undefined);
    try {
      if (!qspTab) {
        return;
      }

      setIsLoading(true);

      const data = await getObjectRelationshipsDetails(
        schema,
        schemaList,
        generics,
        objectid!,
        qspTab
      );

      setRelationships(data);
    } catch (err) {
      setHasError(true);
    }

    setIsLoading(false);
  }, [objectid, schema, qspTab, generics, schemaList]);

  useEffect(() => {
    if (schema) {
      fetchRelationshipDetails();
    }
  }, [fetchRelationshipDetails, schema, date, branch]);

  if (!qspTab) {
    return null;
  }

  return (
    <div className="border-t border-gray-200 px-4 py-5 sm:p-0 flex flex-col flex-1 overflow-auto">
      <RelationshipDetails
        parentNode={props.parentNode}
        mode="TABLE"
        parentSchema={props.parentSchema}
        relationshipsData={relationships}
        relationshipSchema={relationshipSchema}
      />
    </div>
  );
}
