import { Skeleton } from "@/components/ui/skeleton";
import {
  ListSkeleton,
  LoadingAnnouncement,
  PageHeaderSkeleton,
} from "@/components/states";

/**
 * Streamed while this route's server render is in flight.
 *
 * Shaped like the real page so nothing jumps when the data lands.
 */
export default function Loading() {
  return (
    <>
      <LoadingAnnouncement label="Loading saved reports" />
      <PageHeaderSkeleton />
      <div className="space-y-5">
        <Skeleton className="h-9 w-full max-w-md" aria-hidden="true" />
        <ListSkeleton rows={5} />
      </div>
    </>
  );
}
