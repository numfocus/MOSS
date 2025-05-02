// frontend/src/components/Layout.tsx ---

import React from 'react';
import { Outlet, Link, NavLink } from 'react-router-dom';
import './Layout.css';

const Layout: React.FC = () => {
  return (
    <div className="app-layout">
      <header className="app-header">
        <h1><Link to="/">MOSS</Link></h1>
        <nav className="app-nav">
          <ul>
            <li><NavLink to="/" className={({ isActive }) => isActive ? "active-link" : ""}>Home</NavLink></li>
            <li><NavLink to="/ingest" className={({ isActive }) => isActive ? "active-link" : ""}>Ingest</NavLink></li>
            <li><NavLink to="/search" className={({ isActive }) => isActive ? "active-link" : ""}>Search</NavLink></li>
            <li><NavLink to="/shared-queries" className={({ isActive }) => isActive ? "active-link" : ""}>Shared Queries</NavLink></li>
          </ul>
        </nav>
      </header>

      <main className="app-content">
        <Outlet />
      </main>

      <footer className="app-footer">
        <p>© {new Date().getFullYear()} MOSS Project</p>
      </footer>
    </div>
  );
};

export default Layout;