import "./App.css";
import Layout from "./screens/layout/layout";

export function classNames(...classes: string[]) {
  return classes.filter(Boolean).join(" ");
}

function App() {
  return <Layout />;
}

export default App;
