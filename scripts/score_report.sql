\echo
\echo == Conversations closed, and score rows written ==
SELECT
    t.slug                                   AS tenant,
    count(DISTINCT c.id)                     AS conversations_closed,
    count(s.id)                              AS score_rows
FROM tenants t
LEFT JOIN conversations c
       ON c.tenant_id = t.id
      AND c.closed_at >= now() - interval '24 hours'
LEFT JOIN scores s
       ON s.conversation_id = c.id
GROUP BY t.slug
ORDER BY t.slug;

\echo
\echo == Conversations with more than one score row ==
SELECT
    t.slug                                   AS tenant,
    s.conversation_id,
    count(*)                                 AS score_rows,
    array_agg(s.total ORDER BY s.created_at) AS totals,
    count(DISTINCT s.prompt_hash)            AS distinct_prompt_hashes
FROM scores s
JOIN tenants t ON t.id = s.tenant_id
GROUP BY t.slug, s.conversation_id
HAVING count(*) > 1
ORDER BY count(*) DESC, t.slug
LIMIT 25;

\echo
\echo == Score rows with no category rows ==
SELECT
    t.slug                                   AS tenant,
    count(*)                                 AS scores_without_categories
FROM scores s
JOIN tenants t ON t.id = s.tenant_id
LEFT JOIN category_scores cs ON cs.score_id = s.id
WHERE cs.id IS NULL
GROUP BY t.slug
ORDER BY t.slug;

\echo
\echo == Scoring jobs ==
SELECT status, count(*) FROM scoring_jobs GROUP BY status ORDER BY status;

\echo
\echo == Token accounting ==
SELECT
    count(*)                                      AS category_score_rows,
    count(tokens_used)                            AS rows_with_tokens,
    coalesce(sum(tokens_used), 0)                 AS total_tokens
FROM category_scores;

\echo
\echo == Database connections in use ==
SELECT count(*) AS backends, current_setting('max_connections') AS max_connections
FROM pg_stat_activity
WHERE datname = current_database();
\echo
