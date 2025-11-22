import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useId } from "react";

import useQuery from "@/shared/api/graphql/useQuery";
import { Button } from "@/shared/components/buttons/button-primitive";
import ErrorScreen from "@/shared/components/errors/error-screen";
import type { ProfileData } from "@/shared/components/form/object-form";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
} from "@/shared/components/ui/combobox";
import Label from "@/shared/components/ui/label";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { Spinner } from "@/shared/components/ui/spinner";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { getProfiles } from "@/entities/nodes/api/getProfiles";
import { getObjectAttributes } from "@/entities/nodes/object-items/getSchemaObjectColumns";
import { genericSchemasAtom, profileSchemasAtom } from "@/entities/schema/stores/schema.atom";
import type { NodeSchema } from "@/entities/schema/types";

type ProfilesSelectorProps = {
  schema: NodeSchema;
  value?: ProfileData[];
  defaultValue?: ProfileData[];
  onChange: (item: ProfileData[]) => void;
};

export const ProfilesSelector = ({ schema, value, onChange }: ProfilesSelectorProps) => {
  const id = useId();

  const genericSchemas = useAtomValue(genericSchemasAtom);
  const profileSchemas = useAtomValue(profileSchemasAtom);

  const nodeGenerics = schema?.inherit_from ?? [];

  // Get all available generic profiles
  const nodeGenericsProfiles = nodeGenerics
    // Find all generic schema
    .map((nodeGeneric) => genericSchemas.find((generic) => generic.kind === nodeGeneric))
    // Filter for generate_profile ones
    .filter((generic) => generic?.generate_profile)
    // Get only the kind
    .map((generic) => generic?.kind)
    .filter(Boolean);

  // The profiles should include the current object profile + all generic profiles
  const kindList = [schema.kind, ...nodeGenericsProfiles];

  // Add attributes for each profile to get the values in the form
  const profilesList = kindList
    .map((profile) => {
      // Get the profile schema for the current kind
      const profileSchema = profileSchemas.find(
        (profileSchema) => profileSchema.name === profile?.replace("Template", "")
      );

      // Get attributes for query + form data
      const attributes = getObjectAttributes({ schema: profileSchema, forProfiles: true });

      if (!attributes.length) return null;

      return {
        name: profileSchema?.kind,
        schema: profileSchema,
        attributes,
      };
    })
    .filter(Boolean);

  if (!profilesList.length)
    return <ErrorScreen message="Something went wrong while fetching profiles" />;

  const queryString = getProfiles({ profiles: profilesList });

  const query = gql`
    ${queryString}
  `;

  const { data, error, loading } = useQuery(query);

  if (loading) return <LoadingIndicator className="p-4" />;

  if (error) return <ErrorScreen message={error.message} />;

  // Get all profiles name to retrieve the information from the result
  const profilesNameList: string[] = profilesList
    .map((profile) => profile?.name ?? "")
    .filter(Boolean);

  // Get data for each profile in the query result
  const profiles = profilesNameList.reduce<Array<ProfileData>>(
    (acc, profile) => [
      ...acc,
      ...(data?.[profile!]?.edges.map((edge: { node: ProfileData }) => edge.node) ?? []),
    ],
    []
  );

  if (!profiles || profiles.length === 0) return null;

  const selectedValues = value ?? [];

  const handleChange = (profile: ProfileData) => {
    onChange([...selectedValues, profile]);
  };

  const handleRemove = (profile: ProfileData) => {
    onChange(selectedValues.filter((item) => item.id !== profile.id));
  };

  return (
    <div className="bg-gray-100 p-4">
      <Label htmlFor={id}>
        Select profiles <span className="ml-1 text-gray-500 text-xs italic">optional</span>
      </Label>

      <Combobox>
        <PopoverTrigger asChild>
          <div
            className={classNames(
              inputStyle,
              "has-[>:last-child:focus]:border-custom-blue-600 has-[>:last-child:focus]:outline-hidden has-[>:last-child:focus]:ring-2 has-[>:last-child:focus]:ring-custom-blue-600/25",
              "cursor-pointer"
            )}
          >
            <div className="flex grow flex-wrap gap-2">
              {selectedValues?.map((profile) => (
                <Badge key={id} className="flex items-center gap-1 pr-0.5">
                  {profile.display_label}

                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRemove(profile);
                    }}
                    className="h-4 w-4 text-gray-500 hover:text-gray-800"
                    aria-label="Remove"
                    data-testid="remove-option"
                  >
                    &times;
                  </Button>
                </Badge>
              ))}
            </div>

            {loading && <Spinner className="ml-auto" />}

            <button id={id} type="button" className="h-3.5 w-3.5 text-gray-600 outline-hidden">
              <Icon icon="mdi:unfold-more-horizontal" />
            </button>
          </div>
        </PopoverTrigger>

        <ComboboxContent>
          <ComboboxList>
            <ComboboxEmpty>No profiles found</ComboboxEmpty>
            {profiles
              .filter((profile) => !selectedValues.some((value) => value.id === profile.id))
              .map((item) => (
                <ComboboxItem
                  key={item.id}
                  value={item.display_label}
                  onSelect={() => handleChange(item)}
                >
                  {item.display_label}
                </ComboboxItem>
              ))}
          </ComboboxList>
        </ComboboxContent>
      </Combobox>
    </div>
  );
};
