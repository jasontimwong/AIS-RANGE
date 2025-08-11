import React from "react";

export function StaticTest() {
  // No hooks, no state - just pure render
  return React.createElement(
    'div',
    { 
      style: { 
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: '24px',
        fontFamily: 'sans-serif'
      } 
    },
    React.createElement('h1', { style: { fontSize: '48px', marginBottom: '20px' } }, '🚢 ECDIS UI'),
    React.createElement('p', null, 'If you can see this, React is working!'),
    React.createElement('p', { style: { fontSize: '16px', marginTop: '20px', opacity: 0.8 } }, 
      'Time: ' + new Date().toLocaleTimeString()
    )
  );
}