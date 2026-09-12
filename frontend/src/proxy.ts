import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

// Public routes — accessible without login
const isPublicRoute = createRouteMatcher([
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api(.*)",
]);

export default clerkMiddleware(async (auth, request) => {
  if (!isPublicRoute(request)) {
    await auth.protect();
  }
});

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
