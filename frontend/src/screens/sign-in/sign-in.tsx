import DynamicForm from "@/components/form/dynamic-form";
import { DynamicFieldProps } from "@/components/form/fields/common";
import { Card } from "@/components/ui/card";
import { SCHEMA_ATTRIBUTE_KIND } from "@/config/constants";
import { useAuth } from "@/hooks/useAuth";
import Content from "@/screens/layout/content";
import { useLocation, useNavigate } from "react-router-dom";
import { ReactComponent as InfrahubLogo } from "../../images/Infrahub-SVG-verti.svg";

const fields: Array<DynamicFieldProps> = [
  {
    name: "username",
    label: "Username",
    type: SCHEMA_ATTRIBUTE_KIND.TEXT,
    rules: {
      required: true,
    },
  },
  {
    name: "password",
    label: "Password",
    type: SCHEMA_ATTRIBUTE_KIND.PASSWORD,
    rules: {
      required: true,
    },
  },
];

export default function SignIn() {
  let navigate = useNavigate();
  let location = useLocation();
  const { signIn } = useAuth();

  const from = (location.state?.from?.pathname || "/") + (location.state?.from?.search ?? "");

  return (
    <Content className="flex justify-center items-center bg-gray-200 p-2">
      <Card className="w-full max-w-lg shadow">
        <div className="flex flex-col items-center p-8">
          <InfrahubLogo className="h-28 w-28" alt="Intrahub logo" />

          <h2 className="my-8 text-2xl font-semibold text-gray-900">Sign in to your account</h2>

          <DynamicForm
            className="w-full"
            fields={fields}
            onSubmit={async (data) => {
              await signIn(data, () => navigate(from));
            }}
            submitLabel="Sign in"
          />
        </div>
      </Card>
    </Content>
  );
}
