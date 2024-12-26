import { addCollection } from "@iconify-icon/react";
import mdiIcons from "@iconify-json/mdi/icons.json";
import { beforeMount } from "@playwright/experimental-ct-react/hooks";
import { QueryClientProvider } from "@tanstack/react-query";
import { Slide, ToastContainer } from "react-toastify";
import { queryClient } from "../src/api/client";

import "../src/styles/index.css";
import "react-toastify/dist/ReactToastify.css";

addCollection(mdiIcons);

beforeMount(async ({ App }) => {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastContainer
        hideProgressBar={true}
        transition={Slide}
        autoClose={5000}
        closeOnClick={false}
        newestOnTop
        position="bottom-right"
      />
      <App />
    </QueryClientProvider>
  );
});
