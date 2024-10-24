import { BUTTON_TYPES, Button } from "@/components/buttons/button";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import ObjectForm from "@/components/form/object-form";
import ModalDelete from "@/components/modals/modal-delete";
import {
  SCHEMA_DROPDOWN_ADD,
  SCHEMA_DROPDOWN_REMOVE,
  SCHEMA_ENUM_ADD,
  SCHEMA_ENUM_REMOVE,
} from "@/config/constants";
import { SchemaContext } from "@/decorators/withSchemaContext";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { basicMutation } from "@/graphql/mutations/objects/basicMutation";
import { getDropdownOptions } from "@/graphql/queries/objects/dropdownOptions";
import { useLazyQuery } from "@/hooks/useQuery";
import { FormFieldError } from "@/screens/edit-form-hook/form";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { namespacesState, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { classNames, getTextColor } from "@/utils/common";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import { Combobox } from "@headlessui/react";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai/index";
import { forwardRef, useContext, useEffect, useState } from "react";
import { Input } from "./input";
import { MultipleInput } from "./multiple-input";

import DynamicForm from "@/components/form/dynamic-form";
import { Tooltip } from "@/components/ui/tooltip";
import { getObjectDisplayLabel } from "@/graphql/queries/objects/getObjectDisplayLabel";
import usePrevious from "@/hooks/usePrevious";
import { POOLS_DICTIONNARY, POOLS_PEER } from "@/screens/ipam/constants";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { comparedOptions } from "@/utils/array";
import { getOptionsFromRelationship } from "@/utils/getSchemaObjectColumns";
import { Badge } from "../ui/badge";

export type Parent = {
  name?: string;
  value?: string;
};

export type SelectOption = {
  id: string | number;
  name: string;
  color?: string; // For dropdown
  description?: string; // For dropdown
  badge?: string;
};

export enum SelectDirection {
  OVER,
}

export type SelectProps = {
  id?: string;
  className?: string;
  value?: string | string[] | number | number[];
  kind?: string;
  name?: string;
  peer?: string;
  parent?: Parent;
  options: SelectOption[];
  onChange?: (value: any) => void;
  disabled?: boolean;
  error?: FormFieldError;
  direction?: SelectDirection;
  preventObjectsCreation?: boolean;
  multiple?: boolean;
  dropdown?: boolean;
  enum?: boolean;
  field?: any;
  relationship?: any;
  schema?: any;
  preventEmpty?: boolean;
  isOptional?: boolean;
  isUnique?: boolean;
  isInherited?: boolean;
  placeholder?: string;
  peerField?: string;
};

export const Select = forwardRef<HTMLDivElement, SelectProps>((props, ref) => {
  const {
    id,
    className,
    options,
    value,
    onChange,
    disabled,
    error,
    direction,
    peer,
    parent,
    preventObjectsCreation,
    multiple,
    dropdown,
    enum: enumBoolean,
    field,
    schema,
    placeholder,
    preventEmpty,
    peerField, // Field used to build option label
    // eslint-disable-next-line @typescript-eslint/no-unused-vars, no-unused-vars
    isOptional, // Avoid proving useless props
    // eslint-disable-next-line @typescript-eslint/no-unused-vars, no-unused-vars
    isUnique, // Avoid proving useless props
    ...otherProps
  } = props;
  const { kind } = props;

  const { checkSchemaUpdate } = useContext(SchemaContext);

  const schemaList = useAtomValue(schemaState);
  const profiles = useAtomValue(profilesAtom);
  const schemaKindName = useAtomValue(schemaKindNameState);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const namespaces = useAtomValue(namespacesState);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  // TODO: after refactor, find a way to verify the options to trigger or not the request
  const [hasPoolsBeenOpened, setHasPoolsBeenOpened] = useState(false);
  const [hasBeenOpened, setHasBeenOpened] = useState(false);
  const [optionToDelete, setOptionToDelete] = useState<null | number | string>(null);
  const [localOptions, setLocalOptions] = useState(options);
  const previousKind = usePrevious(kind);
  const previousParent = usePrevious(parent?.value);

  const findSelectedOption = () => {
    return multiple
      ? localOptions.filter(
          (option) => Array.isArray(value) && value.map((v) => v.id)?.includes(option.id)
        )
      : localOptions?.find((option) => option?.id === value || option.name === value);
  };

  const [selectedOption, setSelectedOption] = useState(findSelectedOption());

  const namespaceData = namespaces.find((n) => n.name === schema?.namespace);

  const schemaData = [...schemaList, ...profiles].find((s) => s.kind === peer);

  // Check if any kind from inheritance is one of the available for pools
  const canRequestPools = !!schemaData?.inherit_from
    ?.map((from) => POOLS_PEER.includes(from))
    ?.filter(Boolean)?.length;
  const poolPeer = canRequestPools && POOLS_DICTIONNARY[peer];

  const parentFilter = parent?.value ? `${parent.name}__ids: ["${parent.value}"]` : "";

  // Query to fetch options only if a peer is defined
  // TODO: Find another solution for queries while loading schema
  const optionsQueryString = peer
    ? getDropdownOptions({ kind: peer, parentFilter, peerField })
    : "query { ok }";
  const poolsQueryString = poolPeer ? getDropdownOptions({ kind: poolPeer }) : "query { ok }";

  const optionsQuery = gql`
    ${optionsQueryString}
  `;

  const poolsQuery = gql`
    ${poolsQueryString}
  `;

  const [fetchOptions, { loading: optionsLoading, data: optionsData }] = useLazyQuery(optionsQuery);
  const [fetchPoolsOptions, { loading: poolsLoading, data: poolsData }] = useLazyQuery(poolsQuery);
  const loading = optionsLoading || poolsLoading;
  const data = hasBeenOpened ? optionsData : poolsData;

  const labelQueryString = peer ? getObjectDisplayLabel({ kind: peer, peerField }) : "query { ok }";

  const labelQuery = gql`
    ${labelQueryString}
  `;

  const [fetchLabel] = useLazyQuery(labelQuery);

  const optionsResult =
    peer && data ? data[hasBeenOpened ? peer : poolPeer]?.edges.map((edge: any) => edge.node) : [];

  const optionsList = getOptionsFromRelationship({
    options: optionsResult,
    schemas: schemaList,
    peerField,
  });

  const addOption: SelectOption = {
    name: "Add option",
    id: "add-new-option",
  };

  const emptyOption: SelectOption = {
    name: "Empty",
    id: "empty-option",
  };

  const filteredOptions = !query
    ? localOptions
    : localOptions.filter((option) =>
        option?.name?.toString().toLowerCase().includes(query.toLowerCase())
      );

  const finalOptions = [...(preventEmpty ? [] : [emptyOption]), ...(filteredOptions || [])];

  const textColor =
    typeof selectedOption === "object" && !Array.isArray(selectedOption)
      ? getTextColor(selectedOption?.color)
      : "";

  const canRemoveOption = (id: string | number) =>
    namespaceData?.user_editable && (dropdown || enumBoolean) && id !== emptyOption.id;

  const handleChange = (newValue: any) => {
    // Fetch if we are changing the option without opening the select
    // (for ex: when removing an item in the multiple input)
    if (hasPoolsBeenOpened) {
      handleFocusPools();
    } else {
      handleFocus();
    }

    if (!newValue) {
      setSelectedOption(undefined);
      if (onChange) onChange(null);
      return;
    }

    if (newValue.id === addOption.id) {
      setOpen(true);
      return;
    }

    if (newValue.id === emptyOption.id) {
      setSelectedOption(emptyOption);
      if (onChange) onChange(null);
      return;
    }

    if (multiple) {
      const includesNewItemCreation = newValue.find((i: any) => i.id === addOption.id);

      if (includesNewItemCreation) {
        setOpen(true);
        return;
      }

      setOpen(false);
      setSelectedOption(newValue);

      if (hasPoolsBeenOpened) {
        if (onChange)
          onChange(
            newValue.map((item) => ({
              from_pool: {
                id: item.id,
                name: item.name,
                kind: item.kind,
              },
            }))
          );
        return;
      }

      if (onChange) onChange(newValue.map((item) => ({ id: item.id })));
      return;
    }

    setSelectedOption(newValue);
    setQuery("");
    setOpen(false);

    if (hasPoolsBeenOpened) {
      if (onChange) {
        onChange({
          from_pool: {
            id: newValue.id,
            name: newValue.name,
            kind: newValue.kind,
          },
        });
      }
      return;
    }

    if (dropdown || enumBoolean) {
      if (onChange) onChange(newValue.id);
      return;
    }

    if (onChange) onChange({ id: newValue.id });
  };

  const handleCreate = (response: any) => {
    const newItem = {
      id: response.object.id,
      name: response.object.display_label,
    };

    setLocalOptions([...localOptions, newItem]);

    if (multiple) {
      handleChange([...(selectedOption ?? []), newItem]);

      return;
    }

    handleChange(newItem);
  };

  const handleInputChange = (newValue: any) => {
    if (multiple) {
      handleChange(newValue);
      return;
    }

    // Remove the selected option and update query (allow empty query)
    setSelectedOption(undefined);
    setQuery(newValue);
  };

  const handleFocus = () => {
    // Do not fetch if there is no peer
    if (!peer || hasBeenOpened) return;

    // Do not fetch regular options if pool was used
    if (hasPoolsBeenOpened && selectedOption?.length) return;

    setHasPoolsBeenOpened(false);
    setHasBeenOpened(true);
    fetchOptions();
  };

  const handleFocusPools = () => {
    // Do not fetch if there is no peer
    if (!poolPeer || hasPoolsBeenOpened) return;

    // Do not fetch pool options if a regular option was used
    if (hasBeenOpened && selectedOption?.length) return;

    setHasPoolsBeenOpened(true);
    setHasBeenOpened(false);
    fetchPoolsOptions();
  };

  const getOptionStyle = (option: any) => {
    if (option.color) {
      return {
        backgroundColor: option?.color || "",
        color: option?.color ? getTextColor(option?.color) : "",
      };
    }

    if (option.id === emptyOption.id) {
      return {
        fontStyle: "italic",
      };
    }

    return {};
  };

  const renderContentForDropdown = () => {
    const handleSubmit = async (data: any) => {
      setIsLoading(true);

      try {
        const { value, color, label, description } = data;

        const update = {
          kind: schema.kind,
          attribute: field.name,
          dropdown: value,
          color,
          description,
          label,
        };

        const mustationString = basicMutation({
          kind: SCHEMA_DROPDOWN_ADD,
          data: stringifyWithoutQuotes(update),
        });

        const mutation = gql`
          ${mustationString}
        `;

        await graphqlClient.mutate({
          mutation,
          context: {
            branch: branch?.name,
            date,
          },
        });

        const newOption = {
          id: value,
          name: label,
          description,
          color,
        };

        setLocalOptions([...localOptions, newOption]);

        handleChange(newOption);

        setIsLoading(false);

        checkSchemaUpdate();
      } catch (e) {
        setIsLoading(false);
      }
    };

    const handleCancel = () => setOpen(false);

    return (
      <DynamicForm
        fields={[
          {
            name: "value",
            label: "Name",
            type: "Text",
            rules: {
              required: true,
            },
          },
          {
            name: "color",
            label: "Color",
            type: "Color",
          },
          {
            name: "label",
            label: "Label",
            type: "Text",
          },
          {
            name: "description",
            label: "Description",
            type: "Text",
          },
        ]}
        onSubmit={async (data) => {
          await handleSubmit({
            value: data.value.value,
            color: data.color.value,
            label: data.label.value,
            description: data.description.value,
          });
        }}
        onCancel={handleCancel}
        className="p-4"
      />
    );
  };

  const renderContentForEnum = () => {
    const handleSubmit = async ({ value }: any) => {
      setIsLoading(true);

      try {
        const update = {
          kind: schema.kind,
          attribute: field.name,
          enum: value,
        };

        const mustationString = basicMutation({
          kind: SCHEMA_ENUM_ADD,
          data: stringifyWithoutQuotes(update),
        });

        const mutation = gql`
          ${mustationString}
        `;

        await graphqlClient.mutate({
          mutation,
          context: {
            branch: branch?.name,
            date,
          },
        });

        const newOption = {
          id: value,
          name: value,
        };

        setLocalOptions([...localOptions, newOption]);

        handleChange(newOption);

        setOpen(false);

        setIsLoading(false);
      } catch (e) {
        setIsLoading(false);
      }
    };

    const handleCancel = () => setOpen(false);

    return (
      <DynamicForm
        fields={[
          {
            name: "value",
            label: "Value",
            type: kind === "Number" ? "Number" : "Text",
            rules: {
              required: true,
            },
          },
        ]}
        onSubmit={async ({ value }) => {
          await handleSubmit({ value: value.value });
        }}
        onCancel={handleCancel}
        className="p-4"
      />
    );
  };

  const handleDeleteOption = async () => {
    setIsLoading(true);

    try {
      const update = {
        kind: schema.kind,
        attribute: field.name,
        dropdown: optionToDelete,
      };

      const mustationString = basicMutation({
        kind: SCHEMA_DROPDOWN_REMOVE,
        data: stringifyWithoutQuotes(update),
      });

      const mutation = gql`
        ${mustationString}
      `;

      await graphqlClient.mutate({
        mutation,
        context: {
          branch: branch?.name,
          date,
        },
      });

      const newOptions = localOptions.filter((o) => o.id !== optionToDelete);

      setLocalOptions([...newOptions]);

      setOptionToDelete(null);

      setIsLoading(false);
    } catch (error) {
      setIsLoading(false);
    }
  };

  const handleDeleteEum = async () => {
    setIsLoading(true);

    try {
      const update = {
        kind: schema.kind,
        attribute: field.name,
        enum: typeof optionToDelete === "string" ? optionToDelete : JSON.stringify(optionToDelete),
      };

      const mustationString = basicMutation({
        kind: SCHEMA_ENUM_REMOVE,
        data: stringifyWithoutQuotes(update),
      });

      const mutation = gql`
        ${mustationString}
      `;

      await graphqlClient.mutate({
        mutation,
        context: {
          branch: branch?.name,
          date,
        },
      });

      const newOptions = localOptions.filter((o) => o.id !== optionToDelete);

      setLocalOptions([...newOptions]);

      setOptionToDelete(null);

      setIsLoading(false);
    } catch (error) {
      setIsLoading(false);
    }
  };

  const getOptionButton = () => {
    if (peer && !preventObjectsCreation) {
      return (
        <Combobox.Option
          value={addOption}
          className={({ active }) =>
            classNames(
              "relative cursor-pointer select-none py-2 pl-3 pr-9 m-2 rounded-md",
              active ? "bg-custom-blue-600 text-custom-white" : "bg-gray-100 text-gray-900"
            )
          }
        >
          <span className={"truncate flex items-center"}>
            <Icon icon={"mdi:plus"} /> Add {schemaKindName[peer]}
          </span>
        </Combobox.Option>
      );
    }

    if (namespaceData?.user_editable && (dropdown || enumBoolean)) {
      if (field.inherited) {
        return (
          <Combobox.Option
            disabled
            value={addOption}
            className={
              "flex relative select-none py-2 pl-3 pr-9 m-2 rounded-md bg-gray-100 text-gray-900 cursor-not-allowed"
            }
          >
            <Tooltip content="Can't add an option on an attribute inherited from a generic" enabled>
              <span className={"truncate flex flex-grow items-center"}>
                <Icon icon={"mdi:plus"} className="mr-2" /> Add option
              </span>
            </Tooltip>
          </Combobox.Option>
        );
      }

      return (
        <Combobox.Option
          value={addOption}
          className={({ active }) =>
            classNames(
              "flex relative cursor-pointer select-none py-2 pl-3 pr-9 m-2 rounded-md",
              active ? "bg-custom-blue-600 text-custom-white" : "bg-gray-100 text-gray-900"
            )
          }
        >
          <span className={"truncate flex items-center"}>
            <Icon icon={"mdi:plus"} /> Add option
          </span>
        </Combobox.Option>
      );
    }

    return null;
  };

  const getOptionContent = () => {
    if (peer && !preventObjectsCreation) {
      return (
        <SlideOver
          title={
            schemaData && (
              <SlideOverTitle
                schema={schemaData}
                currentObjectLabel="New"
                title={`Create ${schemaData.label}`}
                subtitle={schemaData.description}
              />
            )
          }
          open={open}
          setOpen={setOpen}
          offset={1}
        >
          <ObjectForm
            kind={peer}
            onSuccess={handleCreate}
            onCancel={() => setOpen(false)}
            data-testid="new-object-form"
          />
        </SlideOver>
      );
    }

    if (!namespaceData?.user_editable) {
      return;
    }

    if (dropdown) {
      return (
        <>
          <SlideOver
            title={
              <SlideOverTitle
                schema={schema}
                currentObjectLabel={field?.label}
                title="Add a new option"
                subtitle={field?.description}
              />
            }
            open={open}
            setOpen={setOpen}
            offset={1}
          >
            {renderContentForDropdown()}
          </SlideOver>

          <ModalDelete
            title="Delete"
            description={"Are you sure you want to remove this option?"}
            onCancel={() => setOptionToDelete(null)}
            onDelete={handleDeleteOption}
            open={!!optionToDelete}
            setOpen={() => setOptionToDelete(null)}
            isLoading={isLoading}
          />
        </>
      );
    }

    if (enumBoolean) {
      return (
        <>
          <SlideOver
            title={
              <SlideOverTitle
                schema={schema}
                currentObjectLabel={field?.label}
                title="Add a new option"
                subtitle={field?.description}
              />
            }
            open={open}
            setOpen={setOpen}
            offset={1}
          >
            {renderContentForEnum()}
          </SlideOver>

          <ModalDelete
            title="Delete"
            description={"Are you sure you want to remove this enum?"}
            onCancel={() => setOptionToDelete(null)}
            onDelete={handleDeleteEum}
            open={!!optionToDelete}
            setOpen={() => setOptionToDelete(null)}
            isLoading={isLoading}
          />
        </>
      );
    }

    return null;
  };

  const getInputValue = () => {
    if (multiple) {
      return selectedOption;
    }

    if (query) {
      return query;
    }

    if (typeof selectedOption === "object" && !Array.isArray(selectedOption)) {
      if (selectedOption?.id === emptyOption.id) {
        return "";
      }

      return selectedOption?.name;
    }

    return selectedOption ?? "";
  };

  const getInputStyle = () => {
    if (typeof selectedOption === "object" && !Array.isArray(selectedOption)) {
      return {
        backgroundColor: (typeof selectedOption === "object" && selectedOption?.color) || "",
        color: typeof selectedOption === "object" && selectedOption?.color ? textColor : "",
      };
    }

    return {};
  };

  // Fetch option display label if not defined by current selected option
  const handleFetchLabel = async () => {
    if (!selectedOption && !value) return;

    if (peer && !multiple && !Array.isArray(selectedOption) && !selectedOption?.name) {
      const id = selectedOption?.id ?? value?.id ?? value;
      const { data } = await fetchLabel({ variables: { ids: [id] } });

      const label = peerField
        ? (data[peer]?.edges[0]?.node?.[peerField]?.value ??
          data[peer]?.edges[0]?.node?.[peerField])
        : data[peer]?.edges[0]?.node?.display_label;

      const newSelectedOption = {
        ...selectedOption,
        name: label ?? "Unknown",
      } as SelectOption;

      setSelectedOption(newSelectedOption);

      return;
    }

    if (!Array.isArray(selectedOption)) return;

    // Get ids only
    const ids = selectedOption.map((o) => o.id) ?? [];

    // Get defined names only
    const names = selectedOption.map((o) => o.name).filter(Boolean) ?? [];

    // If ids and names have !== lengths, then some names are not defined
    if (peer && multiple && ids.length && ids.length !== names.length) {
      const { data } = await fetchLabel({ variables: { ids } });

      const newSelectedOptions = data[peer]?.edges.map((edge) => ({
        name: peerField
          ? (edge.node?.[peerField]?.value ?? edge.node?.[peerField])
          : edge.node.display_label,
        id: edge.node.id,
      }));

      setSelectedOption(newSelectedOptions);
    }
  };

  useEffect(() => {
    // Avoid fetching labels if ther eis no value
    if (!value) {
      setSelectedOption(findSelectedOption());
      return;
    }

    if (localOptions.length > 0 && !peer) {
      setSelectedOption(findSelectedOption());
      return;
    }

    if (Array.isArray(value) && !value.length) return;

    handleFetchLabel();
  }, [value]);

  // If options from query are updated
  useEffect(() => {
    setLocalOptions(optionsList);
  }, [optionsList?.length]);

  // If options from parent are updated
  useEffect(() => {
    setLocalOptions(options);
  }, [options?.length]);

  // If kind or parent has changed, remove the current value
  useEffect(() => {
    if (peer && previousKind && peer !== previousKind) {
      handleChange(undefined);
    }

    if (parent?.value && previousParent && parent?.value !== previousParent) {
      handleChange(undefined);
    }
  }, [peer, parent?.value]);

  return (
    <div
      className={classNames("relative", dropdown && disabled && "opacity-60", className)}
      data-testid="select-container"
    >
      <Combobox
        as="div"
        value={multiple ? (selectedOption ?? []) : (selectedOption ?? "")}
        onChange={handleChange}
        disabled={disabled}
        multiple={multiple}
        by={comparedOptions}
        {...otherProps}
      >
        <div className="relative">
          <div className="flex">
            <Combobox.Input
              as={multiple ? MultipleInput : Input}
              value={getInputValue()}
              onChange={handleInputChange}
              onFocus={handleFocus}
              disabled={disabled}
              placeholder={placeholder}
              error={error}
              className={"pr-8"}
              style={getInputStyle()}
              hideEmpty
              data-testid="select-input"
            />
            <Combobox.Button
              ref={ref}
              id={id}
              className={classNames(
                "absolute inset-y-0 flex items-center rounded-r-md px-2 focus:outline-none disabled:cursor-not-allowed",
                canRequestPools ? "right-10" : "right-0"
              )}
              data-testid="select-open-option-button"
              onClick={handleFocus}
            >
              {loading && <LoadingScreen hideText size={24} />}

              {!loading && (
                <Icon icon={"mdi:chevron-down"} className="text-gray-500" style={getInputStyle()} />
              )}
            </Combobox.Button>
            {canRequestPools && (
              <Tooltip content="Open pools options" enabled>
                <Combobox.Button
                  className="inset-y-0 right-0 flex items-center rounded-md px-2 ml-2 focus:outline-none disabled:cursor-not-allowed ring-1 ring-inset ring-gray-300"
                  data-testid="select-open-pool-option-button"
                  onClick={handleFocusPools}
                >
                  <Icon icon={"mdi:list-box"} className="text-gray-500" />
                </Combobox.Button>
              </Tooltip>
            )}
          </div>

          {!loading && finalOptions && finalOptions.length > 0 && (
            <Combobox.Options
              className={classNames(
                "absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-custom-white text-base shadow-lg ring-1 ring-custom-black ring-opacity-5 focus:outline-none sm:text-sm",
                direction === SelectDirection.OVER ? "bottom-0" : ""
              )}
            >
              {finalOptions.map((option, index) => (
                <Combobox.Option
                  key={index}
                  value={option}
                  className="cursor-pointer select-none py-2 px-3"
                  style={getOptionStyle(option)}
                >
                  {({ selected }) => (
                    <div className="z-10 flex items-center gap-2">
                      <div className="grow truncate">
                        <span
                          className={classNames("block truncate", selected ? "font-semibold" : "")}
                        >
                          {option.name}
                        </span>

                        {option.description && (
                          <span
                            className={classNames(
                              "block truncate italic text-xs",
                              selected ? "font-semibold" : ""
                            )}
                          >
                            {option.description}
                          </span>
                        )}
                      </div>

                      <div className="flex">
                        {option.badge && <Badge className="mr-2">{option.badge}</Badge>}

                        <div className="w-4">
                          {selected && (
                            <Icon icon={"mdi:check"} className="w-4 h-4 text-custom-blue-700" />
                          )}
                        </div>
                      </div>

                      {canRemoveOption(option.id) && (
                        <Tooltip
                          content="Can't delete an option on an attribute inherited from a generic"
                          enabled={field.inherited}
                        >
                          <Button
                            disabled={field.inherited}
                            buttonType={BUTTON_TYPES.INVISIBLE}
                            className="p-0"
                            onClick={() => setOptionToDelete(option.id)}
                          >
                            <Icon
                              icon="mdi:trash"
                              className={field.inherited ? "text-gray-400" : "text-red-500"}
                            />
                          </Button>
                        </Tooltip>
                      )}
                    </div>
                  )}
                </Combobox.Option>
              ))}

              {getOptionButton()}
            </Combobox.Options>
          )}
        </div>
      </Combobox>

      {getOptionContent()}
    </div>
  );
});
