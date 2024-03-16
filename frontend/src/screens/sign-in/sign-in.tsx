import logoImage from "../../images/Infrahub-SVG-verti.svg";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import { Form } from "../edit-form-hook/form";
import LoadingScreen from "../loading-screen/loading-screen";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

export default function SignIn() {
  let navigate = useNavigate();
  let location = useLocation();
  const { isLoading, signIn } = useAuth();

  const from = location.state?.from?.pathname || "/";

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
      <div className="flex h-full justify-center items-center bg-gray-200">
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

                {!isLoading && (
                  <Form
                    fields={fields}
                    submitLabel="Sign in"
                    onSubmit={(data) => signIn(data, () => navigate(from))}
                  />
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
