import { useState } from "react";
import NoDataFound from "@/screens/errors/no-data-found";
import { ProfilesSelector } from "@/components/form/profiles-selector";
import { ObjectFormProps, ProfileData } from "@/components/form/object-form";
import { NodeForm } from "@/components/form/node-form";
import { useSchema } from "@/hooks/useSchema";

export const NodeWithProfileForm = ({
  isFilterForm,
  kind,
  currentProfiles,
  ...props
}: ObjectFormProps) => {
  const { schema } = useSchema(kind);
  const [selectedProfiles, setSelectedProfiles] = useState<ProfileData[] | undefined>();

  if (!schema) {
    return <NoDataFound message={`${kind} schema not found. Try to reload the page.`} />;
  }

  return (
    <>
      <ProfilesSelector
        schema={schema}
        defaultValue={currentProfiles}
        value={selectedProfiles}
        onChange={setSelectedProfiles}
      />

      <NodeForm
        schema={schema}
        isFilterForm={isFilterForm}
        profiles={selectedProfiles}
        {...props}
      />
    </>
  );
};
