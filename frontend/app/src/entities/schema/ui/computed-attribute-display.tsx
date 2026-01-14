import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import type { components } from "@/shared/api/rest/types.generated";
import { Button } from "@/shared/components/buttons/button-primitive";
import { DataViewer } from "@/shared/components/data-viewer/data-viewer";
import Modal from "@/shared/components/modals/modal";
import { Badge } from "@/shared/components/ui/badge";

import { ModelDisplay } from "./styled";

export const ComputedAttributeDisplay = ({
  computedAttribute,
}: {
  computedAttribute?: components["schemas"]["ComputedAttribute-Output"] | null;
}) => {
  const [isOpen, setOpen] = useState(false);

  if (!computedAttribute) {
    return "-";
  }

  if (computedAttribute.kind === "Jinja2" && computedAttribute.jinja2_template) {
    const jinja2TemplateData = computedAttribute.jinja2_template as string;

    return (
      <div className="flex items-center gap-2">
        <ModelDisplay kinds={["CoreTransformJinja2"]} />

        <Button
          variant={"active-outline"}
          size={"icon"}
          onClick={() => setOpen(true)}
          data-testid="jinja2-transform-button"
        >
          <Icon icon={"mdi:eye-outline"} />
        </Button>

        <Modal setOpen={setOpen} open={isOpen}>
          <DataViewer
            title="Jinja2 template"
            fileName="jinja2-template.txt"
            data={jinja2TemplateData}
          />
        </Modal>
      </div>
    );
  }

  if (computedAttribute.kind === "TransformPython") {
    return (
      <div className="flex items-center gap-2">
        <ModelDisplay kinds={["CoreTransformPython"]} />

        <Badge variant={"gray-outline"}>{computedAttribute.transform}</Badge>
      </div>
    );
  }

  return null;
};
