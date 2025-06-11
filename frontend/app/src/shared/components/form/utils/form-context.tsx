import { NodeObject } from "@/entities/nodes/types";
import { NodeSchema } from "@/entities/schema/types";
import { ReactNode, createContext } from "react";

export interface FormContextType {
  parentSchema: NodeSchema | null;
  parentData: NodeObject | null;
}

export interface FormContextProps extends FormContextType {
  children: ReactNode;
}

export const FormContext = createContext<FormContextType>({
  parentSchema: null,
  parentData: null,
});

export const FormContextProvider = ({ children, parentSchema, parentData }: FormContextProps) => {
  const value = {
    parentSchema,
    parentData,
  };

  return <FormContext value={value}>{children}</FormContext>;
};
