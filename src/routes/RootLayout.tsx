import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { Outlet } from "@tanstack/react-router";
import AppSidebar from "@/components/SideBar";
import DBStatus from "@/components/dbstatus/DBStatus";
import DarkModeToggle from "@/components/DarkModeToggle";

export function RootLayout() {
  return (
    <div className="App min-h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100">
      <header className="bg-white dark:bg-gray-800 shadow p-4 mb-4 flex justify-between items-center">
        <h1 className="text-xl font-semibold">Mapping</h1>
        <DarkModeToggle />
      </header>
      <SidebarProvider>
        <AppSidebar />
        <main className="container mx-auto px-0 md:pl-[var(--sidebar-width)] peer-data-[collapsible=icon]:md:pl-[var(--sidebar-width-icon)] transition-[padding] duration-200 ease-linear">
          <SidebarTrigger className="md:hidden fixed top-4 right-4 z-20" />
          <Outlet />
        </main>
        <DBStatus />

      </SidebarProvider>
      <footer className="text-center p-4 mt-8 text-xs text-gray-500"></footer>
    </div>
  );
}
