-- A fourth query status: 'rejected'.
--
-- The agent may decline a question that is not about companies, markets or
-- financial concepts. Nothing is retrieved and no report is produced, so the run
-- did not fail -- the request was answered, with a refusal.
--
-- Kept distinct from 'failed' because `research_queries` is the record used to
-- show that tool selection varies per question. Folding refusals into failures
-- would make that column unreadable: a pipeline error and an off-topic question
-- are different events and are investigated differently.
--
-- 0001 declared the check inline, so Postgres named it for us.

alter table research_queries
    drop constraint research_queries_status_check;

alter table research_queries
    add constraint research_queries_status_check
    check (status in ('success', 'partial', 'failed', 'rejected'));
