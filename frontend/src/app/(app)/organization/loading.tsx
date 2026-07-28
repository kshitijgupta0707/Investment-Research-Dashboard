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
      <LoadingAnnouncement label="Loading workspace settings" />
      <PageHeaderSkeleton />
      <div className="space-y-6">
        <RowsSkeleton rows={3} />
        <RowsSkeleton rows={2} />
      </div>
    </>
  );
}
