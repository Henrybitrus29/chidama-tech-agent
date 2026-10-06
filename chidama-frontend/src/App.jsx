import React from 'react';
import AgentWidget from './AgentWidget'; // Ensure AgentWidget.jsx is in this exact same folder!

function App() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans selection:bg-emerald-500 selection:text-slate-950 overflow-x-hidden relative">
      
      {/* Subtle Background Glow Effects */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-emerald-500/10 blur-[120px] rounded-full pointer-events-none z-0"></div>
      
      {/* Navigation Bar */}
      <nav className="w-full border-b border-slate-800/50 bg-slate-950/80 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-emerald-500 flex items-center justify-center font-bold text-slate-950">
              C
            </div>
            <span className="font-bold text-xl tracking-tight text-white">Chidama Tech</span>
          </div>
          <div className="hidden md:flex gap-8 text-sm font-medium text-slate-400">
            <a href="#services" className="hover:text-emerald-400 transition-colors">Services</a>
            <a href="#architecture" className="hover:text-emerald-400 transition-colors">Architecture</a>
            <a href="#operations" className="hover:text-emerald-400 transition-colors">Global Operations</a>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <main className="flex flex-col items-center justify-center px-6 pt-24 pb-32 text-center relative z-10">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900 border border-slate-700 text-xs font-medium text-emerald-400 mb-8">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          System Architecture Staging Environment
        </div>
        
        <h1 className="text-5xl md:text-7xl font-extrabold text-white tracking-tight mb-6 max-w-4xl leading-tight">
          Enterprise <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-cyan-500">Intelligence</span> & Architecture.
        </h1>
        
        <p className="text-lg md:text-xl text-slate-400 max-w-2xl mb-12 leading-relaxed">
          We engineer secure, full-stack environments and autonomous AI agents for high-growth startups and global enterprises.
        </p>

        <div className="flex gap-4 justify-center">
          <a href="#architecture" className="px-8 py-4 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-lg transition-all shadow-[0_0_20px_rgba(16,185,129,0.3)] hover:shadow-[0_0_30px_rgba(16,185,129,0.5)]">
            Explore Capabilities
          </a>
          <a href="#services" className="px-8 py-4 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 font-semibold rounded-lg transition-all flex items-center justify-center">
            View Methodology
          </a>
        </div>
      </main>

      {/* Services Grid Section */}
      <section id="services" className="py-24 bg-slate-900/50 border-y border-slate-800/50 z-10 relative">
        <div className="max-w-7xl mx-auto px-6">
          <div className="mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">Core Infrastructure & Services</h2>
            <p className="text-slate-400 max-w-2xl">We do not rely on paper credentials; we are defined by demonstrable skill and shipped projects. Our team consists of relentless builders and defensive-minded engineers.</p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Service 1 */}
            <div className="bg-slate-950 p-8 rounded-xl border border-slate-800 hover:border-emerald-500/50 transition-colors group">
              <div className="w-12 h-12 bg-slate-900 rounded-lg flex items-center justify-center mb-6 border border-slate-800 group-hover:border-emerald-500/30">
                <svg className="w-6 h-6 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" /></svg>
              </div>
              <h3 className="text-xl font-bold text-white mb-3">Full-Stack Engineering</h3>
              <p className="text-sm text-slate-400 leading-relaxed">Lightning-fast, highly responsive React and Next.js frontends powered by robust, scalable Python and FastAPI backends.</p>
            </div>

            {/* Service 2 */}
            <div className="bg-slate-950 p-8 rounded-xl border border-slate-800 hover:border-emerald-500/50 transition-colors group">
              <div className="w-12 h-12 bg-slate-900 rounded-lg flex items-center justify-center mb-6 border border-slate-800 group-hover:border-emerald-500/30">
                <svg className="w-6 h-6 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
              </div>
              <h3 className="text-xl font-bold text-white mb-3">Pre-Deployment Hardening</h3>
              <p className="text-sm text-slate-400 leading-relaxed">We secure what we build. Strict OWASP vulnerability scanning and SQLi testing in local virtual environments prior to handover.</p>
            </div>

            {/* Service 3 */}
            <div className="bg-slate-950 p-8 rounded-xl border border-slate-800 hover:border-emerald-500/50 transition-colors group">
              <div className="w-12 h-12 bg-slate-900 rounded-lg flex items-center justify-center mb-6 border border-slate-800 group-hover:border-emerald-500/30">
                <svg className="w-6 h-6 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
              </div>
              <h3 className="text-xl font-bold text-white mb-3">Enterprise Automation</h3>
              <p className="text-sm text-slate-400 leading-relaxed">Serverless n8n workflows, custom Python ETL scripts, and safe data harvesting pipelines that eliminate manual bottlenecks.</p>
            </div>

            {/* Service 4 */}
            <div className="bg-slate-950 p-8 rounded-xl border border-slate-800 hover:border-emerald-500/50 transition-colors group">
              <div className="w-12 h-12 bg-slate-900 rounded-lg flex items-center justify-center mb-6 border border-slate-800 group-hover:border-emerald-500/30">
                <svg className="w-6 h-6 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
              </div>
              <h3 className="text-xl font-bold text-white mb-3">Agentic AI Architecture</h3>
              <p className="text-sm text-slate-400 leading-relaxed">Integration of LangGraph, vector databases, and custom autonomous AI-driven terminal tools for internal engineering teams.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Featured Architecture (Projects) Section */}
      <section id="architecture" className="py-24 z-10 relative">
        <div className="max-w-7xl mx-auto px-6">
          <div className="mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">Featured Architecture</h2>
            <p className="text-slate-400 max-w-2xl">A selection of active pipelines and systems engineered by our team.</p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            
            {/* Project: B2B Lead Printer */}
            <div className="bg-slate-900/50 rounded-2xl border border-slate-800 overflow-hidden flex flex-col">
              <div className="h-48 bg-slate-950 border-b border-slate-800 p-6 flex items-center justify-center relative overflow-hidden">
                <div className="absolute inset-0 opacity-20 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-emerald-500 via-slate-950 to-slate-950"></div>
                <h4 className="text-2xl font-black text-slate-700 tracking-widest z-10">PIPELINE_01</h4>
              </div>
              <div className="p-8 flex-1 flex flex-col">
                <div className="flex gap-2 mb-4">
                  <span className="px-2 py-1 bg-slate-800 rounded text-xs font-semibold text-emerald-400">n8n</span>
                  <span className="px-2 py-1 bg-slate-800 rounded text-xs font-semibold text-emerald-400">Python</span>
                </div>
                <h3 className="text-xl font-bold text-white mb-3">The B2B Lead Printer</h3>
                <p className="text-sm text-slate-400 leading-relaxed mb-6 flex-1">An automated lead generation pipeline that scrapes target prospects, cross-references corporate emails, and sanitizes data outputs for CRM integration.</p>
              </div>
            </div>

            {/* Project: Campus Signage */}
            <div className="bg-slate-900/50 rounded-2xl border border-slate-800 overflow-hidden flex flex-col">
              <div className="h-48 bg-slate-950 border-b border-slate-800 p-6 flex items-center justify-center relative overflow-hidden">
                <div className="absolute inset-0 opacity-20 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-cyan-500 via-slate-950 to-slate-950"></div>
                <h4 className="text-2xl font-black text-slate-700 tracking-widest z-10">ENGINE_02</h4>
              </div>
              <div className="p-8 flex-1 flex flex-col">
                <div className="flex gap-2 mb-4">
                  <span className="px-2 py-1 bg-slate-800 rounded text-xs font-semibold text-cyan-400">Flask</span>
                  <span className="px-2 py-1 bg-slate-800 rounded text-xs font-semibold text-cyan-400">AI Classification</span>
                </div>
                <h3 className="text-xl font-bold text-white mb-3">Campus Signage System</h3>
                <p className="text-sm text-slate-400 leading-relaxed mb-6 flex-1">A dynamic digital signage backend utilizing AI models to automatically classify, prioritize, and display university announcements and alerts in real-time.</p>
              </div>
            </div>

            {/* Project: GEMCODE */}
            <div className="bg-slate-900/50 rounded-2xl border border-slate-800 overflow-hidden flex flex-col border-emerald-500/30 relative">
              <div className="absolute top-4 right-4 flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
              </div>
              <div className="h-48 bg-slate-950 border-b border-slate-800 p-6 flex items-center justify-center relative overflow-hidden">
                <div className="absolute inset-0 opacity-20 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-emerald-500 via-slate-950 to-slate-950"></div>
                <h4 className="text-2xl font-black text-slate-700 tracking-widest z-10">AGENT_03</h4>
              </div>
              <div className="p-8 flex-1 flex flex-col">
                <div className="flex gap-2 mb-4">
                  <span className="px-2 py-1 bg-slate-800 rounded text-xs font-semibold text-emerald-400">LangGraph</span>
                  <span className="px-2 py-1 bg-slate-800 rounded text-xs font-semibold text-emerald-400">RAG</span>
                </div>
                <h3 className="text-xl font-bold text-white mb-3">GEMCODE AI</h3>
                <p className="text-sm text-slate-400 leading-relaxed mb-6 flex-1">A proprietary autonomous AI agent engineered for context retention and enterprise consultation. (Currently active on this page).</p>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* Global Operations Section */}
      <section id="operations" className="py-24 bg-slate-900/50 border-t border-slate-800/50 z-10 relative">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <h2 className="text-3xl font-bold text-white mb-6">Global Delivery. Competitive Architecture.</h2>
          <p className="text-slate-400 text-lg leading-relaxed mb-8">
            Chidama Tech Partners is an upcoming US LLC operating an elite engineering hub out of Nigeria. By leveraging top-tier global talent, we deliver enterprise-grade architecture, uncompromising security, and advanced AI integration at highly accessible pricing tiers.
          </p>
          <a href="mailto:hello@chidama.tech" className="inline-flex items-center gap-2 text-emerald-400 font-semibold hover:text-emerald-300 transition-colors">
            Request a Custom Statement of Work <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
          </a>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 border-t border-slate-800 text-center text-slate-500 text-sm z-10 relative bg-slate-950">
        <p>&copy; {new Date().getFullYear()} Chidama Tech Partners LLC. All rights reserved.</p>
      </footer>

      {/* The Agent Widget */}
      <AgentWidget />

    </div>
  );
}

export default App;