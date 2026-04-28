import { EyeIcon } from "lucide-react";
import { DialogTrigger } from "react-aria-components";

import type { components } from "@/shared/api/rest/types.generated";
import { Button } from "@/shared/components/aria/button";
import { Modal } from "@/shared/components/aria/modal";
import { Row } from "@/shared/components/container";
import { DataViewer } from "@/shared/components/data-viewer/data-viewer";
import { Badge } from "@/shared/components/ui/badge";

import { SchemaKindDisplay } from "./styled";

export const ComputedAttributeDisplay = ({
  computedAttribute,
  onKindClick,
}: {
  computedAttribute?: components["schemas"]["ComputedAttribute-Output"] | null;
  onKindClick?: (kind: string) => void;
}) => {
  if (!computedAttribute) {
    return "-";
  }

  if (computedAttribute.kind === "Jinja2" && computedAttribute.jinja2_template) {
    const jinja2TemplateData = computedAttribute.jinja2_template as string;

    return (
      <Row>
        <SchemaKindDisplay kinds={["CoreTransformJinja2"]} onKindClick={onKindClick} />

        <DialogTrigger>
          <Button variant="outline" size="xs" shape="circle" data-testid="jinja2-transform-button">
            <EyeIcon className="size-3.5" />
          </Button>

          <Modal>
            <DataViewer
              title="Jinja2 Template"
              fileName="jinja2-template.txt"
              data={jinja2TemplateData}
            />
          </Modal>
        </DialogTrigger>
      </Row>
    );
  }

  if (computedAttribute.kind === "TransformPython") {
    return (
      <Row>
        <SchemaKindDisplay kinds={["CoreTransformPython"]} onKindClick={onKindClick} />

        <Badge variant="gray-outline">{computedAttribute.transform as string}</Badge>
      </Row>
    );
  }

  return null;
};
