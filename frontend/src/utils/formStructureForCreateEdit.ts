import { parseISO } from "date-fns";
import { SelectOption } from "../components/select";
import { iPeerDropdownOptions } from "../graphql/queries/objects/dropdownOptionsForRelatedPeers";
import {
  ControlType,
  DynamicFieldData,
  getFormInputControlTypeFromSchemaAttributeKind,
  SchemaAttributeType,
} from "../screens/edit-form-hook/dynamic-control-types";
import { iGenericSchema, iNodeSchema } from "../state/atoms/schema.atom";

const getIsDisabled = (owner?: any, user?: any, isProtected?: boolean) => {
  // Field is available if there is no owner and if is_protected is not set to true
  if (!isProtected || !owner || user?.permissions?.isAdmin) return false;

  // Field is available only if is_protected is set to true and if the owner is the user
  return owner?.id !== user?.data?.sub;
};

const getFieldValue = (row: any, attribute: any) => {
  const value = row && row[attribute.name] ? row[attribute.name].value : attribute.default_value;

  if (attribute.kind === "DateTime") {
    return parseISO(value);
  }

  return value;
};

const validate = (value: any, defaultValue?: any, optional?: boolean) => {
  // If optionnal, no validator is needed (we try to validate if the value is defined or not)
  if (optional) {
    return true;
  }

  // The value is defined, then we can validate
  if (value) {
    return true;
  }

  // If the value is false but itso is the default_value, then validate (checkbox example)
  if (defaultValue !== undefined && value === defaultValue) {
    return true;
  }

  // No value and the value is not the default_value, then mark as required
  return "Required";
};

const getFormStructureForCreateEdit = (
  schema: iNodeSchema,
  schemas: iNodeSchema[],
  generics: iGenericSchema[],
  dropdownOptions: iPeerDropdownOptions,
  row?: any,
  user?: any
): DynamicFieldData[] => {
  if (!schema) {
    return [];
  }

  const formFields: DynamicFieldData[] = [];

  schema.attributes?.forEach((attribute) => {
    let options: SelectOption[] = [];

    if (attribute.enum) {
      options = attribute.enum?.map((row: any) => ({
        name: row,
        id: row,
      }));
    }

    formFields.push({
      name: attribute.name + ".value",
      kind: attribute.kind as SchemaAttributeType,
      type: attribute.enum
        ? "select"
        : getFormInputControlTypeFromSchemaAttributeKind(attribute.kind as SchemaAttributeType),
      label: attribute.label ? attribute.label : attribute.name,
      value: getFieldValue(row, attribute),
      options: {
        values: options,
      },
      config: {
        validate: (value: any) => validate(value, attribute.default_value, attribute.optional),
      },
      isProtected: getIsDisabled(
        row && row[attribute.name]?.owner,
        user,
        row && row[attribute.name] && row[attribute.name].is_protected
      ),
    });
  });

  // TODO: Get relationships from util function for consistency
  schema.relationships
    ?.filter(
      (relationship) =>
        relationship.cardinality === "one" ||
        relationship.kind === "Attribute" ||
        relationship.kind === "Parent"
    )
    .forEach((relationship) => {
      let options: SelectOption[] = [];

      const isInherited = generics.find((g) => g.kind === relationship.peer);

      if (!isInherited && dropdownOptions[relationship.peer]) {
        options = dropdownOptions[relationship.peer].map((row: any) => ({
          name: row.display_label,
          id: row.id,
        }));
      } else {
        const generic = generics.find((g) => g.kind === relationship.peer);
        if (generic) {
          (generic.used_by || []).forEach((name) => {
            const relatedSchema = schemas.find((s) => s.kind === name);
            if (relatedSchema) {
              options.push({
                id: name,
                name: relatedSchema.name,
              });
            }
          });
        }
      }

      formFields.push({
        name: relationship.name + (relationship.cardinality === "one" ? ".id" : ".list"),
        kind: "String",
        type:
          relationship.cardinality === "many"
            ? ("multiselect" as ControlType)
            : isInherited
            ? "select2step"
            : ("select" as ControlType),
        label: relationship.label ? relationship.label : relationship.name,
        value: (() => {
          if (!row || !row[relationship.name]) {
            return "";
          }

          const value = row[relationship.name].node ?? row[relationship.name];

          if (relationship.cardinality === "one" && !isInherited) {
            return value.id;
          } else if (relationship.cardinality === "one" && isInherited) {
            return value;
          } else if (value.edges) {
            return value.edges.map((item: any) => item?.node?.id);
          } else if (value.node) {
            return value.node.map((item: any) => item?.node?.id);
          }

          return "";
        })(),
        options: {
          values: options,
        },
        config: {
          validate: (value: any) => validate(value, null, relationship.optional),
        },
        isProtected: getIsDisabled(
          row && row[relationship.name]?.properties?.owner,
          user,
          row && row[relationship.name] && row[relationship.name]?.properties?.is_protected
        ),
      });
    });

  return formFields;
};

export default getFormStructureForCreateEdit;

export const getFormStructureForMetaEdit = (
  row: any,
  type: "attribute" | "relationship",
  schemaList: iNodeSchema[]
): DynamicFieldData[] => {
  const sourceOwnerFields =
    type === "attribute" ? ["owner", "source"] : ["_relation__owner", "_relation__source"];

  const booleanFields =
    type === "attribute"
      ? ["is_visible", "is_protected"]
      : ["_relation__is_visible", "_relation__is_protected"];

  const relatedObjects: { [key: string]: string } = {
    source: "DataSource",
    owner: "DataOwner",
    _relation__source: "DataSource",
    _relation__owner: "DataOwner",
  };

  const sourceOwnerFormFields: DynamicFieldData[] = sourceOwnerFields.map((f) => {
    const schemaOptions: SelectOption[] = [
      ...schemaList
        .filter((schema) => {
          if ((schema.inherit_from || []).indexOf(relatedObjects[f]) > -1) {
            return true;
          } else {
            return false;
          }
        })
        .map((schema) => ({
          name: schema.kind,
          id: schema.name,
        })),
    ];

    return {
      name: f,
      kind: "Text",
      isAttribute: false,
      isRelationship: false,
      type: "select2step",
      label: f
        .split("_")
        .filter((r) => !!r)
        .join(" "),
      value: row?.[f],
      options: {
        values: schemaOptions,
      },
      config: {},
    };
  });

  const booleanFormFields: DynamicFieldData[] = booleanFields.map((f) => {
    return {
      name: f,
      kind: "Checkbox",
      isAttribute: false,
      isRelationship: false,
      type: "checkbox",
      label: f
        .split("_")
        .filter((r) => !!r)
        .join(" "),
      value: row?.[f],
      options: {
        values: [],
      },
      config: {},
    };
  });

  return [...sourceOwnerFormFields, ...booleanFormFields];
};

export const getFormStructureForMetaEditPaginated = (
  row: any,
  schemaList: iNodeSchema[]
): DynamicFieldData[] => {
  const sourceOwnerFields = ["owner", "source"];

  const booleanFields = ["is_visible", "is_protected"];

  const relatedObjects: { [key: string]: string } = {
    source: "LineageSource",
    owner: "LineageOwner",
    _relation__source: "LineageSource",
    _relation__owner: "LineageOwner",
  };

  const sourceOwnerFormFields: DynamicFieldData[] = sourceOwnerFields.map((field) => {
    const schemaOptions: SelectOption[] = [
      ...schemaList
        .filter((schema) => {
          if ((schema.inherit_from || []).indexOf(relatedObjects[field]) > -1) {
            return true;
          } else {
            return false;
          }
        })
        .map((schema) => ({
          name: schema.name,
          id: schema.kind,
        })),
    ];

    return {
      name: field,
      kind: "Text",
      isAttribute: false,
      isRelationship: false,
      type: "select2step",
      label: field.split("_").filter(Boolean).join(" "),
      value: row?.[field],
      options: {
        values: schemaOptions,
      },
      config: {},
    };
  });

  const booleanFormFields: DynamicFieldData[] = booleanFields.map((field) => {
    return {
      name: field,
      kind: "Checkbox",
      isAttribute: false,
      isRelationship: false,
      type: "checkbox",
      label: field.split("_").filter(Boolean).join(" "),
      value: row?.[field],
      options: {
        values: [],
      },
      config: {},
    };
  });

  return [...sourceOwnerFormFields, ...booleanFormFields];
};
