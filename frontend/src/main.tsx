// --- FILE: frontend/src/main.tsx ---
// (Providing the complete file updated for Task 9.3)

import React from 'react';
import ReactDOM from 'react-dom/client';
// --- Use createBrowserRouter for modern React Router ---
import { createBrowserRouter, RouterProvider, RouteObject } from 'react-router-dom';

// --- Core Components ---
import Layout from './components/Layout.tsx';

// --- Page Components ---
import IngestPage from './pages/IngestPage.tsx';
import RepositoryDetailPage from './pages/RepositoryDetailPage.tsx';
import WorkDetailPage from './pages/WorkDetailPage.tsx';
import PersonDetailPage from './pages/PersonDetailPage.tsx';
import InstitutionDetailPage from './pages/InstitutionDetailPage.tsx';
import SearchPage from './pages/SearchPage.tsx';
import SharedQueriesPage from './pages/SharedQueriesPage.tsx'; // <-- Import SharedQueriesPage (Added in Task 9.3)

// Placeholder for HomePage (can be expanded)
const HomePage = () => (
  <div>
    <h2>Welcome to MOSS</h2>
    <p>Use the navigation to ingest data, search, or run shared queries.</p>
  </div>
);
const NotFoundPage = () => <h2>404 - Page Not Found</h2>;

// --- Global Styles ---
import './index.css';

// --- Define routes using RouteObject[] for createBrowserRouter ---
const routes: RouteObject[] = [
  {
    path: '/',
    element: <Layout />, // Main layout wraps all pages
    children: [
      { index: true, element: <HomePage /> }, // Home page at root
      { path: 'ingest', element: <IngestPage /> },
      { path: 'repositories/:id', element: <RepositoryDetailPage /> },
      { path: 'works/:id', element: <WorkDetailPage /> },
      { path: 'persons/:id', element: <PersonDetailPage /> },
      { path: 'institutions/:id', element: <InstitutionDetailPage /> },
      { path: 'search', element: <SearchPage /> },
      // --- ADD SHARED QUERIES ROUTE (Added in Task 9.3) ---
      { path: 'shared-queries', element: <SharedQueriesPage /> },
      // --- END SHARED QUERIES ROUTE ---
      { path: '*', element: <NotFoundPage /> } // Catch-all 404 route
    ],
  },
];

// Create the router instance
const router = createBrowserRouter(routes);

// Render the application
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {/* Use RouterProvider with the created router */}
    <RouterProvider router={router} />
  </React.StrictMode>,
);