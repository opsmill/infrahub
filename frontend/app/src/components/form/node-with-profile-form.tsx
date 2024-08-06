import { useAtomValue } from "jotai/index";
import { genericsState, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import { useState } from "react";
import NoDataFound from "@/screens/errors/no-data-found";
import { ProfilesSelector } from "@/components/form/profiles-selector";
import { NodeForm, ObjectFormProps, ProfileData } from "@/components/form/object-form";

export const NodeWithProfileForm = ({
  isFilterForm,
  kind,
  currentProfiles,
  ...props
}: ObjectFormProps) => {
  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);
  const profiles = useAtomValue(profilesAtom);

  const [selectedProfiles, setSelectedProfiles] = useState<ProfileData[] | undefined>();

  const nodeSchema = [...nodes, ...generics, ...profiles].find((node) => node.kind === kind);

  if (!nodeSchema) {
    return <NoDataFound message={`${kind} schema not found. Try to reload the page.`} />;
  }

  return (
    <>
      {!isFilterForm && "generate_profile" in nodeSchema && nodeSchema.generate_profile && (
        <ProfilesSelector
          schema={nodeSchema}
          defaultValue={currentProfiles}
          value={selectedProfiles}
          onChange={setSelectedProfiles}
          currentProfiles={currentProfiles}
        />
      )}
      <NodeForm
        schema={nodeSchema}
        isFilterForm={isFilterForm}
        profiles={selectedProfiles}
        {...props}
      />
    </>
  );
};
