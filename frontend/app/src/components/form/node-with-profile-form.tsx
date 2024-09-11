import { useState } from "react";
import { ProfilesSelector } from "@/components/form/profiles-selector";
import { ProfileData } from "@/components/form/object-form";
import { NodeForm, NodeFormProps } from "@/components/form/node-form";

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
