import React from 'react';
import AgentWidget from './AgentWidget';

function App() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6 font-sans">
      <div className="max-w-3xl text-center space-y-6">
        <h1 className="text-5xl font-extrabold text-slate-900 tracking-tight">
          Chidama Tech Partners LLC
        </h1>
        <p className="text-lg text-slate-600">
          This is the staging ground for your future high-speed portfolio. 
          The backend engine is live. The frontend is styled. 
        </p>
        <div className="p-4 bg-indigo-50 border border-indigo-100 rounded-xl inline-block mt-8">
          <p className="text-indigo-800 font-medium">
            Look in the bottom right corner of your screen to interact with your live Agentic AI! ↘️
          </p>
        </div>
      </div>
      
      {/* This line mounts our floating widget to the page */}
      <AgentWidget />
    </div>
  );
}

export default App;