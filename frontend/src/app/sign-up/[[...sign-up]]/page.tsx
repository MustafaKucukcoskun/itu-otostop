import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <div className="min-h-screen mesh-bg flex items-center justify-center">
      <div className="grain-overlay" />
      <SignUp
        appearance={{
          elements: {
            rootBox: "relative z-10",
            card: "glass rounded-2xl ring-1 ring-border/20 shadow-2xl",
          },
        }}
      />
    </div>
  );
}
