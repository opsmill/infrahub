import type { components } from "@/shared/api/rest/types.generated";

export type Config = components["schemas"]["ConfigAPI"];

export type FeatureFlag = keyof Config["experimental_features"];

export type SSOProvider = components["schemas"]["SSOProviderInfo"];
