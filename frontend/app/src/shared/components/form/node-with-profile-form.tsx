import { NodeForm, NodeFormProps } from "@/shared/components/form/node-form";
import { ProfileData } from "@/shared/components/form/object-form";
import { ProfilesSelector } from "@/shared/components/form/profiles-selector";
import { useState } from "react";

export const NodeWithProfileForm = ({ schema, profiles, ...props }: NodeFormProps) => {
  const [selectedProfiles, setSelectedProfiles] = useState<ProfileData[] | undefined>();

  return (
    <>
      <ProfilesSelector
        schema={schema}
        defaultValue={profiles}
        value={selectedProfiles}
        onChange={setSelectedProfiles}
      />

      <NodeForm schema={schema} profiles={selectedProfiles} {...props} />
    </>
  );
};
