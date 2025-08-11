import React from "react";

export function TestApp() {
  return (
    <div style={{ padding: "20px", background: "#0b0f12", color: "#d8dee9", minHeight: "100vh" }}>
      <h1>ECDIS UI Test</h1>
      <p>React is working!</p>
      <div style={{ marginTop: "20px", padding: "10px", background: "#2e3440", borderRadius: "4px" }}>
        <h2>Status Check:</h2>
        <ul>
          <li>✅ React rendering</li>
          <li>✅ TypeScript compilation</li>
          <li>✅ Vite dev server</li>
        </ul>
      </div>
    </div>
  );
}