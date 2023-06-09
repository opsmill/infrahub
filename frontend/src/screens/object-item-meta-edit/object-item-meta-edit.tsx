import { gql, useReactiveVar } from "@apollo/client";
import { useState } from "react";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/alert";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { updateObjectWithId } from "../../graphql/mutations/objects/updateObjectWithId";
import { branchVar } from "../../graphql/variables/branchVar";
import { dateVar } from "../../graphql/variables/dateVar";
import { iNodeSchema } from "../../state/atoms/schema.atom";
import { getFormStructureForMetaEditPaginated } from "../../utils/formStructureForCreateEdit";
import getMutationMetaDetailsFromFormData from "../../utils/getMutationMetaDetailsFromFormData";
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
    closeDrawer,
  } = props;

  const branch = useReactiveVar(branchVar);
  const date = useReactiveVar(dateVar);
  const [isLoading, setIsLoading] = useState(false);

  const formStructure = getFormStructureForMetaEditPaginated(
    attributeOrRelationshipToEdit,
    type,
    schemaList
  );

  async function onSubmit(data: any) {
    setIsLoading(true);

    const updatedObject = getMutationMetaDetailsFromFormData(
      schema,
      data,
      row,
      type,
      attributeOrRelationshipName,
      attributeOrRelationshipToEdit
    );

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

        closeDrawer();

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
        onCancel={closeDrawer}
        onSubmit={onSubmit}
        fields={formStructure}
        isLoading={isLoading}
      />
    </div>
  );
}
