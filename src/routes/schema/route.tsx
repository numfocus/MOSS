import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "@/router";
import SchemaManager  from "./SchemaManager";

export const schemaRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/schema",
  component: SchemaManager,
});
