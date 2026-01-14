import {
  type RunGeneratorFromApiParams,
  runGeneratorFromApi,
} from "@/entities/generators/api/run-generator-from-api";

export type RunGeneratorParams = RunGeneratorFromApiParams;

export type RunGenerator = (params: RunGeneratorParams) => Promise<{ taskId: string }>;

export const runGenerator: RunGenerator = async (params) => {
  const { data, errors } = await runGeneratorFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const taskId = data?.CoreGeneratorDefinitionRun?.task?.id;
  if (!taskId) {
    throw new Error("No task returned");
  }

  return { taskId };
};
