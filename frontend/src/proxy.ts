import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

// Public routes — accessible without login
const isPublicRoute = createRouteMatcher([
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api(.*)",
]);

export default clerkMiddleware(
  async (auth, request) => {
    if (!isPublicRoute(request)) {
      await auth.protect();
    }
  },
  {
    // Giriş yapmamış kullanıcı, uygulamanın KENDİ Türkçe giriş sayfasına gitsin.
    // Bu ayar olmadan middleware signInUrl'i çözemiyor ve kullanıcıyı Clerk'in
    // barındırdığı İngilizce hesap portalına (accounts.dev) atıyordu — yani
    // providers.tsx'teki Türkçe özelleştirme hiç görünmüyordu.
    // ClerkProvider'ın signInUrl prop'u yalnızca istemci tarafında geçerli;
    // middleware onu görmüyor, bu yüzden burada ayrıca verilmesi gerekiyor.
    signInUrl: "/sign-in",
  },
);

export const config = {
  matcher: [
    // Skip Next.js internals and static files.
    // manifest.json açıkça muaf: desendeki `js(?!on)` .json'u muaf tutmuyor,
    // bu yüzden middleware manifesti yakalayıp 404'e yeniden yazıyordu.
    // Tarayıcı manifesti çerezsiz istediği için giriş yapmış kullanıcıda bile kırıktı.
    "/((?!_next|manifest\.json|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // Always run for API routes
    "/(api|trpc)(.*)",
  ],
};
