import { useSearchParams } from "react-router";

import {
  type LabelChoices,
  MAPPED_LABEL,
} from "@/entities/rack-elevation/domain/model/label-choice";

const PARAMS: Record<keyof LabelChoices, string> = {
  rack: "rack_label",
  item: "label",
  subtitle: "subtitle",
};

export function useLabelChoices() {
  const [searchParams, setSearchParams] = useSearchParams();

  const choices: LabelChoices = {
    rack: searchParams.get(PARAMS.rack) ?? MAPPED_LABEL,
    item: searchParams.get(PARAMS.item) ?? MAPPED_LABEL,
    subtitle: searchParams.get(PARAMS.subtitle) ?? MAPPED_LABEL,
  };

  const setChoices = (next: LabelChoices) => {
    setSearchParams(
      (current) => {
        const params = new URLSearchParams(current);
        for (const [key, param] of Object.entries(PARAMS) as [keyof LabelChoices, string][]) {
          if (next[key] === MAPPED_LABEL) params.delete(param);
          else params.set(param, next[key]);
        }
        return params;
      },
      { replace: true }
    );
  };

  return { choices, setChoices };
}
