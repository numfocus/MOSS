import { createRoute, createRootRoute } from "@tanstack/react-router";
import Dashboard from "@/Dashboard";
import { schemaRoute } from "@/routes/schema/route";
import { viewRoute } from "@/routes/view/route";
import { botRoute } from "@/routes/bot/route";
import { devRoute } from "@/routes/dev/route";
import { RootLayout } from "./routes/RootLayout";

const ErrorComponent = () => {
  return (
    <div>
      <h1>Oops! Something went wrong.</h1>
    </div>
  );
};

export const rootRoute = createRootRoute({
  component: RootLayout,
  errorComponent: ErrorComponent,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: Dashboard,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  viewRoute,
  schemaRoute,
  botRoute,
  devRoute,
]);
export default routeTree;
