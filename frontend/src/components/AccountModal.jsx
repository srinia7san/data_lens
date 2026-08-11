import { useState } from "react";
import { X } from "lucide-react";

export default function AccountModal({ user, onClose, onSubmit, isLoading }) {
  const [geminiApiKey, setGeminiApiKey] = useState("");
  const [pineconeApiKey, setPineconeApiKey] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit({ geminiApiKey, pineconeApiKey });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Account Keys</h2>
          <button className="btn-icon" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="account-summary">
          <div>{user?.name}</div>
          <span>{user?.email}</span>
        </div>

        <form onSubmit={handleSubmit} autoComplete="off">
          <div className="form-group">
            <label htmlFor="gemini-key">Gemini API Key</label>
            <input
              id="gemini-key"
              type="password"
              placeholder={user?.has_gemini_api_key ? "Saved" : "Not saved"}
              value={geminiApiKey}
              onChange={(e) => setGeminiApiKey(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label htmlFor="pinecone-key">Pinecone API Key</label>
            <input
              id="pinecone-key"
              type="password"
              placeholder={user?.has_pinecone_api_key ? "Saved" : "Not saved"}
              value={pineconeApiKey}
              onChange={(e) => setPineconeApiKey(e.target.value)}
            />
          </div>

          <button type="submit" className="btn-primary" disabled={isLoading}>
            {isLoading ? <span className="btn-spinner" /> : "Save Keys"}
          </button>
        </form>
      </div>
    </div>
  );
}
