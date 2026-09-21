import { useState } from "react";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { TENANT, getQueue, getScores, rescore } from "./api";

const PAGE_SIZE = 25;

const styles: Record<string, React.CSSProperties> = {
  page: {
    fontFamily: "system-ui, sans-serif",
    margin: "0 auto",
    maxWidth: 1200,
    padding: 24,
    color: "#1c1c1c",
  },
  layout: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) 420px",
    gap: 24,
    alignItems: "start",
  },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 14 },
  th: { textAlign: "left", borderBottom: "2px solid #ddd", padding: "8px 6px" },
  td: { borderBottom: "1px solid #eee", padding: "8px 6px" },
  rowSelected: { background: "#eef4ff" },
  button: { padding: "4px 10px", cursor: "pointer" },
  linkButton: {
    padding: 0,
    border: "none",
    background: "none",
    color: "#1a56c4",
    cursor: "pointer",
    font: "inherit",
    textDecoration: "underline",
  },
  panel: {
    position: "sticky",
    top: 24,
    border: "1px solid #ddd",
    borderRadius: 6,
    padding: 16,
    background: "#fafafa",
  },
  pager: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    marginTop: 16,
    fontSize: 14,
  },
  muted: { color: "#666" },
  warn: { color: "#b00020" },
};

function ScoreHistory({ conversationId }: { conversationId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["scores", conversationId],
    queryFn: () => getScores(conversationId),
  });

  if (isLoading) return <p style={styles.muted}>Loading score history…</p>;
  if (error) return <p style={styles.warn}>Could not load scores: {String(error)}</p>;
  if (!data?.length) return <p style={styles.muted}>No scores yet.</p>;

  return (
    <table style={styles.table}>
      <thead>
        <tr>
          <th style={styles.th}>Scored at</th>
          <th style={styles.th}>Total</th>
          <th style={styles.th}>Prompt hash</th>
        </tr>
      </thead>
      <tbody>
        {data.map((score) => (
          <tr key={score.id}>
            <td style={styles.td}>{new Date(score.created_at).toLocaleString()}</td>
            <td style={styles.td}>{Number(score.total).toFixed(1)}</td>
            <td style={styles.td}>
              <code>{score.prompt_hash.slice(0, 10)}</code>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function App() {
  const [selected, setSelected] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const queryClient = useQueryClient();

  const queue = useQuery({
    queryKey: ["queue", offset],
    queryFn: () => getQueue(PAGE_SIZE, offset),
    placeholderData: keepPreviousData,
  });

  const rescoreMutation = useMutation({
    mutationFn: rescore,
    onSuccess: (_data, conversationId) => {
      queryClient.invalidateQueries({ queryKey: ["queue"] });
      queryClient.invalidateQueries({ queryKey: ["scores", conversationId] });
    },
  });

  const rows = queue.data ?? [];
  const hasNext = rows.length === PAGE_SIZE;
  const first = rows.length ? offset + 1 : 0;
  const last = offset + rows.length;

  return (
    <div style={styles.page}>
      <h1>Rubric — review queue</h1>
      <p style={styles.muted}>
        Tenant: <strong>{TENANT}</strong>
      </p>

      <div style={styles.layout}>
        <div>
          {queue.isLoading && <p style={styles.muted}>Loading queue…</p>}
          {queue.error && (
            <p style={styles.warn}>Could not load the queue: {String(queue.error)}</p>
          )}

          {queue.data && rows.length === 0 && (
            <p style={styles.muted}>
              Nothing in the queue. The queue lists conversations that already have a
              score, so run <code>make repro-batch</code> or <code>make repro-webhook</code>{" "}
              to score some.
            </p>
          )}

          {rows.length > 0 && (
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Conversation</th>
                  <th style={styles.th}>Score</th>
                  <th style={styles.th}>Scored at</th>
                  <th style={styles.th} />
                </tr>
              </thead>
              <tbody>
                {rows.map((item) => {
                  const isSelected = selected === item.conversation_id;
                  const pending =
                    rescoreMutation.isPending &&
                    rescoreMutation.variables === item.conversation_id;
                  return (
                    <tr key={item.id} style={isSelected ? styles.rowSelected : undefined}>
                      <td style={styles.td}>
                        <button
                          style={styles.linkButton}
                          onClick={() => setSelected(item.conversation_id)}
                        >
                          {item.conversation_id.slice(0, 8)}
                        </button>
                      </td>
                      <td style={styles.td}>{Number(item.total).toFixed(1)}</td>
                      <td style={styles.td}>
                        {new Date(item.created_at).toLocaleString()}
                      </td>
                      <td style={styles.td}>
                        <button
                          style={styles.button}
                          disabled={pending}
                          onClick={() => {
                            setSelected(item.conversation_id);
                            rescoreMutation.mutate(item.conversation_id);
                          }}
                        >
                          {pending ? "Re-scoring…" : "Re-score"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}

          <div style={styles.pager}>
            <button
              style={styles.button}
              disabled={offset === 0 || queue.isFetching}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              Previous
            </button>
            <button
              style={styles.button}
              disabled={!hasNext || queue.isFetching}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Next
            </button>
            <span style={styles.muted}>
              {rows.length ? `Showing ${first}–${last}` : "No rows"}
              {queue.isFetching ? " · loading…" : ""}
            </span>
          </div>

          {rescoreMutation.error && (
            <p style={styles.warn}>Re-score failed: {String(rescoreMutation.error)}</p>
          )}
        </div>

        <div style={styles.panel}>
          <h2 style={{ marginTop: 0, fontSize: 16 }}>Score history</h2>
          {selected ? (
            <>
              <p style={styles.muted}>
                Conversation <code>{selected.slice(0, 8)}</code>
              </p>
              <ScoreHistory conversationId={selected} />
            </>
          ) : (
            <p style={styles.muted}>
              Select a conversation on the left to see every score kept for it.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
