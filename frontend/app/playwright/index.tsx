import { beforeMount } from "@playwright/experimental-ct-react/hooks";
import { Slide, ToastContainer } from "react-toastify";

import "../src/styles/index.css";
import "react-toastify/dist/ReactToastify.css";

beforeMount(async ({ App }) => {
  return (
    <>
      <ToastContainer
        hideProgressBar={true}
        transition={Slide}
        autoClose={5000}
        closeOnClick={false}
        newestOnTop
        position="bottom-right"
      />
      <App />
    </>
  );
});
