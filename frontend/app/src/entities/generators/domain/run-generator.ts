import {
  type RunGeneratorFromApiParams,
  runGeneratorFromApi,
} from "@/entities/generators/api/run-generator-from-api";

export type RunGeneratorParams = RunGeneratorFromApiParams;

export type RunGenerator = (params: RunGeneratorParams) => Promise<{ taskId: string }>;

export const runGenerator: RunGenerator = async (params) => {
  const { data } = await runGeneratorFromApi(params);

  return { taskId: data.CoreGeneratorDefinitionRun.task.id };
};
