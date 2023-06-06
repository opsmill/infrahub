import { gql, useReactiveVar } from "@apollo/client";
import { useState } from "react";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/alert";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { updateObjectWithId } from "../../graphql/mutations/objects/updateObjectWithId";
import { branchVar } from "../../graphql/variables/branchVar";
import { dateVar } from "../../graphql/variables/dateVar";
import { iNodeSchema } from "../../state/atoms/schema.atom";
import { getFormStructureForMetaEdit } from "../../utils/formStructureForCreateEdit";
import { stringifyWithoutQuotes } from "../../utils/string";
import EditFormHookComponent from "../edit-form-hook/edit-form-hook-component";
interface Props {
  row: any;
  schema: iNodeSchema;
  type: "attribute" | "relationship";
  attributeOrRelationshipToEdit: any;
  attributeOrRelationshipName: any;
  schemaList: iNodeSchema[];
  closeDrawer: Function;
  onUpdateComplete: Function;
}

export default function ObjectItemMetaEdit(props: Props) {
  const {
    row,
    type,
    attributeOrRelationshipName,
    schema,
    schemaList,
    attributeOrRelationshipToEdit,
    onUpdateComplete,
  } = props;

  const branch = useReactiveVar(branchVar);
  const date = useReactiveVar(dateVar);
  const [isLoading, setIsLoading] = useState(false);

  const formStructure = getFormStructureForMetaEdit(
    attributeOrRelationshipToEdit,
    type,
    attributeOrRelationshipName,
    schemaList
  );

  async function onSubmit(data: any) {
    setIsLoading(true);

    let updatedObject: any = {
      id: props.row.id,
    };

    if (type === "relationship") {
      const relationshipSchema = schema.relationships?.find(
        (s) => s.name === attributeOrRelationshipName
      );

      if (relationshipSchema?.cardinality === "many") {
        const newRelationshipList = row[attributeOrRelationshipName].map((item: any) => {
          if (item.id === props.attributeOrRelationshipToEdit.id) {
            return {
              ...data,
              id: item.id,
            };
          } else {
            return {
              id: item.id,
            };
          }
        });

        updatedObject[attributeOrRelationshipName] = newRelationshipList;
      } else {
        updatedObject[attributeOrRelationshipName] = {
          id: props.row[attributeOrRelationshipName].id,
          ...data,
        };
      }
    } else {
      updatedObject[attributeOrRelationshipName] = {
        ...data,
      };
    }

    if (Object.keys(updatedObject).length) {
      try {
        const mutationString = updateObjectWithId({
          name: schema.name,
          data: stringifyWithoutQuotes({
            id: row.id,
            ...updatedObject,
          }),
        });

        const mutation = gql`
          ${mutationString}
        `;

        await graphqlClient.mutate({
          mutation,
          context: { branch: branch?.name, date },
        });

        toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Metadata updated"} />);

        onUpdateComplete();

        setIsLoading(false);

        return;
      } catch (e) {
        setIsLoading(false);

        toast(
          <Alert
            message="Something went wrong while updating the meetadata"
            type={ALERT_TYPES.ERROR}
          />
        );

        console.error("Something went wrong while updating the meetadata", e);

        return;
      }
    }
  }

  return (
    <div className="flex-1 bg-white flex">
      <EditFormHookComponent
        onCancel={props.closeDrawer}
        onSubmit={onSubmit}
        fields={formStructure}
        isLoading={isLoading}
      />
    </div>
  );
}
