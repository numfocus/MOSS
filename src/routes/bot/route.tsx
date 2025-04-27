import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "@/router";
import DataWorker from "./DataWorker";

export const botRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/bot",
  component: DataWorker,
});
