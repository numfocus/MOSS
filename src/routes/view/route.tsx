import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "@/router";
import View from "./DataView";

export const viewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/view",
  component: View,
});
