# Jarvis Vision: Personal AI Agent

> **North Star**: An AI system that knows everything about Aaron's life and can act on his behalf—with human approval for all actions.

---

## 🎯 The Goal

Build a **personal AI agent** that:
1. **Remembers everything** - Every conversation, meeting, note, idea
2. **Understands context** - Knows who people are, what matters, what's happening
3. **Takes action** - Creates calendar events, drafts emails, updates CRM
4. **Stays under control** - Human-in-the-loop for all actions

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                              │
│  Voice Notes │ Meetings │ WhatsApp │ Email │ Calendar │ Files   │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     INGESTION PIPELINE                           │
│              (Airflow + Python + Embeddings)                     │
│                                                                  │
│  • Transcribe audio (WhisperX on Modal)                         │
│  • Extract entities (people, dates, topics)                     │
│  • Generate embeddings (local model)                            │
│  • Store everything in Supabase                                 │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        SUPABASE                                  │
│                   (Personal Knowledge Base)                      │
│                                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │
│  │ Transcripts │ │  Meetings   │ │   People    │ │  Tasks    │  │
│  │ (full text) │ │ (summaries) │ │   (CRM)     │ │           │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │
│  │ Reflections │ │   Emails    │ │  Messages   │ │  Events   │  │
│  │             │ │ (summaries) │ │ (WhatsApp)  │ │ (calendar)│  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    pgvector Embeddings                      ││
│  │              (semantic search across everything)            ││
│  └─────────────────────────────────────────────────────────────┘│
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      RAG QUERY LAYER                             │
│                                                                  │
│  Query: "What do I know about John's startup?"                  │
│                         │                                        │
│                         ▼                                        │
│  1. Embed query → 2. Vector search → 3. Fetch relevant chunks   │
│                         │                                        │
│                         ▼                                        │
│  4. Send to LLM with context → 5. Generate answer               │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        AI AGENT                                  │
│              (Local Qwen/Llama or Claude API)                    │
│                                                                  │
│  Connected via MCP to:                                          │
│  • Beeper (WhatsApp, Signal, Telegram)                          │
│  • Google Calendar                                              │
│  • Gmail                                                        │
│  • Notion                                                       │
│  • Supabase (memory)                                            │
│  • Browser (research)                                           │
│  • Filesystem                                                   │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   HUMAN-IN-THE-LOOP                              │
│                                                                  │
│  Agent proposes action → Aaron approves/modifies → Action taken │
│                                                                  │
│  Examples:                                                       │
│  • "Create calendar event for Thursday 3pm with John?" [✓/✗]   │
│  • "Draft reply to Sarah about Singapore trip?" [✓/✗]          │
│  • "Update CRM: Mike now at Stripe?" [✓/✗]                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Data Sources to Ingest

### Phase 1: Core (Current + Near-term)
| Source | Data Type | Status |
|--------|-----------|--------|
| Voice recordings | Transcripts, meetings, reflections | ✅ Working |
| Notion | CRM, tasks, notes | ✅ Working (write), 🔄 Sync to Supabase |
| Google Calendar | Events, meetings | 🔜 Next |
| Gmail | Email summaries | 🔜 Next |
| WhatsApp (Beeper) | Message history | 🔜 Next |

### Phase 2: Extended
| Source | Data Type | Priority |
|--------|-----------|----------|
| Browser history | Articles read, research | Medium |
| Google Drive | Documents, PDFs | Medium |
| Telegram | Messages | Medium |
| Signal | Messages | Medium |
| Health data | Sleep, exercise | Low |
| Location history | Places visited | Low |
| Financial data | Transactions | Low |
| Photos | OCR text, AI descriptions | Low |

---

## 🤖 Agent Capabilities

### Autonomous Actions (Auto with notification)
- Update CRM with new information about contacts
- Index new content into Supabase
- Tag and categorize incoming data
- Track follow-ups and reminders

### Draft Actions (Requires approval)
- Create calendar events
- Draft email replies
- Draft WhatsApp messages
- Create Notion pages
- Propose task creation

### Query Capabilities
- "What do I know about [person]?"
- "Summarize my meetings from last week"
- "What did I learn about [topic]?"
- "Who mentioned [keyword] recently?"
- "What tasks am I behind on?"
- "What should I follow up on with [person]?"

---

## 🛠️ Technical Stack

### Current Infrastructure
| Component | Technology | Status |
|-----------|------------|--------|
| Orchestration | Airflow (Docker) | ✅ Running |
| Transcription | WhisperX on Modal (T4 GPU) | ✅ Running |
| Analysis | Claude Haiku API | ✅ Running |
| Storage | Notion (4 databases) | ✅ Running |
| File monitoring | Google Drive API | ✅ Running |

### To Add
| Component | Technology | Priority |
|-----------|------------|----------|
| Vector DB | Supabase + pgvector | 🔴 High |
| Embeddings | Local model (BGE/MiniLM) | 🔴 High |
| Notion sync | Supabase ↔ Notion | 🔴 High |
| Local LLM | Qwen2.5-32B / Llama-70B | 🟡 Medium |
| MCP servers | Calendar, Gmail, etc. | 🟡 Medium |
| Agent loop | Python service | 🟡 Medium |
| Voice interface | Whisper + TTS | 🟢 Later |

### Hardware
- **GPU**: NVIDIA RTX 5000 Ada (32GB VRAM)
  - Can run: Qwen2.5-32B, Llama-3.1-70B (Q4), local embeddings
  - Inference: 1-3 seconds for queries

---

## 📈 Implementation Phases

### Phase 1: Knowledge Gathering ← **START HERE**
**Goal**: Get all data into Supabase for RAG

- [ ] Set up Supabase project (self-hosted or cloud)
- [ ] Create database schema for all data types
- [ ] Set up pgvector extension
- [ ] Build Notion → Supabase sync
- [ ] Store transcripts with embeddings
- [ ] Build basic RAG query endpoint
- [ ] Test: "What do I know about X?"

### Phase 2: MCP Integration
**Goal**: Connect LLM to external services

- [ ] Set up Google Calendar MCP
- [ ] Set up Gmail MCP
- [ ] Configure Claude Desktop with all MCPs
- [ ] Test: Auto-extract calendar events from messages
- [ ] Test: Draft email replies with context

### Phase 3: Agent Loop
**Goal**: Proactive monitoring and suggestions

- [ ] Build message monitoring (Beeper webhook/polling)
- [ ] Auto-extract: people, dates, action items
- [ ] Background context updates to Supabase
- [ ] Notification system for proposed actions
- [ ] Approval interface (Telegram bot? Web UI?)

### Phase 4: Local LLM
**Goal**: Reduce costs, increase privacy

- [ ] Set up vLLM with Qwen2.5-32B
- [ ] Connect MCP servers to local LLM
- [ ] Hybrid routing: simple queries → local, complex → Claude
- [ ] 24/7 agent running on local hardware

### Phase 5: Voice Interface
**Goal**: Conversational interaction

- [ ] Real-time voice input (Whisper streaming)
- [ ] RAG query with voice
- [ ] TTS response (Piper or similar)
- [ ] Wake word detection (optional)

---

## 💰 Cost Projections

| Phase | Monthly Cost |
|-------|--------------|
| Current (Jarvis) | ~$5-10 (Modal + Claude Haiku) |
| + Supabase | +$0-25 |
| + More Claude API | +$10-20 |
| Full local LLM | ~$5 (electricity) |
| **Total (hybrid)** | **$20-50/mo** |
| **Total (full local)** | **$5-15/mo** |

---

## 🔐 Privacy & Control Principles

1. **Data stays local/self-hosted** where possible
2. **Human approves all external actions** (messages, emails, calendar)
3. **Audit log** of all agent actions
4. **Kill switch** - ability to disable agent instantly
5. **Gradual trust** - start with notifications, graduate to auto-actions

---

## 🎯 Success Metrics

1. **Recall**: Can answer "What do I know about X?" accurately
2. **Speed**: < 2 seconds for RAG queries
3. **Coverage**: 90%+ of communications indexed
4. **Action accuracy**: Proposed actions are correct 95%+ of time
5. **Time saved**: Reduce admin work by 1+ hour/day

---

## 📝 About Aaron (System Context)

> This context is provided to all LLM interactions for personalized assistance.

Aaron is a German engineer based in Sydney, currently in transition after being the first employee at Algenie, an Australian biotech startup developing photobioreactor technology for algae and cyanobacteria cultivation. He holds two master's degrees from Germany and Tsinghua University in China, and previously worked in consulting before moving into the startup world to pursue more tangible, impact-driven work.

**Core interests**: Climate tech, biotech, agritech, foodtech, longevity

**Technical background**: 
- Hardware: Embedded systems (Arduino, ESP32)
- Software: Python automation, custom infrastructure
- Preference: Self-hosted and open-source over subscriptions

**Current situation**:
- Systematic about relationship management (Notion CRM)
- Preparing to relocate to Singapore/Southeast Asia
- Exploring startup opportunities in the region

---

## 🚀 Next Action

**Start Phase 1**: Set up Supabase and begin syncing Notion data.

```
1. Create Supabase project
2. Enable pgvector extension
3. Create tables: transcripts, meetings, people, reflections, tasks
4. Build sync script: Notion → Supabase
5. Add embedding generation to Jarvis pipeline
6. Build RAG query endpoint
```

---

*Document created: November 29, 2025*
*Last updated: November 29, 2025*
