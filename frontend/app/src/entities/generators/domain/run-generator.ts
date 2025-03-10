import {
  RunGeneratorFromApiParams,
  runGeneratorFromApi,
} from "@/entities/generators/api/run-generator-from-api";

export type RunGeneratorParams = RunGeneratorFromApiParams;

export type RunGenerator = (params: RunGeneratorParams) => Promise<void>;

export const runGenerator: RunGenerator = async (params) => {
  await runGeneratorFromApi(params);
};
