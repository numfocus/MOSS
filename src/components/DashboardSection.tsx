// src/components/DashboardSection.tsx
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function DashboardSection() {
  return (
    <section>
      <h2>Controls</h2>
      <Button>Get Started</Button>

      <Card>
        <CardHeader>
          <CardTitle>RepoView</CardTitle>
          <CardDescription>Repo data aquisition, integration, and visualization</CardDescription>
        </CardHeader>
        <CardContent>
          <p>Card content goes here.</p>
        </CardContent>
        <CardFooter>
          <Button>Action</Button>
        </CardFooter>
      </Card>
    </section>
  );
}
