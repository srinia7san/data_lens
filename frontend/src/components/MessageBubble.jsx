import SqlBlock from "./SqlBlock";
import DataTable from "./DataTable";
import ChartDisplay from "./ChartDisplay";
import { User, Cpu } from "lucide-react";

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";
  const showDetails = !message.mode || message.mode === "both";

  return (
    <div className={`message-row ${isUser ? "user" : "assistant"}`}>
      {/* Avatar */}
      <div className={`msg-avatar ${isUser ? "user" : "assistant"}`}>
        {isUser ? <User size={18} /> : <Cpu size={18} />}
      </div>

      {/* Content */}
      <div className="msg-content">
        <span className="msg-sender">{isUser ? "You" : "DataLens"}</span>

        {/* Loading state */}
        {message.loading && (
          <div className="loading-dots">
            <span /><span /><span />
          </div>
        )}

        {/* Error state */}
        {message.error && (
          <div className="msg-error">⚠ {message.error}</div>
        )}

        {/* Text content */}
        {message.text && <div className="msg-text">{message.text}</div>}

        {/* Chart — renders seamlessly inline */}
        {message.chartConfig && message.queryResults && (
          <div className="msg-chart-inline">
            <ChartDisplay config={message.chartConfig} rows={message.queryResults} />
          </div>
        )}

        {/* Generated SQL — collapsible */}
        {showDetails && message.sql && <SqlBlock sql={message.sql} />}

        {/* Data Table — collapsible */}
        {showDetails && message.queryResults && message.queryResults.length > 0 && (
          <DataTable rows={message.queryResults} />
        )}
      </div>
    </div>
  );
}
