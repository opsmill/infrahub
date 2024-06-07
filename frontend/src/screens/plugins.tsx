import { Suspense, lazy } from "react";

// const URL =
// "http://localhost:8000/api/file/17d4816a-25b3-4c25-368b-c514d7470277/dist/vite-project.cjs?content_type=text/javascript";
// "http://localhost:8000/api/file/17d4816a-25b3-4c25-368b-c514d7470277/dist/vite-project.umd.cjs?content_type=text/javascript";
// "http://localhost:8000/api/file/17d4816a-25b3-4c25-368b-c514d7470277/dist/vite-project.js?content_type=text/javascript";

const RemoteComponent = lazy(() => import("remoteApp/RemoteComponent"));

export const Plugins = () => {
  return (
    <div>
      <Suspense fallback={<div>Loading...</div>}>
        <RemoteComponent />
      </Suspense>
    </div>
  );
};

// export const Plugins = () => {
//   const [Component, setComponent] = useState(null);

//   useEffect(() => {
//     const url = URL;
//     import(url)
//       .then((module) => {
//         console.log("module: ", module);
//         setComponent(module);
//       })
//       .catch((error) => {
//         // Handle error
//         console.log("error: ", error);
//       });
//   }, []);

//   return Component ? <Component /> : <div>Loading...</div>;
// };
