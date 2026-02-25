import { SignIn } from "@clerk/nextjs";
import AuthLayout from "@/components/auth-layout";
import { clerkAppearance } from "@/lib/clerk-appearance";

export default function SignInPage() {
  return (
    <AuthLayout subtitle="Otomatik ders kayıt aracına giriş yap">
      <SignIn appearance={clerkAppearance} />
    </AuthLayout>
  );
}
