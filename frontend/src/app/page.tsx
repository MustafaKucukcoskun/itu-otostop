import { Dashboard } from "@/components/dashboard";
import { PrivacyBanner } from "@/components/privacy-banner";
import { AppNavbar } from "@/components/app-navbar";

export default function Home() {
  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <main>
        <Dashboard />
      </main>
      <PrivacyBanner />
    </div>
  );
}
