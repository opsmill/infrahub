import type { UseFormReturn } from "react-hook-form";

import { Checkbox } from "@/shared/components/inputs/checkbox";
import { KindMultiSelect } from "@/shared/components/inputs/kind-multi-select";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/shared/components/ui/accordion";
import {
  Form,
  FormField,
  FormInput,
  FormLabel,
  FormMessage,
  FormSubmit,
} from "@/shared/components/ui/form";
import { Input } from "@/shared/components/ui/input";

import { ObjectPicker } from "../object-picker";
import { isVisibleNamespace } from "../utils";
import type { DependenciesModeFormValues } from "./use-dependencies-mode-params";

type DependenciesModeFormProps = {
  form: UseFormReturn<DependenciesModeFormValues>;
  onSubmit: (values: DependenciesModeFormValues) => void;
  isPending: boolean;
};

export function DependenciesModeForm({ form, onSubmit, isPending }: DependenciesModeFormProps) {
  return (
    <Form
      form={form as unknown as UseFormReturn}
      onSubmit={(values) => onSubmit(values as DependenciesModeFormValues)}
      className="p-4"
    >
      <FormField
        name="sourceId"
        rules={{ required: "Source is required" }}
        render={({ field }) => (
          <div className="space-y-1">
            <ObjectPicker
              label="Source Object"
              value={(field.value as string) ?? ""}
              onChange={field.onChange}
            />
            <FormMessage />
          </div>
        )}
      />

      <FormField
        name="targetKinds"
        rules={{
          validate: (value) => {
            const arr = value as string[];
            return (Array.isArray(arr) && arr.length > 0) || "Select at least one target kind";
          },
        }}
        render={({ field }) => (
          <div className="space-y-1">
            <KindMultiSelect
              value={(field.value as string[]) ?? []}
              onChange={field.onChange}
              label="Target kinds"
              filter={isVisibleNamespace}
            />
            <FormMessage />
          </div>
        )}
      />

      <Accordion type="single" collapsible>
        <AccordionItem value="advanced">
          <AccordionTrigger>Search options</AccordionTrigger>
          <AccordionContent className="space-y-3">
            <FormField
              name="maxDepth"
              rules={{
                required: "Max depth is required",
                min: { value: 1, message: "Must be ≥ 1" },
                max: { value: 20, message: "Must be ≤ 20" },
              }}
              render={({ field }) => (
                <div className="space-y-1">
                  <FormLabel>Max Depth</FormLabel>
                  <FormInput>
                    <Input
                      type="number"
                      min={1}
                      max={20}
                      value={(field.value as number) ?? ""}
                      onChange={(e) => {
                        const value = e.target.valueAsNumber;
                        field.onChange(isNaN(value) ? null : value);
                      }}
                    />
                  </FormInput>
                  <FormMessage />
                </div>
              )}
            />

            <FormField
              name="maxResults"
              rules={{
                required: "Max results is required",
                min: { value: 1, message: "Must be ≥ 1" },
                max: { value: 200, message: "Must be ≤ 200" },
              }}
              render={({ field }) => (
                <div className="space-y-1">
                  <FormLabel>Max Targets</FormLabel>
                  <FormInput>
                    <Input
                      type="number"
                      min={1}
                      max={200}
                      value={(field.value as number) ?? ""}
                      onChange={(e) => {
                        const value = e.target.valueAsNumber;
                        field.onChange(isNaN(value) ? null : value);
                      }}
                    />
                  </FormInput>
                  <FormMessage />
                </div>
              )}
            />

            <FormField
              name="maxPaths"
              rules={{
                required: "Max paths is required",
                min: { value: 1, message: "Must be ≥ 1" },
                max: { value: 5000, message: "Must be ≤ 5000" },
              }}
              render={({ field }) => (
                <div className="space-y-1">
                  <FormLabel>Max Paths</FormLabel>
                  <FormInput>
                    <Input
                      type="number"
                      min={1}
                      max={5000}
                      value={(field.value as number) ?? ""}
                      onChange={(e) => {
                        const value = e.target.valueAsNumber;
                        field.onChange(isNaN(value) ? null : value);
                      }}
                    />
                  </FormInput>
                  <FormMessage />
                </div>
              )}
            />

            <FormField
              name="shortestPathsOnly"
              render={({ field }) => (
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <FormInput>
                      <Checkbox
                        checked={Boolean(field.value)}
                        onChange={(e) => field.onChange(e.target.checked)}
                      />
                    </FormInput>
                    <FormLabel className="cursor-pointer">Shortest paths only</FormLabel>
                  </div>
                  <p className="text-gray-500 text-xs">
                    Only return the shortest path(s) to each target. Uncheck to return every path
                    within the max depth.
                  </p>
                </div>
              )}
            />
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      <FormSubmit isPending={isPending} className="w-full">
        Find Dependencies
      </FormSubmit>
    </Form>
  );
}
