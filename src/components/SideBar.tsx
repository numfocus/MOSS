import { Home, Database, Bot, LucideTowerControl, Calendar } from "lucide-react";
import { Link, useRouteContext } from "@tanstack/react-router";

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

import { useMemo } from "react";
import React from "react";

const AppSidebar = () => {
  const { route } = useRouteContext({
    from: undefined
  });
  const items = useMemo(() => [
    { title: "Home", url: "/", icon: Home },
    { title: "Schema Manager", url: "/schema/", icon: Calendar },
    { title: "View", url: "/view/", icon: Database },
    { title: "Data Worker", url: "/bot/", icon: Bot },
    { title: "Dev Tools", url: "/dev/", icon: LucideTowerControl },
  ], [ ]);


  return (
    <Sidebar>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Application</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild isActive={route?.id === item.url}>
                    <Link to={item.url}>
                      <item.icon />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}

export default React.memo(AppSidebar);
