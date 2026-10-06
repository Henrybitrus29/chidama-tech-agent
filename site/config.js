// The only file you need to edit to personalise the site.
window.SITE_CONFIG = {
  name: "Henry",
  api: "https://chidama-tech-agent.onrender.com",      // your Render URL, no trailing slash
  email: "you@example.com",
  upwork: "https://www.upwork.com/freelancers/~YOUR-ID",
  github: "https://github.com/Henrybitrus29",
  // Only keep stats that are true. Each item is [big text, small label].
  stats: [["3", "case studies"], ["CI", "on every repo"], ["Free", "tier deployable"]]
};

// Add a project = add an object. The filter buttons update by themselves. Delete any claim you cannot back up.
window.SITE_PROJECTS = [
 {title:"Concierge Agent",cat:"AI agents",blurb:"A support agent that answers only from a company's documents, cites sources, refuses what it cannot support, books appointments and hands off to humans.",
  points:["Retrieval with an answer gate that refuses off-topic questions","Code-validated tools; injection blocks lead and booking creation","Offline evaluation set runs as a CI regression test"],
  stack:["Python","FastAPI","LangGraph","Groq"],links:[["Code","https://github.com/Henrybitrus29/chidama-tech-agent"],["Live demo","#agent"]]},
 {title:"LeadFlow AI",cat:"Automation",blurb:"Website leads are validated, deduplicated, scored by an LLM and routed to the right person in seconds, with alerts when anything fails.",
  points:["Plain code decides the route; the model only scores","Fails closed: bad AI output goes to a human, never auto-replied","15 end-to-end test leads incl. spam and prompt injection"],
  stack:["n8n","HubSpot","Groq","JavaScript"],links:[["Case study","#"],["Workflow","#"]]},
 {title:"VendorGuard",cat:"Full-stack",blurb:"Vendors upload compliance documents; an AI pipeline extracts and checks them, and low-confidence cases land in a human review queue.",
  points:["Next.js dashboard with vendor and admin roles","Background processing with Redis and RQ","Security tests and CI in the repo"],
  stack:["Next.js","FastAPI","PostgreSQL","Docker"],links:[["Case study","#"],["Code","#"]]}
];