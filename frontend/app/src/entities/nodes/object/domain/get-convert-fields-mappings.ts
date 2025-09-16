import {
  FieldsMappingParams,
  getConvertFieldsMappingFromApi,
} from "@/entities/nodes/object/api/get-convert-fields-mappings-from-api";

export const getConvertFieldsMapping = async ({
  sourceKind,
  targetKind,
  branchName,
  atDate,
}: FieldsMappingParams) => {
  const { data, errors } = await getConvertFieldsMappingFromApi({
    sourceKind,
    targetKind,
    branchName,
    atDate,
  });
  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data?.FieldsMappingTypeConversion?.mapping ?? {};
};
