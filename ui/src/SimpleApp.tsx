import React, { useEffect, useState } from "react";

export function SimpleApp() {
  const [status, setStatus] = useState<string>("Loading...");
  const [backendStatus, setBackendStatus] = useState<any>(null);

  console.log("SimpleApp component mounted!");

  useEffect(() => {
    console.log("Testing backend connection...");
    // Test backend connection
    fetch("/status")
      .then(res => res.json())
      .then(data => {
        setBackendStatus(data);
        setStatus("Connected!");
      })
      .catch(err => {
        setStatus("Backend connection failed: " + err.message);
      });
  }, []);

  return (
    <div style={{
      minHeight: "100vh",
      background: "#0b0f12",
      color: "#d8dee9",
      padding: "20px",
      fontFamily: "monospace"
    }}>
      <h1 style={{ color: "#88c0d0" }}>🚢 ECDIS Route Planner UI</h1>
      
      <div style={{
        marginTop: "20px",
        padding: "15px",
        background: "#2e3440",
        borderRadius: "8px",
        border: "1px solid #3b4252"
      }}>
        <h2>System Status</h2>
        <p>Frontend: {status}</p>
        {backendStatus && (
          <>
            <p>Backend: {backendStatus.status}</p>
            <p>ENC Loaded: {backendStatus.enc_loaded ? "Yes" : "No"}</p>
            <p>Planner Ready: {backendStatus.planner_ready ? "Yes" : "No"}</p>
          </>
        )}
      </div>

      <div style={{
        marginTop: "20px",
        padding: "15px",
        background: "#3b4252",
        borderRadius: "8px"
      }}>
        <h3>Quick Test Links:</h3>
        <ul style={{ listStyle: "none", padding: 0 }}>
          <li>
            <a href="/enc/lite" target="_blank" style={{ color: "#a3be8c" }}>
              Test ENC Data Endpoint →
            </a>
          </li>
          <li style={{ marginTop: "10px" }}>
            <a href="/status" target="_blank" style={{ color: "#a3be8c" }}>
              Test Status Endpoint →
            </a>
          </li>
        </ul>
      </div>

      <div style={{
        marginTop: "20px",
        padding: "15px",
        background: "#2e3440",
        borderRadius: "8px",
        fontSize: "12px",
        color: "#81a1c1"
      }}>
        <p>If you see this, React is working! ✅</p>
        <p>Next step: Check browser console for any errors.</p>
      </div>
    </div>
  );
}