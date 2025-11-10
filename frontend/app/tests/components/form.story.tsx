import { Form, type FormProps, FormSubmit } from "../../src/shared/components/ui/form";

export const TestForm = ({ children, onSubmit = () => {}, ...props }: FormProps) => (
  <Form onSubmit={onSubmit} {...props}>
    {children}
    <FormSubmit>Submit</FormSubmit>
  </Form>
);
