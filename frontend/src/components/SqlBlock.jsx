import { Copy, Check, ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

export default function SqlBlock({ sql }) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);

  if (!sql) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard not available */
    }
  };

  return (
    <div className="msg-collapsible">
      <button
        className="msg-collapsible-toggle"
        onClick={() => setExpanded((prev) => !prev)}
      >
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span>Generated SQL</span>
      </button>

      {expanded && (
        <div className="sql-block-inline">
          <div className="sql-block-toolbar">
            <button className="btn-icon" onClick={handleCopy} title="Copy SQL">
              {copied ? <Check size={14} color="var(--green)" /> : <Copy size={14} />}
            </button>
          </div>
          <pre className="sql-block-code">{sql}</pre>
        </div>
      )}
    </div>
  );
}
