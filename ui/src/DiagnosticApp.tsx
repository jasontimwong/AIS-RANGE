import React, { useEffect, useState } from "react";

export function DiagnosticApp() {
  const [mounted, setMounted] = useState(false);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [encOk, setEncOk] = useState<boolean | null>(null);
  
  useEffect(() => {
    setMounted(true);
    
    // Test backend connections
    fetch("/status")
      .then(res => res.json())
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false));
      
    fetch("/enc/lite")
      .then(res => res.json())
      .then(() => setEncOk(true))
      .catch(() => setEncOk(false));
  }, []);
  
  // Use inline styles to ensure visibility
  const containerStyle: React.CSSProperties = {
    position: "fixed",
    top: 0,
    left: 0,
    width: "100vw",
    height: "100vh",
    background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    color: "white",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "20px",
    fontFamily: "sans-serif"
  };
  
  const boxStyle: React.CSSProperties = {
    background: "rgba(0,0,0,0.5)",
    padding: "30px",
    borderRadius: "10px",
    textAlign: "center"
  };
  
  return (
    <div style={containerStyle}>
      <div style={boxStyle}>
        <h1 style={{ fontSize: "48px", marginBottom: "20px" }}>
          🚢 ECDIS UI Diagnostic
        </h1>
        
        <div style={{ marginBottom: "10px" }}>
          React Mounted: {mounted ? "✅ YES" : "❌ NO"}
        </div>
        
        <div style={{ marginBottom: "10px" }}>
          Backend Status: {
            backendOk === null ? "⏳ Testing..." : 
            backendOk ? "✅ Connected" : "❌ Failed"
          }
        </div>
        
        <div style={{ marginBottom: "10px" }}>
          ENC Data: {
            encOk === null ? "⏳ Testing..." : 
            encOk ? "✅ Available" : "❌ Failed"
          }
        </div>
        
        <div style={{ marginTop: "20px", fontSize: "16px", opacity: 0.8 }}>
          If you can see this, React is working properly!
        </div>
        
        <div style={{ marginTop: "10px", fontSize: "14px", opacity: 0.6 }}>
          Time: {new Date().toLocaleString()}
        </div>
      </div>
    </div>
  );
}