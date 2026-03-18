import { useState } from "react";

import type { CoreFileFormProps } from "@/shared/components/form/core-file-form";
import { CoreFileForm } from "@/shared/components/form/core-file-form";
import type { ProfileData } from "@/shared/components/form/object-form";
import { ProfilesSelector } from "@/shared/components/form/profiles-selector";

export const FileWithProfileForm = ({ schema, profiles, ...props }: CoreFileFormProps) => {
  const [selectedProfiles, setSelectedProfiles] = useState<ProfileData[] | undefined>();

  return (
    <>
      <ProfilesSelector
        schema={schema}
        defaultValue={profiles}
        value={selectedProfiles}
        onChange={setSelectedProfiles}
      />

      <CoreFileForm schema={schema} profiles={selectedProfiles} {...props} />
    </>
  );
};
