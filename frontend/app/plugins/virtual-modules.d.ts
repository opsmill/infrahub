declare module "virtual:infrahub-plugins" {
  import type { RegisteredPlugin } from "@/entities/plugins/types";

  export const plugins: RegisteredPlugin[];
  const module: { plugins: RegisteredPlugin[] };
  export default module;
}
