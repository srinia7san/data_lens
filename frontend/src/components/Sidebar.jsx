import { ChevronLeft, Cpu, Database, Key, LogOut, Plus, Trash2 } from "lucide-react";

export default function Sidebar({
  connections,
  activeConnection,
  onAddClick,
  onSwitch,
  onRemove,
  collapsed,
  onToggle,
  user,
  onLogout,
  onOpenAccountModal,
}) {
  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      {/* Header */}
      <div className="sidebar-header">
        <div className="logo">
          <Cpu size={20} className="logo-icon-svg" />
          <span className="logo-text">DataLens</span>
        </div>
        <button className="btn-icon" onClick={onToggle} title="Toggle sidebar">
          <ChevronLeft size={18} />
        </button>
      </div>

      {/* Main Navigation */}
      <div className="sidebar-content">
        <div className="section-header">
          <span>DATABASES</span>
          <button className="btn-icon" onClick={onAddClick} title="Add database">
            <Plus size={16} />
          </button>
        </div>

        <div className="db-list">
          {connections.length === 0 ? (
            <div className="empty-state-sidebar">No databases connected</div>
          ) : (
            connections.map((conn) => (
              <div
                key={conn.name}
                className={`db-item ${activeConnection === conn.name ? "active" : ""}`}
                onClick={() => onSwitch({ name: conn.name })}
              >
                <div className="db-info">
                  <Database size={14} className="db-icon" />
                  <span className="db-name" title={conn.name}>
                    {conn.name}
                  </span>
                </div>
                <button
                  className="btn-icon delete-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemove({ name: conn.name });
                  }}
                  title="Remove connection"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="sidebar-footer">
        {user && (
          <div className="user-box">
            <div className="user-name">{user.name}</div>
            <div className="user-email">{user.email}</div>
            <div className="user-actions">
              <button className="btn-icon" onClick={onOpenAccountModal} title="API Keys & Account">
                <Key size={15} />
              </button>
              <button className="btn-icon" onClick={onLogout} title="Logout">
                <LogOut size={15} />
              </button>
            </div>
          </div>
        )}
        <div className="session-info">
          <span className={`session-dot ${connections.length > 0 ? "live" : ""}`} />
          <span>
            {connections.length > 0
              ? `${connections.length} connection${connections.length > 1 ? "s" : ""}`
              : "No active session"}
          </span>
        </div>
      </div>
    </aside>
  );
}
