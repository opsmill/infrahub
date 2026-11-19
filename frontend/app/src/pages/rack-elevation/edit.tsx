import { useParams } from "react-router";

import { MappingFormPage } from "@/entities/rack-elevation/ui/mapping-form-page";

export function Component() {
  const { mappingId } = useParams();
  return <MappingFormPage key={mappingId} mappingId={mappingId} />;
}
