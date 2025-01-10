import { Form, FormProps, FormSubmit } from "@/shared/components/ui/form";

export const TestForm = ({ children, onSubmit = () => {}, ...props }: FormProps) => (
  <Form onSubmit={onSubmit} {...props}>
    {children}
    <FormSubmit>Submit</FormSubmit>
  </Form>
);
