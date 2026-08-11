import { useRef, useEffect } from "react";
import { Send, ArrowUp, Cpu } from "lucide-react";
import MessageBubble from "./MessageBubble";

export default function ChatArea({
  messages,
  input,
  onInputChange,
  onSend,
  isLoading,
  isDisabled,
  responseMode,
  onResponseModeChange,
}) {
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 150) + "px";
    }
  }, [input]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && input.trim()) {
        onSend();
      }
    }
  };

  const showWelcome = messages.length === 0;

  return (
    <>
      {/* Chat Messages */}
      <div className="chat-area">
        {showWelcome ? (
          <div className="welcome">
            <Cpu size={44} className="welcome-icon-svg" />
            <h1>DataLens</h1>
            <p>
              AI-powered data analyst. Ask questions in plain English — get SQL,
              charts, and insights instantly.
            </p>
            <div className="welcome-steps">
              <div className="step">
                <div className="step-num">1</div>
                <div className="step-text">Add a database connection</div>
              </div>
              <div className="step">
                <div className="step-num">2</div>
                <div className="step-text">Ask a question in natural language</div>
              </div>
              <div className="step">
                <div className="step-num">3</div>
                <div className="step-text">Get SQL, charts, and insights</div>
              </div>
            </div>
          </div>
        ) : (
          <div className="messages-stream">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area — ChatGPT-style centered capsule */}
      <div className="input-dock">
        <div className="input-dock-inner">
          <div className="mode-pills" role="group" aria-label="Response mode">
            <button
              type="button"
              className={responseMode === "answer" ? "active" : ""}
              onClick={() => onResponseModeChange("answer")}
            >
              Answer
            </button>
            <button
              type="button"
              className={responseMode === "chart" ? "active" : ""}
              onClick={() => onResponseModeChange("chart")}
            >
              Chart
            </button>
            <button
              type="button"
              className={responseMode === "both" ? "active" : ""}
              onClick={() => onResponseModeChange("both")}
            >
              Both
            </button>
          </div>
          <div className="input-capsule">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => onInputChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                isDisabled
                  ? "Add a database connection to start..."
                  : "Ask a question about your data..."
              }
              rows={1}
              disabled={isDisabled}
            />
            <button
              className="send-btn"
              onClick={onSend}
              disabled={isLoading || isDisabled || !input.trim()}
              title="Send message"
            >
              {isLoading ? (
                <span className="btn-spinner" />
              ) : (
                <ArrowUp size={18} />
              )}
            </button>
          </div>
          <p className="input-hint">Press Enter to send · Shift+Enter for new line</p>
        </div>
      </div>
    </>
  );
}
