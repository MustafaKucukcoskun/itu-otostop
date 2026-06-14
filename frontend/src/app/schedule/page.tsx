import { ScheduleBuilder } from "@/components/schedule-builder";
import { AppNavbar } from "@/components/app-navbar";

export default function SchedulePage() {
  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <main>
        <ScheduleBuilder />
      </main>
    </div>
  );
}
