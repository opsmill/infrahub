import { Card, CardContent } from "@infrahub/ui";
import { useState } from "react";
import { useNavigate } from "react-router";

import { Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { DynamicField } from "@/shared/components/form/dynamic-form";
import type { FormFieldValue } from "@/shared/components/form/type";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Form, FormSubmit } from "@/shared/components/ui/form";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import { useGetNumberPools } from "@/entities/resource-manager/ui/queries/get-number-pools.query";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { getTemplateRelationshipFromSchema } from "@/entities/schema/domain/rules/get-template-relationship-from-schema";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import type { ServiceCatalogEntry } from "@/entities/service-portal/domain/model/service-catalog";
import {
  mapSubmitErrors,
  type SubmitErrors,
} from "@/entities/service-portal/domain/rules/map-submit-errors";
import { pickAllowlistedFields } from "@/entities/service-portal/domain/rules/pick-allowlisted-fields";
import { useSubmitServiceRequest } from "@/entities/service-portal/ui/queries/submit-service-request.mutation";
import { getServiceRequestUrl } from "@/entities/service-portal/ui/routing/service-portal-urls";

interface ServiceOrderFormProps {
  entry: ServiceCatalogEntry;
}

export function ServiceOrderForm({ entry }: ServiceOrderFormProps) {
  const { schema } = useSchema(entry.target_kind);
  const templateKind = schema ? getTemplateRelationshipFromSchema(schema)?.peer : undefined;
  const { schema: templateSchema } = useSchema(templateKind);

  if (!schema) {
    return (
      <NoDataFound message="This service can't be ordered right now. Please contact your administrator." />
    );
  }

  if (entry.template_id && templateSchema) {
    return (
      <TemplatedOrderForm
        entry={entry}
        schema={schema}
        templateSchema={templateSchema}
        templateId={entry.template_id}
      />
    );
  }

  return <OrderForm entry={entry} schema={schema} template={null} />;
}

interface TemplatedOrderFormProps extends ServiceOrderFormProps {
  schema: ModelSchema;
  templateSchema: ModelSchema;
  templateId: string;
}

// The backend applies the template to the created service; here it only pre-fills visible fields.
function TemplatedOrderForm({
  entry,
  schema,
  templateSchema,
  templateId,
}: TemplatedOrderFormProps) {
  const {
    data: template,
    isPending,
    error,
  } = useGetObject({
    objectSchema: templateSchema,
    objectId: templateId,
    getAttributesVisible: (attributes) => attributes,
    getRelationshipsVisible: (relationships) => relationships,
  });

  if (isPending) return <LoadingIndicator className="my-4" />;
  if (error) return <ErrorScreen message={error.message} />;

  return <OrderForm entry={entry} schema={schema} template={template} />;
}

interface OrderFormProps extends ServiceOrderFormProps {
  schema: ModelSchema;
  template: NodeObject | null;
}

function OrderForm({ entry, schema, template }: OrderFormProps) {
  const auth = useAuth();
  const navigate = useNavigate();
  const submitServiceRequest = useSubmitServiceRequest();
  const [submitErrors, setSubmitErrors] = useState<SubmitErrors | null>(null);
  const { data: numberPools, isPending } = useGetNumberPools({
    objectKinds: [schema.kind!, ...(("inherit_from" in schema && schema.inherit_from) || [])],
  });

  if (isPending) return <LoadingIndicator className="my-4" />;

  const fields = pickAllowlistedFields(
    getFormFieldsFromSchema({
      schema,
      objectTemplate: template,
      auth,
      // The portal always works on the default branch
      isDefaultBranch: true,
      pools: numberPools,
    }),
    entry.fields
  );

  const defaultValues = Object.fromEntries(fields.map((field) => [field.name, field.defaultValue]));

  async function onSubmit(formData: Record<string, FormFieldValue>) {
    setSubmitErrors(null);
    try {
      // Without a template id the create-input builder leaves `object_template` out: the backend
      // applies the entry's template itself. Template values the user didn't touch are skipped.
      const inputs = getCreateMutationFromFormData(fields, formData);
      const { requestId } = await submitServiceRequest.mutateAsync({ entryId: entry.id, inputs });
      navigate(getServiceRequestUrl(requestId));
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "The request could not be submitted.";
      setSubmitErrors(
        mapSubmitErrors(
          message,
          fields.map((field) => field.name)
        )
      );
    }
  }

  return (
    <Card>
      <CardContent>
        <Form onSubmit={onSubmit} defaultValues={defaultValues}>
          {submitErrors?.formError && (
            <p role="alert" className="rounded-md bg-red-50 p-2 text-red-700 text-sm">
              {submitErrors.formError}
            </p>
          )}

          {fields.map((field) => (
            <div key={field.name}>
              <DynamicField {...field} />
              {submitErrors?.fieldErrors[field.name] && (
                <p role="alert" className="mt-1 text-red-600 text-sm">
                  {submitErrors.fieldErrors[field.name]}
                </p>
              )}
            </div>
          ))}

          <Row className="justify-end">
            <FormSubmit>Submit request</FormSubmit>
          </Row>
        </Form>
      </CardContent>
    </Card>
  );
}
