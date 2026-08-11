import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

const MAX_DISPLAY_ROWS = 50;

export default function DataTable({ rows }) {
  const [expanded, setExpanded] = useState(false);

  if (!rows || rows.length === 0) return null;

  const columns = useMemo(() => Object.keys(rows[0]), [rows]);
  const displayRows = rows.slice(0, MAX_DISPLAY_ROWS);

  return (
    <div className="msg-collapsible">
      <button
        className="msg-collapsible-toggle"
        onClick={() => setExpanded((prev) => !prev)}
      >
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span>Query Results</span>
        <span className="msg-collapsible-meta">{rows.length} row{rows.length !== 1 ? "s" : ""}</span>
      </button>

      {expanded && (
        <div className="data-table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                {columns.map((col) => (
                  <th key={col}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {displayRows.map((row, i) => (
                <tr key={i}>
                  {columns.map((col) => (
                    <td key={col}>
                      {row[col] === null ? (
                        <span style={{ color: "var(--text-tertiary)", fontStyle: "italic" }}>null</span>
                      ) : (
                        String(row[col])
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length > MAX_DISPLAY_ROWS && (
            <div className="data-table-footer">
              Showing {MAX_DISPLAY_ROWS} of {rows.length} rows
            </div>
          )}
        </div>
      )}
    </div>
  );
}
