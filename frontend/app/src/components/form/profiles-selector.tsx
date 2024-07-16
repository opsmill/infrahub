import { genericsState, iNodeSchema, profilesAtom } from "@/state/atoms/schema.atom";
import { useId } from "react";
import { useAtomValue } from "jotai/index";
import { getObjectAttributes } from "@/utils/getSchemaObjectColumns";
import ErrorScreen from "@/screens/errors/error-screen";
import { getProfiles } from "@/graphql/queries/objects/getProfiles";
import { gql } from "@apollo/client";
import useQuery from "@/hooks/useQuery";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import Label from "@/components/ui/label";
import { MultiCombobox } from "@/components/ui/combobox";

type ProfilesSelectorProps = {
  schema: iNodeSchema;
  value?: any[];
  defaultValue?: any[];
  onChange: (item: any[]) => void;
  currentProfiles?: any[];
};

export const ProfilesSelector = ({
  schema,
  value,
  defaultValue,
  onChange,
}: ProfilesSelectorProps) => {
  const id = useId();

  const generics = useAtomValue(genericsState);
  const profiles = useAtomValue(profilesAtom);

  const nodeGenerics = schema?.inherit_from ?? [];

  // Get all available generic profiles
  const nodeGenericsProfiles = nodeGenerics
    // Find all generic schema
    .map((nodeGeneric: any) => generics.find((generic) => generic.kind === nodeGeneric))
    // Filter for generate_profile ones
    .filter((generic: any) => generic.generate_profile)
    // Get only the kind
    .map((generic: any) => generic.kind)
    .filter(Boolean);

  // The profiles should include the current object profile + all generic profiles
  const kindList = [schema.kind, ...nodeGenericsProfiles];

  // Add attributes for each profile to get the values in the form
  const profilesList = kindList
    .map((profile) => {
      // Get the profile schema for the current kind
      const profileSchema = profiles.find((profileSchema) => profileSchema.name === profile);

      // Get attributes for query + form data
      const attributes = getObjectAttributes({ schema: profileSchema, forListView: true });

      if (!attributes.length) return null;

      return {
        name: profileSchema?.kind,
        schema: profileSchema,
        attributes,
      };
    })
    .filter(Boolean);

  // Get all profiles name to retrieve the informations from the result
  const profilesNameList: string[] = profilesList
    .map((profile) => profile?.name ?? "")
    .filter(Boolean);

  if (!profilesList.length)
    return <ErrorScreen message="Something went wrong while fetching profiles" />;

  const queryString = getProfiles({ profiles: profilesList });

  const query = gql`
    ${queryString}
  `;

  const { data, error, loading } = useQuery(query);

  if (loading) return <LoadingScreen size={30} hideText className="p-4 pb-0" />;

  if (error) return <ErrorScreen message={error.message} />;

  // Get data for each profile in the query result
  const profilesData = profilesNameList.reduce(
    (acc, profile) => [...acc, ...(data?.[profile!]?.edges ?? [])],
    []
  );

  // Build combobox options
  const items = profilesData?.map((edge: any) => ({
    value: edge.node.id,
    label: edge.node.display_label,
    data: edge.node,
  }));

  const selectedValues = value?.map((profile) => profile.id) ?? [];

  const handleChange = (newProfilesId: string[]) => {
    const newSelectedProfiles = newProfilesId
      .map((profileId) => items.find((option) => option.value === profileId))
      .filter(Boolean)
      .map((option) => option?.data);

    onChange(newSelectedProfiles);
  };

  if (!profilesData || profilesData.length === 0) return null;

  if (!value && defaultValue) {
    const ids = defaultValue.map((profile) => profile.id);

    handleChange(ids);
  }

  return (
    <div className="p-4 bg-gray-100">
      <Label htmlFor={id}>
        Select profiles <span className="text-xs italic text-gray-500 ml-1">optional</span>
      </Label>

      <MultiCombobox id={id} items={items} onChange={handleChange} value={selectedValues} />
    </div>
  );
};
