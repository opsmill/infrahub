import { useState } from "react";

import { NodeForm, type NodeFormProps } from "@/shared/components/form/node-form";
import type { ProfileData } from "@/shared/components/form/object-form";
import { ProfilesSelector } from "@/shared/components/form/profiles-selector";

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
