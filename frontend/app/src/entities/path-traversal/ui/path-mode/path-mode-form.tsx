import { Button } from "@infrahub/ui";
import type { UseFormReturn } from "react-hook-form";

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
import type { PathModeFormValues } from "./use-path-mode-params";

type PathModeFormProps = {
  form: UseFormReturn<PathModeFormValues>;
  onSubmit: (values: PathModeFormValues) => void;
  isPending: boolean;
};

export function PathModeForm({ form, onSubmit, isPending }: PathModeFormProps) {
  const sourceId = form.watch("sourceId");
  const destinationId = form.watch("destinationId");

  function handleSwap() {
    form.setValue("sourceId", destinationId, { shouldDirty: true });
    form.setValue("destinationId", sourceId, { shouldDirty: true });
  }

  return (
    <Form
      form={form as unknown as UseFormReturn}
      onSubmit={(values) => onSubmit(values as PathModeFormValues)}
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

      {(sourceId || destinationId) && (
        <Button variant="ghost" onClick={handleSwap} className="w-full">
          ⇅ Swap
        </Button>
      )}

      <FormField
        name="destinationId"
        rules={{ required: "Destination is required" }}
        render={({ field }) => (
          <div className="space-y-1">
            <ObjectPicker
              label="Destination Object"
              value={(field.value as string) ?? ""}
              onChange={field.onChange}
            />
            <FormMessage />
          </div>
        )}
      />

      <Accordion type="single" collapsible>
        <AccordionItem value="advanced">
          <AccordionTrigger>Search options</AccordionTrigger>
          <AccordionContent className="space-y-3">
            <div className="flex gap-4">
              <div className="flex-1 space-y-1">
                <FormField
                  name="maxDepth"
                  rules={{
                    required: "Max depth is required",
                    min: { value: 1, message: "Must be ≥ 1" },
                    max: { value: 20, message: "Must be ≤ 20" },
                  }}
                  render={({ field }) => (
                    <>
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
                    </>
                  )}
                />
              </div>
              <div className="flex-1 space-y-1">
                <FormField
                  name="maxPaths"
                  rules={{
                    required: "Max paths is required",
                    min: { value: 1, message: "Must be ≥ 1" },
                    max: { value: 100, message: "Must be ≤ 100" },
                  }}
                  render={({ field }) => (
                    <>
                      <FormLabel>Max Paths</FormLabel>
                      <FormInput>
                        <Input
                          type="number"
                          min={1}
                          max={100}
                          value={(field.value as number) ?? ""}
                          onChange={(e) => {
                            const value = e.target.valueAsNumber;
                            field.onChange(isNaN(value) ? null : value);
                          }}
                        />
                      </FormInput>
                      <FormMessage />
                    </>
                  )}
                />
              </div>
            </div>

            <FormField
              name="kindFilter"
              render={({ field }) => (
                <KindMultiSelect
                  value={(field.value as string[]) ?? []}
                  onChange={field.onChange}
                  label="Kinds to include"
                  placeholder="Select kinds to include..."
                  filter={isVisibleNamespace}
                />
              )}
            />

            <FormField
              name="excludedKinds"
              render={({ field }) => (
                <KindMultiSelect
                  value={(field.value as string[]) ?? []}
                  onChange={field.onChange}
                  label="Kinds to exclude"
                  placeholder="Select kinds to exclude..."
                  filter={isVisibleNamespace}
                />
              )}
            />
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      <FormSubmit isPending={isPending} className="w-full">
        Find Paths
      </FormSubmit>
    </Form>
  );
}
