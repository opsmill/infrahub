import { Icon } from "@iconify-icon/react";
import { useEffect, useId } from "react";

import { Button } from "@/shared/components/buttons/button-primitive";
import ErrorScreen from "@/shared/components/errors/error-screen";
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

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { useGetProfiles } from "@/entities/nodes/profiles/domain/get-profiles.query";
import type { ProfileData } from "@/entities/nodes/profiles/types";
import type { NodeSchema } from "@/entities/schema/types";

type ProfilesSelectorProps = {
  schema: NodeSchema;
  value?: ProfileData[];
  defaultValue?: ProfileData[];
  onChange: (item: ProfileData[]) => void;
};

export const ProfilesSelector = ({
  schema,
  value,
  defaultValue,
  onChange,
}: ProfilesSelectorProps) => {
  const id = useId();
  const { data: profiles = [], error, isPending } = useGetProfiles({ schema });

  useEffect(() => {
    if (!value && defaultValue && profiles.length && !isPending) {
      const defaultProfiles = defaultValue
        .map((defaultProfile) => {
          return profiles.find((profile) => {
            return profile.id === defaultProfile.id;
          });
        })
        .filter((profile): profile is ProfileData => {
          return !!profile?.id;
        });

      onChange(defaultProfiles);
    }
  }, [defaultValue, isPending, profiles, value, onChange]);

  if (isPending) return <LoadingIndicator className="p-4" />;

  if (error) return <ErrorScreen message={error.message} />;

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
                  {getNodeLabel(profile)}

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

            {isPending && <Spinner className="ml-auto" />}

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
                  value={getNodeLabel(item)}
                  onSelect={() => handleChange(item)}
                >
                  {getNodeLabel(item)}
                </ComboboxItem>
              ))}
          </ComboboxList>
        </ComboboxContent>
      </Combobox>
    </div>
  );
};
