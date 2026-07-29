-- Analyst notes on a saved report.
--
-- Deliberately a separate column rather than an edit to `structured_result`.
-- That column is the record of what the agent retrieved, and every source tag
-- and confidence rating in the UI rests on it being untouched by hand. A figure
-- an analyst typed must never become indistinguishable from one attributed to a
-- provider.
--
-- Nullable: most reports will never carry a note, and an empty string would be
-- a second way of saying the same thing.

alter table research_reports
    add column analyst_notes text,
    add column notes_updated_at timestamptz,
    add column notes_updated_by uuid references users (id) on delete set null;

-- The note is attributed in the UI, so the author is read on every report view.
create index research_reports_notes_updated_by_idx
    on research_reports (notes_updated_by)
    where notes_updated_by is not null;
