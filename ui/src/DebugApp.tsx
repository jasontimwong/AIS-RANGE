import React, { useEffect, useState } from "react";

export function DebugApp() {
  const [logs, setLogs] = useState<string[]>([]);
  
  const addLog = (msg: string) => {
    setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
  };
  
  useEffect(() => {
    addLog("DebugApp mounted");
    
    // Test backend
    fetch("/status")
      .then(res => {
        addLog(`Backend status: ${res.status}`);
        return res.json();
      })
      .then(data => {
        addLog(`Backend data: ${JSON.stringify(data)}`);
      })
      .catch(err => {
        addLog(`Backend error: ${err.message}`);
      });
  }, []);
  
  // Inline everything to avoid style issues
  return (
    <div style={{
      position: "fixed",
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: "#0b0f12",
      color: "#d8dee9",
      padding: "20px",
      fontFamily: "monospace",
      overflow: "auto"
    }}>
      <h1 style={{ color: "#88c0d0", marginBottom: "20px" }}>
        🔍 ECDIS UI Debug Console
      </h1>
      
      <div style={{
        background: "#2e3440",
        padding: "15px",
        borderRadius: "8px",
        marginBottom: "20px"
      }}>
        <h2>React Status</h2>
        <div style={{ color: "#a3be8c" }}>✅ React is rendering this component!</div>
        <div>Timestamp: {new Date().toISOString()}</div>
      </div>
      
      <div style={{
        background: "#3b4252",
        padding: "15px",
        borderRadius: "8px"
      }}>
        <h2>Event Log</h2>
        {logs.length === 0 ? (
          <div>No logs yet...</div>
        ) : (
          logs.map((log, i) => (
            <div key={i} style={{ 
              padding: "5px 0",
              borderBottom: i < logs.length - 1 ? "1px solid #434c5e" : "none",
              color: log.includes("error") ? "#bf616a" : "#d8dee9"
            }}>
              {log}
            </div>
          ))
        )}
      </div>
      
      <div style={{
        position: "fixed",
        bottom: "20px",
        right: "20px",
        background: "#5e81ac",
        color: "white",
        padding: "10px 20px",
        borderRadius: "8px",
        fontSize: "14px"
      }}>
        Page loaded: {typeof window !== 'undefined' ? 'Browser' : 'SSR'}
      </div>
    </div>
  );
}