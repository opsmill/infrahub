import {
  type PlaceRackItemFromApiParams,
  placeRackItemFromApi,
} from "@/entities/rack-elevation/api/place-rack-item-from-api";

export type PlaceRackItemParams = PlaceRackItemFromApiParams;
export type PlaceRackItemResult = Awaited<
  ReturnType<typeof placeRackItemFromApi>
>["data"]["RackElevationPlace"];

export const placeRackItem = async (params: PlaceRackItemParams): Promise<PlaceRackItemResult> => {
  const { data, errors } = await placeRackItemFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data.RackElevationPlace;
};
