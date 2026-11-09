import {
  type GetObjectConvertFieldsMappingFromApiParams,
  getObjectConvertFieldsMappingFromApi,
} from "@/entities/nodes/convert/api/get-object-convert-fields-mapping-from-api";

export type GetObjectConvertFieldsMappingParams = GetObjectConvertFieldsMappingFromApiParams;

export const GetObjectConvertFieldsMapping = async (
  params: GetObjectConvertFieldsMappingParams
) => {
  const { data, errors } = await getObjectConvertFieldsMappingFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data.FieldsMappingTypeConversion?.mapping ?? {};
};
