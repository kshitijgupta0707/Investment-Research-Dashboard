import { Skeleton } from "@/components/ui/skeleton";
import { LoadingAnnouncement, ReportSkeleton } from "@/components/states";

/** Streamed while the saved report is fetched. */
export default function Loading() {
  return (
    <>
      <LoadingAnnouncement label="Loading report" />
      <div aria-hidden="true">
        <Skeleton className="mb-6 h-4 w-24" />
        <Skeleton className="mb-4 h-6 w-4/5" />
        <Skeleton className="mb-6 h-8 w-64" />
      </div>
      <ReportSkeleton />
    </>
  );
}
