import type React from "react";

import { Col, Row } from "@/shared/components/container";
import { Form, FormSubmit } from "@/shared/components/ui/form";

import {
  type FilterCondition,
  FilterConditionSelect,
  type FilterConditionSelectProps,
} from "@/entities/nodes/object/ui/filters/filter-condition-select";

interface FilterFormLayoutProps {
  filterType: FilterConditionSelectProps["filterType"];
  condition: FilterCondition;
  onConditionChange: (condition: FilterCondition) => void;
  testId: string;
  onSubmit: (formData: Record<string, unknown>) => void;
  children?: React.ReactNode;
  label?: React.ReactNode;
}

export function FilterFormLayout({
  filterType,
  condition,
  onConditionChange,
  testId,
  onSubmit,
  children,
  label,
}: FilterFormLayoutProps) {
  return (
    <Col className="max-h-[inherit] overflow-hidden p-2">
      <Row className="shrink-0 gap-0">
        <span className="font-semibold text-sm">{label}</span>
        <FilterConditionSelect
          filterType={filterType}
          value={condition}
          onChange={(key) => onConditionChange(key as FilterCondition)}
        />
      </Row>

      <Form
        className="inline-flex min-h-0 flex-col gap-0 space-y-2"
        onSubmit={(formData) => onSubmit(formData as Record<string, unknown>)}
        data-testid={testId}
      >
        {children}
        <FormSubmit size="sm" className="shrink-0 self-end">
          Apply
        </FormSubmit>
      </Form>
    </Col>
  );
}
