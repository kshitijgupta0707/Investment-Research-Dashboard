import { Skeleton } from "@/components/ui/skeleton";
import {
  ListSkeleton,
  LoadingAnnouncement,
  PageHeaderSkeleton,
  RowsSkeleton,
} from "@/components/states";

/**
 * Streamed while this route's server render is in flight.
 *
 * Shaped like the real page so nothing jumps when the data lands.
 */
export default function Loading() {
  return (
    <>
      <LoadingAnnouncement label="Loading your dashboard" />
      <PageHeaderSkeleton />
      <div className="space-y-6">
        <div className="grid gap-3 sm:grid-cols-2" aria-hidden="true">
          <Skeleton className="h-[76px]" />
          <Skeleton className="h-[76px]" />
        </div>
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <ListSkeleton rows={3} />
          </div>
          <RowsSkeleton rows={4} />
          <div className="lg:col-span-3">
            <ListSkeleton rows={3} />
          </div>
        </div>
      </div>
    </>
  );
}
