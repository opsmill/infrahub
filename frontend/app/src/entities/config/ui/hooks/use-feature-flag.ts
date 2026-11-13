import type { FeatureFlag } from "@/entities/config/domain/model/config";
import { useConfig } from "@/entities/config/ui/config-provider";

export function useFeatureFlag(flag: FeatureFlag): boolean {
  const config = useConfig();

  return config.experimental_features?.[flag] ?? false;
}
