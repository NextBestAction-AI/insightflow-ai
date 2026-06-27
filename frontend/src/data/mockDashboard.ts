import type { ActivityItem, AgentNode, CustomerData } from "../types/dashboard";

export const CURRENT_USER = {
  name: "Sarah",
  role: "Customer Success Manager",
  email: "sarah.c@insightflow.ai",
  avatar:
    "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=100&q=80",
};

export const CUSTOMER: CustomerData = {
  name: "Acme Corporation",
  health: 89,
  renewalProbability: 91,
  churnRisk: "Low",
  confidence: 96,
};

export const DEFAULT_METRICS = {
  customerHealth: 89,
  renewalProbability: 91,
  churnRisk: "Low",
  aiConfidence: 96,
};

export const DEFAULT_ACTIVITIES: ActivityItem[] = [
  {
    id: 1,
    time: "10:12",
    title: "Interaction uploaded",
    description: "Meeting transcript uploaded for Acme Corporation (meeting_transcript.pdf)",
    type: "upload",
  },
  {
    id: 2,
    time: "10:13",
    title: "Knowledge retrieved",
    description: "Matched SLA agreements and 3 solutions from vector store",
    type: "retrieve",
  },
  {
    id: 3,
    time: "10:14",
    title: "Customer health calculated",
    description: "Health score: 89% — engagement declined 18% over 14 days",
    type: "health",
  },
  {
    id: 4,
    time: "10:15",
    title: "Risk detected",
    description: "Support volume increased; renewal approaching in 14 days",
    type: "risk",
  },
  {
    id: 5,
    time: "10:16",
    title: "Recommendation generated",
    description: "Schedule Executive Business Review — expected to reduce churn risk by 23%",
    type: "recommendation",
  },
];

export const AGENT_NODES: AgentNode[] = [
  {
    id: 1,
    name: "Planner Agent",
    role: "Orchestrator",
    activity: "Delegating tasks to specialized agents...",
    log: "Parsing customer interaction transcripts & delegating agent routines...",
  },
  {
    id: 2,
    name: "Interaction Agent",
    role: "NLP Analyzer",
    activity: "Extracting sentiment from meeting transcript...",
    log: "Extracting conversational sentiment & critical customer queries...",
  },
  {
    id: 3,
    name: "Knowledge Retrieval Agent",
    role: "Retrieval",
    activity: "Searching knowledge base for SLA documents...",
    log: "Searching vector databases for related SLA documents and solutions...",
  },
  {
    id: 4,
    name: "CRM Agent",
    role: "Data Sync",
    activity: "Syncing account history and renewal dates...",
    log: "Retrieving account history, subscription renewal dates, and recent emails...",
  },
  {
    id: 5,
    name: "Customer Health Agent",
    role: "Health Indexer",
    activity: "Calculating health metrics across signals...",
    log: "Calculating customer metrics. Active health calculated: 89%.",
  },
  {
    id: 6,
    name: "Risk Analysis Agent",
    role: "Risk Analyzer",
    activity: "Analyzing customer signals for churn risk...",
    log: "CRITICAL: Detected 18% engagement decline and 3 new high priority tickets.",
  },
  {
    id: 7,
    name: "Business Reasoning Agent",
    role: "Inference",
    activity: "Simulating outcomes and mapping to CLV...",
    log: "Simulating potential actions and mapping to customer lifetime value...",
  },
  {
    id: 8,
    name: "Recommendation Agent",
    role: "Next Best Action",
    activity: "Constructing next best action...",
    log: "Constructing recommendation: 'Schedule Executive Business Review'...",
  },
  {
    id: 9,
    name: "Explanation Agent",
    role: "NLG Explainer",
    activity: "Drafting evidence-backed explanation...",
    log: "Drafting evidence: Engagement drop, ticket escalations, contract renewal due in 14 days.",
  },
  {
    id: 10,
    name: "Human Approval",
    role: "Operator Gate",
    activity: "Awaiting manager authorization...",
    log: "Queueing action for manager authorization. Pending input...",
  },
  {
    id: 11,
    name: "Memory Update",
    role: "Vector DB Writer",
    activity: "Syncing decision to semantic memory...",
    log: "Syncing final approved action to long term semantic index. Complete.",
  },
];

export const EXECUTIVE_SUMMARY_POINTS = [
  "Customer engagement has declined 18% over the past two weeks.",
  "Support volume increased with 3 open escalations.",
  "Renewal is approaching in 14 days ($128,000 ARR).",
  "Recommended proactive outreach via Executive Business Review.",
];

export const MOCK_CUSTOMERS = [
  {
    id: 1,
    name: "Acme Corporation",
    health: 89,
    arr: "$128,000",
    renewalDays: 14,
    churnRisk: "Low" as const,
    csm: "Sarah",
    status: "At Risk",
  },
  {
    id: 2,
    name: "Globex Industries",
    health: 72,
    arr: "$84,500",
    renewalDays: 45,
    churnRisk: "Medium" as const,
    csm: "Sarah",
    status: "Monitoring",
  },
  {
    id: 3,
    name: "Initech LLC",
    health: 94,
    arr: "$210,000",
    renewalDays: 120,
    churnRisk: "Low" as const,
    csm: "Mike",
    status: "Healthy",
  },
  {
    id: 4,
    name: "Umbrella Corp",
    health: 58,
    arr: "$56,000",
    renewalDays: 7,
    churnRisk: "High" as const,
    csm: "Sarah",
    status: "Critical",
  },
];

export const KNOWLEDGE_DOCUMENTS = [
  {
    id: 1,
    title: "Enterprise SLA Agreement v3.2",
    category: "Contracts",
    lastSynced: "2 hours ago",
    chunks: 142,
  },
  {
    id: 2,
    title: "Executive Business Review Playbook",
    category: "Playbooks",
    lastSynced: "5 hours ago",
    chunks: 89,
  },
  {
    id: 3,
    title: "Churn Prevention Framework",
    category: "Frameworks",
    lastSynced: "1 day ago",
    chunks: 67,
  },
  {
    id: 4,
    title: "Product Usage Analytics Guide",
    category: "Product Docs",
    lastSynced: "1 day ago",
    chunks: 54,
  },
  {
    id: 5,
    title: "Support Escalation Procedures",
    category: "Support",
    lastSynced: "3 days ago",
    chunks: 38,
  },
  {
    id: 6,
    title: "Renewal Negotiation Templates",
    category: "Templates",
    lastSynced: "4 days ago",
    chunks: 24,
  },
];

export const RECOMMENDATION_DATA = {
  customer: "Acme Corporation",
  action: "Schedule Executive Business Review",
  reason: "Customer engagement decreased 18%",
  confidence: 96,
  expectedImpact: "Reduce churn risk by 23%",
  evidence: [
    { text: "Meeting transcript analyzed", type: "success" as const },
    { text: "CRM history reviewed", type: "success" as const },
    { text: "Product usage declined 18%", type: "warning" as const },
    { text: "Support tickets increased (+3 escalations)", type: "warning" as const },
    { text: "Contract renewal due in 14 days", type: "info" as const },
  ],
};
