import logoImage from "../../images/logo.png";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import { Form } from "../edit-form-hook/form";
import LoadingScreen from "../loading-screen/loading-screen";

export default function SignIn(props: any) {
  const { onSubmit, isLoading } = props;

  const fields: DynamicFieldData[] = [
    {
      name: "username",
      label: "Username",
      type: "text",
      value: "",
      config: {
        required: "Required",
      },
    },
    {
      name: "password",
      label: "Password",
      type: "password",
      value: "",
    },
  ];

  return (
    <>
      <div className="flex h-screen justify-center items-center bg-gray-200">
        <div className="flex flex-col justify-center px-4 py-12 sm:px-6 lg:flex-none lg:px-20 xl:px-24 rounded-xl login-container shadow-lg bg-custom-white">
          <div className="mx-auto w-full max-w-sm lg:w-96">
            <div>
              <img className="w-28 h-auto rounded-lg m-auto" src={logoImage} alt="Your Company" />
              <h2 className="mt-8 text-2xl font-bold leading-9 tracking-tight text-gray-900 text-center">
                Sign in to your account
              </h2>
            </div>

            <div className="">
              <div className="h-[300px] flex">
                {isLoading && <LoadingScreen />}

                {!isLoading && <Form fields={fields} onSubmit={onSubmit} submitLabel={"Sign in"} />}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
