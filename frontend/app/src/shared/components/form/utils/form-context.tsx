import { createContext, use } from "react";

import type { NodeObject } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";

export interface FormContextType {
  parentSchema?: ModelSchema | null;
  parentData?: NodeObject | null;
}

export const FormContext = createContext<FormContextType>({
  parentSchema: null,
  parentData: null,
});

export function useCurrentFormContext() {
  const context = use(FormContext);
  if (!context) {
    throw new Error("useFormContext must be used within a FormContextProvider.");
  }

  return context;
}
