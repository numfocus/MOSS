import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider, createRouter } from "@tanstack/react-router";
import { SurrealProvider } from "./contexts/SurrealProvider";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./index.css";
import routeTree from "./router";

const queryClient = new QueryClient();
const root = ReactDOM.createRoot(document.getElementById("root")!);
const endpoint = import.meta.env.VITE_SURREAL_URL || "indxdb://demo";
const namespace = import.meta.env.VITE_SURREAL_NS || "test";
const database = import.meta.env.VITE_SURREAL_DB || "test";

const router = createRouter({
  routeTree,
})


root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <SurrealProvider
        endpoint={endpoint}
        namespace={namespace}
        database={database}
      >
        <RouterProvider router={router} />
      </SurrealProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);