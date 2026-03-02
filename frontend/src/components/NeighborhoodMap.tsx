"use client";

import dynamic from "next/dynamic";

const NeighborhoodMapClient = dynamic(() => import("@/components/NeighborhoodMapClient"), {
  ssr: false,
  loading: () => (
    <div className="flex min-h-[500px] items-center justify-center rounded-2xl border border-black/10 bg-surface p-5 text-sm opacity-80">
      Loading neighborhood heatmap...
    </div>
  ),
});

export default function NeighborhoodMap() {
  return <NeighborhoodMapClient />;
}
