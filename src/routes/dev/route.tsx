import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "@/router";
import DevTools from "./DevTools";

export const devRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/dev",
  component: DevTools,
});
