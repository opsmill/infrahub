import { gql } from "@apollo/client";
import { Combobox } from "@headlessui/react";
import { CheckIcon } from "@heroicons/react/20/solid";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai/index";
import { useContext, useEffect, useState } from "react";
import {
  DEFAULT_BRANCH_NAME,
  SCHEMA_DROPDOWN_ADD,
  SCHEMA_DROPDOWN_REMOVE,
  SCHEMA_ENUM_ADD,
  SCHEMA_ENUM_REMOVE,
} from "../../config/constants";
import { SchemaContext } from "../../decorators/withSchemaContext";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { basicMutation } from "../../graphql/mutations/objects/basicMutation";
import { getDropdownOptions } from "../../graphql/queries/objects/dropdownOptions";
import { useLazyQuery } from "../../hooks/useQuery";
import { Form, FormFieldError } from "../../screens/edit-form-hook/form";
import ObjectItemCreate from "../../screens/object-item-create/object-item-create-paginated";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { namespacesState, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { datetimeAtom } from "../../state/atoms/time.atom";
import { classNames, getTextColor } from "../../utils/common";
import { stringifyWithoutQuotes } from "../../utils/string";
import { BUTTON_TYPES, Button } from "../buttons/button";
import SlideOver from "../display/slide-over";
import ModalDelete from "../modals/modal-delete";
import { Input } from "./input";
import { MultipleInput } from "./multiple-input";

import { getObjectDisplayLabel } from "../../graphql/queries/objects/getObjectDisplayLabel";
import { POOLS_DICTIONNARY, POOLS_PEER } from "../../screens/ipam/constants";
import LoadingScreen from "../../screens/loading-screen/loading-screen";
import { comparedOptions } from "../../utils/array";
import { getOptionsFromRelationship } from "../../utils/getSchemaObjectColumns";
import { Tooltip } from "../ui/tooltip";

export type SelectOption = {
  id: string | number;
  name: string;
  color?: string; // For dropdown
  description?: string; // For dropdown
};

export enum SelectDirection {
  OVER,
}

type SelectProps = {
  value?: string | string[] | number | number[];
  kind?: string;
  name?: string;
  peer?: string;
  options: SelectOption[];
  onChange: (value: any) => void;
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
};

export const Select = (props: SelectProps) => {
  const {
    options,
    value,
    onChange,
    disabled,
    error,
    direction,
    peer,
    preventObjectsCreation,
    multiple,
    dropdown,
    enum: enumBoolean,
    field,
    schema,
    preventEmpty,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars, no-unused-vars
    isOptional, // Avoid proving useless props
    // eslint-disable-next-line @typescript-eslint/no-unused-vars, no-unused-vars
    isUnique, // Avoid proving useless props
    ...otherProps
  } = props;

  const { kind } = props;

  const { checkSchemaUpdate } = useContext(SchemaContext);

  const schemaList = useAtomValue(schemaState);
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
  const [selectedOption, setSelectedOption] = useState(
    multiple
      ? localOptions.filter((option) => value?.list?.includes(option.id))
      : localOptions?.find((option) => option?.id === value || option.name === value)
  );

  const namespaceData = namespaces.find((n) => n.name === schema?.namespace);

  const schemaData = schemaList.find((s) => s.kind === peer);

  // Check if any kind from inheritance is one of the available for pools
  const canRequestPools = !!schemaData?.inherit_from
    ?.map((from) => POOLS_PEER.includes(from))
    ?.filter(Boolean)?.length;
  const poolPeer = canRequestPools && POOLS_DICTIONNARY[peer];

  // Query to fetch options only if a peer is defined
  // TODO: Find another solution for queries while loading schema
  const optionsQueryString = peer ? getDropdownOptions({ kind: peer }) : "query { ok }";
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

  const labelQueryString = peer ? getObjectDisplayLabel({ kind: peer }) : "query { ok }";

  const labelQuery = gql`
    ${labelQueryString}
  `;

  const [fetchLabel] = useLazyQuery(labelQuery);

  const optionsResult =
    peer && data ? data[hasBeenOpened ? peer : poolPeer]?.edges.map((edge: any) => edge.node) : [];

  const optionsList = getOptionsFromRelationship({
    options: optionsResult,
    schemas: schemaList,
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

    handleFocus();

    if (newValue.id === addOption.id) {
      setOpen(true);
      return;
    }

    if (newValue.id === emptyOption.id) {
      setSelectedOption(emptyOption);
      onChange(newValue);
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
      onChange({ list: newValue.map((item) => item.id) });

      return;
    }

    setSelectedOption(newValue);
    setQuery("");
    setOpen(false);

    if (hasPoolsBeenOpened) {
      onChange(hasPoolsBeenOpened ? { from_pool: { id: newValue.id } } : { id: newValue.id });
      return;
    }

    if (dropdown || enumBoolean) {
      onChange(newValue.id);
      return;
    }

    onChange({ id: newValue.id });
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

    setHasPoolsBeenOpened(false);
    setHasBeenOpened(true);
    fetchOptions();
  };

  const handleFocusPools = () => {
    // Do not fetch if there is no peer
    if (!poolPeer || hasPoolsBeenOpened) return;

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
    const fields = [
      {
        name: "value",
        label: "Name",
        value: "",
        type: "text",
        config: {
          required: "Required",
        },
      },
      {
        name: "color",
        label: "Color",
        value: "",
        type: "color",
        isOptional: true,
      },
      {
        name: "label",
        label: "Label",
        value: "",
        type: "text",
        isOptional: true,
      },
      {
        name: "description",
        label: "Description",
        value: "",
        type: "text",
        isOptional: true,
      },
    ];

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
      <Form fields={fields} onSubmit={handleSubmit} onCancel={handleCancel} isLoading={isLoading} />
    );
  };

  const renderContentForEnum = () => {
    const fields = [
      {
        name: "value",
        label: "Value",
        value: "",
        type: kind === "Number" ? "number" : "text",
        config: {
          required: "Required",
        },
      },
    ];

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
      <Form fields={fields} onSubmit={handleSubmit} onCancel={handleCancel} isLoading={isLoading} />
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
    if (!namespaceData?.user_editable) {
      return null;
    }

    if (peer && !preventObjectsCreation) {
      return (
        <Combobox.Option
          value={addOption}
          className={({ active }) =>
            classNames(
              "relative cursor-pointer select-none py-2 pl-3 pr-9 m-2 rounded-md",
              active ? "bg-custom-blue-600 text-custom-white" : "bg-gray-100 text-gray-900"
            )
          }>
          <span className={"truncate flex items-center"}>
            <Icon icon={"mdi:plus"} /> Add {schemaKindName[peer]}
          </span>
        </Combobox.Option>
      );
    }

    if (dropdown || enumBoolean) {
      return (
        <Combobox.Option
          value={addOption}
          className={({ active }) =>
            classNames(
              "flex relative cursor-pointer select-none py-2 pl-3 pr-9 m-2 rounded-md",
              active ? "bg-custom-blue-600 text-custom-white" : "bg-gray-100 text-gray-900"
            )
          }>
          <span className={"truncate flex items-center"}>
            <Icon icon={"mdi:plus"} /> Add option
          </span>
        </Combobox.Option>
      );
    }

    return null;
  };

  const getOptionContent = () => {
    if (!namespaceData?.user_editable) {
      return;
    }

    if (peer && !preventObjectsCreation) {
      return (
        <SlideOver
          title={
            <div className="space-y-2">
              <div className="flex items-center w-full">
                <span className="text-lg font-semibold mr-3">Create {schemaData?.label}</span>
                <div className="flex-1"></div>
                <div className="flex items-center">
                  <Icon icon={"mdi:layers-triple"} />
                  <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
                </div>
              </div>

              <div className="text-sm">{schemaData?.description}</div>

              <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20 mr-2">
                <svg
                  className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                  viewBox="0 0 6 6"
                  aria-hidden="true">
                  <circle cx={3} cy={3} r={3} />
                </svg>
                {schemaData?.kind}
              </span>
            </div>
          }
          open={open}
          setOpen={setOpen}
          offset={1}>
          <ObjectItemCreate
            onCreate={handleCreate}
            onCancel={() => setOpen(false)}
            objectname={peer}
            preventObjectsCreation
          />
        </SlideOver>
      );
    }

    if (dropdown) {
      return (
        <>
          <SlideOver
            title={
              <div className="space-y-2">
                <div className="flex items-center w-full">
                  <span className="text-lg font-semibold mr-3">Create new option</span>
                  <div className="flex-1"></div>
                  <div className="flex items-center">
                    <Icon icon={"mdi:layers-triple"} />
                    <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
                  </div>
                </div>

                <div className="text-sm">{field?.description ?? field?.label}</div>

                <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20 mr-2">
                  <svg
                    className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                    viewBox="0 0 6 6"
                    aria-hidden="true">
                    <circle cx={3} cy={3} r={3} />
                  </svg>
                  {schema?.kind}
                </span>
              </div>
            }
            open={open}
            setOpen={setOpen}
            offset={1}>
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
              <div className="space-y-2">
                <div className="flex items-center w-full">
                  <span className="text-lg font-semibold mr-3">Create new option</span>
                  <div className="flex-1"></div>
                  <div className="flex items-center">
                    <Icon icon={"mdi:layers-triple"} />
                    <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
                  </div>
                </div>

                <div className="text-sm">{field?.description ?? field?.label}</div>

                <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20 mr-2">
                  <svg
                    className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                    viewBox="0 0 6 6"
                    aria-hidden="true">
                    <circle cx={3} cy={3} r={3} />
                  </svg>
                  {schema?.kind}
                </span>
              </div>
            }
            open={open}
            setOpen={setOpen}
            offset={1}>
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
    if (!selectedOption) return;

    if (peer && !multiple && !Array.isArray(selectedOption) && !selectedOption?.name) {
      const { data } = await fetchLabel({ variables: { ids: [selectedOption?.id] } });

      const label = data[peer]?.edges[0]?.node?.display_label;

      const newSelectedOption = {
        ...selectedOption,
        name: label ?? "Unkown",
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
        name: edge.node.display_label,
        id: edge.node.id,
      }));

      setSelectedOption(newSelectedOptions);
    }
  };

  useEffect(() => {
    // Avoid fetching labels if ther eis no value
    if (!value) return;

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

  return (
    <div className="relative" data-testid="select-container">
      <Combobox
        as="div"
        value={multiple ? selectedOption ?? [] : selectedOption ?? ""}
        onChange={handleChange}
        disabled={disabled}
        multiple={multiple}
        by={comparedOptions}
        {...otherProps}>
        <div className="relative">
          <div className="flex">
            <Combobox.Input
              as={multiple ? MultipleInput : Input}
              value={getInputValue()}
              onChange={handleInputChange}
              onFocus={handleFocus}
              disabled={disabled}
              error={error}
              className={"pr-8"}
              style={getInputStyle()}
              hideEmpty
              data-testid="select-input"
            />
            <Combobox.Button
              className={classNames(
                "absolute inset-y-0 flex items-center rounded-r-md px-2 focus:outline-none disabled:cursor-not-allowed",
                canRequestPools ? "right-10" : "right-0"
              )}
              data-testid="select-open-option-button"
              onClick={handleFocus}>
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
                  onClick={handleFocusPools}>
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
              )}>
              {finalOptions.map((option, index) => (
                <Combobox.Option
                  key={index}
                  value={option}
                  className="cursor-pointer select-none py-2 px-3"
                  style={getOptionStyle(option)}>
                  {({ selected }) => (
                    <div className="z-10 flex items-center gap-2">
                      <div className="grow truncate">
                        <span
                          className={classNames("block truncate", selected ? "font-semibold" : "")}>
                          {option.name}
                        </span>

                        {option.description && (
                          <span
                            className={classNames(
                              "block truncate italic text-xs",
                              selected ? "font-semibold" : ""
                            )}>
                            {option.description}
                          </span>
                        )}
                      </div>

                      {selected && (
                        <CheckIcon className="w-4 h-4 text-custom-blue-700" aria-hidden="true" />
                      )}

                      {canRemoveOption(option.id) && (
                        <Button
                          buttonType={BUTTON_TYPES.INVISIBLE}
                          className="p-0"
                          onClick={() => setOptionToDelete(option.id)}>
                          <Icon icon="mdi:trash" className="text-red-500" />
                        </Button>
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
};
