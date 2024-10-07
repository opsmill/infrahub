import { NodeForm, NodeFormProps } from "@/components/form/node-form";
import { ProfileData } from "@/components/form/object-form";
import { ProfilesSelector } from "@/components/form/profiles-selector";
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
