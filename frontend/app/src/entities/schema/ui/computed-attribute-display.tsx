import { EyeIcon } from "lucide-react";
import { DialogTrigger, Pressable } from "react-aria-components";

import type { components } from "@/shared/api/rest/types.generated";
import { Modal } from "@/shared/components/aria/modal";
import { Row } from "@/shared/components/container";
import { DataViewer } from "@/shared/components/data-viewer/data-viewer";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";

import { ModelDisplay } from "./styled";

export const ComputedAttributeDisplay = ({
  computedAttribute,
}: {
  computedAttribute?: components["schemas"]["ComputedAttribute-Output"] | null;
}) => {
  if (!computedAttribute) {
    return "-";
  }

  if (computedAttribute.kind === "Jinja2" && computedAttribute.jinja2_template) {
    const jinja2TemplateData = computedAttribute.jinja2_template as string;

    return (
      <Row>
        <ModelDisplay kinds={["CoreTransformJinja2"]} />

        <DialogTrigger>
          <Pressable>
            <Button variant="outline" size="icon" data-testid="jinja2-transform-button">
              <EyeIcon className="size-3.5" />
            </Button>
          </Pressable>

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
        <ModelDisplay kinds={["CoreTransformPython"]} />

        <Badge variant="gray-outline">{computedAttribute.transform as string}</Badge>
      </Row>
    );
  }

  return null;
};
