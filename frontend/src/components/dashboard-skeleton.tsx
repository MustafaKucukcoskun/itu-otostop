"use client";

/**
 * Dashboard config yüklenirken gösterilen iskelet.
 * `.skeleton` (globals.css) sade opaklık nabzı kullanır — shimmer sweep yok.
 * Yerleşim gerçek dashboard'ı birebir aynalar; geçişte layout shift olmaz.
 */
export function DashboardSkeleton() {
  return (
    <main className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6">
      {/* Hero card */}
      <div className="border bg-card">
        <div className="flex flex-col items-center gap-4 p-12">
          <div className="skeleton h-3 w-20" />
          <div className="skeleton h-16 w-72" />
          <div className="skeleton h-3 w-40" />
        </div>
        <div className="flex gap-3 border-t p-4">
          <div className="skeleton h-10 flex-1" />
          <div className="skeleton h-10 flex-1" />
        </div>
      </div>

      {/* 2-column layout skeletons */}
      <div className="flex flex-col gap-5 lg:grid lg:grid-cols-12 lg:gap-6">
        {/* Left column */}
        <div className="space-y-5 lg:col-span-6">
          <div className="skeleton h-3 w-28" />
          <div className="border bg-card">
            <div className="skeleton mx-4 my-3 h-4 w-24" />
            <div className="border-t p-4">
              <div className="skeleton h-20 w-full" />
            </div>
          </div>
          <div className="border bg-card">
            <div className="flex gap-px border-b">
              <div className="skeleton m-3 h-4 w-16" />
              <div className="skeleton m-3 h-4 w-16" />
            </div>
            <div className="space-y-2 p-4">
              <div className="skeleton h-9 w-full" />
              <div className="skeleton h-10 w-full" />
            </div>
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-5 lg:col-span-6">
          <div className="skeleton h-3 w-24" />
          <div className="border bg-card">
            <div className="skeleton mx-4 my-3 h-4 w-28" />
            <div className="space-y-2 border-t p-4">
              <div className="skeleton h-6 w-full" />
              <div className="skeleton h-6 w-full" />
              <div className="skeleton h-6 w-full" />
            </div>
          </div>
          <div className="border bg-card">
            <div className="skeleton mx-4 my-3 h-4 w-20" />
            <div className="border-t p-4">
              <div className="skeleton h-40 w-full" />
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
