"use client";

/**
 * Skeleton placeholder shown while dashboard config is loading.
 * Uses shimmer sweep animation (`.skeleton` class from globals.css)
 * instead of Tailwind's animate-pulse for a visible, premium loading effect.
 *
 * Layout mirrors the real dashboard exactly to prevent layout shift
 * when the skeleton transitions to the real content.
 */
export function DashboardSkeleton() {
  return (
    <div className="min-h-screen mesh-bg relative">
      {/* Background layers */}
      <div className="dot-grid fixed inset-0 pointer-events-none z-0" />
      <div className="mesh-orb-accent" />
      <div className="grain-overlay" />

      {/* Header skeleton */}
      <header className="sticky top-0 z-50 glass border-b border-border/10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="skeleton h-8 w-8 rounded-xl" />
            <div className="skeleton h-4 w-24 rounded-md" />
          </div>
          <div className="flex items-center gap-2">
            <div className="skeleton h-6 w-20 rounded-full" />
            <div className="w-px h-5 bg-border/20" />
            <div className="skeleton h-8 w-8 rounded-lg" />
            <div className="skeleton h-8 w-8 rounded-lg" />
            <div className="skeleton h-8 w-8 rounded-lg" />
          </div>
        </div>
      </header>

      {/* Main content skeleton */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Hero card */}
        <div className="glass rounded-2xl overflow-hidden">
          <div className="p-8 flex flex-col items-center gap-4">
            <div
              className="skeleton h-4 w-16 rounded-md"
              style={{ animationDelay: "0.1s" }}
            />
            <div
              className="skeleton h-16 w-72 rounded-xl"
              style={{ animationDelay: "0.2s" }}
            />
            <div
              className="skeleton h-3 w-32 rounded-md"
              style={{ animationDelay: "0.3s" }}
            />
            <div
              className="skeleton h-3 w-28 rounded-md"
              style={{ animationDelay: "0.35s" }}
            />
          </div>
          <div className="px-6 pb-6 flex gap-3">
            <div
              className="skeleton flex-1 h-11 rounded-xl"
              style={{ animationDelay: "0.4s" }}
            />
            <div
              className="skeleton flex-1 h-11 rounded-xl"
              style={{ animationDelay: "0.45s" }}
            />
          </div>
        </div>

        {/* 2-column layout skeletons */}
        <div className="flex flex-col lg:grid lg:grid-cols-12 gap-5 lg:gap-6">
          {/* Left column */}
          <div className="lg:col-span-6 space-y-5">
            <div
              className="skeleton h-5 w-32 rounded-md"
              style={{ animationDelay: "0.5s" }}
            />
            {/* Token card */}
            <div className="glass rounded-2xl p-5 space-y-3">
              <div
                className="skeleton h-4 w-24 rounded-md"
                style={{ animationDelay: "0.55s" }}
              />
              <div
                className="skeleton h-10 w-full rounded-xl"
                style={{ animationDelay: "0.6s" }}
              />
            </div>
            {/* CRN card */}
            <div className="glass rounded-2xl p-5 space-y-3">
              <div
                className="skeleton h-4 w-20 rounded-md"
                style={{ animationDelay: "0.65s" }}
              />
              <div
                className="skeleton h-10 w-full rounded-xl"
                style={{ animationDelay: "0.7s" }}
              />
              <div className="flex gap-2 mt-2">
                <div
                  className="skeleton h-7 w-16 rounded-lg"
                  style={{ animationDelay: "0.75s" }}
                />
                <div
                  className="skeleton h-7 w-16 rounded-lg"
                  style={{ animationDelay: "0.8s" }}
                />
              </div>
            </div>
          </div>

          {/* Right column */}
          <div className="lg:col-span-6 space-y-5">
            <div
              className="skeleton h-5 w-24 rounded-md"
              style={{ animationDelay: "0.5s" }}
            />
            {/* Calibration card */}
            <div className="glass rounded-2xl p-5 space-y-3">
              <div
                className="skeleton h-4 w-28 rounded-md"
                style={{ animationDelay: "0.55s" }}
              />
              <div className="flex gap-4 mt-2">
                <div
                  className="skeleton flex-1 h-16 rounded-xl"
                  style={{ animationDelay: "0.6s" }}
                />
                <div
                  className="skeleton flex-1 h-16 rounded-xl"
                  style={{ animationDelay: "0.65s" }}
                />
              </div>
            </div>
            {/* Log card */}
            <div className="glass rounded-2xl p-5 space-y-2">
              <div
                className="skeleton h-4 w-20 rounded-md"
                style={{ animationDelay: "0.6s" }}
              />
              <div className="space-y-1.5 mt-2">
                <div
                  className="skeleton h-3 w-full rounded"
                  style={{ animationDelay: "0.65s" }}
                />
                <div
                  className="skeleton h-3 w-4/5 rounded"
                  style={{ animationDelay: "0.7s" }}
                />
                <div
                  className="skeleton h-3 w-3/5 rounded"
                  style={{ animationDelay: "0.75s" }}
                />
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
