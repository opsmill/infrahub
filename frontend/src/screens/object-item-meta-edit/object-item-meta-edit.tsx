import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { useState } from "react";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/utils/alert";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { updateObjectWithId } from "../../graphql/mutations/objects/updateObjectWithId";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { iNodeSchema } from "../../state/atoms/schema.atom";
import { datetimeAtom } from "../../state/atoms/time.atom";
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

  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [isLoading, setIsLoading] = useState(false);

  const formStructure = getFormStructureForMetaEditPaginated(
    attributeOrRelationshipToEdit,
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
          kind: schema.kind,
          data: stringifyWithoutQuotes(updatedObject),
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
        console.error("Something went wrong while updating the meetadata", e);

        setIsLoading(false);

        return;
      }
    }
  }

  return (
    <div className="flex-1 bg-custom-white flex">
      <EditFormHookComponent
        onCancel={closeDrawer}
        onSubmit={onSubmit}
        fields={formStructure}
        isLoading={isLoading}
      />
    </div>
  );
}
