"use client";

export function SkeletonCard() {
  return (
    <div className="relative overflow-hidden rounded-lg border border-border/50 bg-card p-6">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="h-4 w-32 rounded bg-muted animate-pulse" />
          <div className="h-6 w-20 rounded-full bg-muted animate-pulse" />
        </div>

        {/* Content */}
        <div className="space-y-2">
          <div className="h-3 w-full rounded bg-muted animate-pulse" />
          <div className="h-3 w-3/4 rounded bg-muted animate-pulse" />
        </div>

        {/* Footer */}
        <div className="flex gap-4">
          <div className="h-3 w-24 rounded bg-muted animate-pulse" />
          <div className="h-3 w-24 rounded bg-muted animate-pulse" />
        </div>
      </div>

      {/* Shimmer effect */}
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/5 to-transparent" />
    </div>
  );
}
