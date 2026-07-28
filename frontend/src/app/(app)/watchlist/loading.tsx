import { Skeleton } from "@/components/ui/skeleton";
import {
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
      <LoadingAnnouncement label="Loading your watchlist" />
      <PageHeaderSkeleton />
      <div className="space-y-6">
        <Skeleton className="h-[92px] w-full" aria-hidden="true" />
        <RowsSkeleton rows={5} />
      </div>
    </>
  );
}
