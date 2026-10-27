"use client";

import { PageTransition } from "@/components/ui/PageTransition";
import { InspiredDashboard } from "@/components/dashboard/InspiredDashboard";

export default function Home() {
  return (
    <PageTransition>
      <InspiredDashboard />
    </PageTransition>
  );
}
