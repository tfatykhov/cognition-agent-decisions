---
layout: page
title: "Nous — A Mind That Remembers"
description: "Meet Nous, the first cognitive agent built on the FORGE architecture. It remembers every conversation, learns from every decision, sleeps to consolidate, and never forgets who you are."
---

<style>
/* Nous Landing Page Styles */
.nous-hero {
  text-align: center;
  padding: 4rem 1rem 3rem;
  max-width: 800px;
  margin: 0 auto;
}

.nous-hero h1 {
  font-size: 3rem;
  font-weight: 800;
  background: linear-gradient(135deg, #6366f1, #a78bfa, #c084fc);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 0.5rem;
  margin-top: 0 !important;
  padding-top: 0 !important;
  border-top: none !important;
  line-height: 1.2;
}

.nous-hero .subtitle {
  font-size: 1.4rem;
  color: var(--vp-c-text-2);
  margin-top: 0.5rem;
  margin-bottom: 1.5rem;
}

.nous-hero .tagline {
  font-size: 1.1rem;
  color: var(--vp-c-text-3);
  max-width: 600px;
  margin: 0 auto 2rem;
  line-height: 1.6;
}

.brand-hierarchy {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  margin: 2rem auto;
  flex-wrap: wrap;
}

.brand-pill {
  padding: 0.5rem 1.2rem;
  border-radius: 999px;
  font-weight: 600;
  font-size: 0.9rem;
}

.brand-pill.company {
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.3);
  color: #818cf8;
}

.brand-pill.arch {
  background: rgba(167, 139, 250, 0.15);
  border: 1px solid rgba(167, 139, 250, 0.3);
  color: #a78bfa;
}

.brand-pill.agent {
  background: rgba(192, 132, 252, 0.15);
  border: 1px solid rgba(192, 132, 252, 0.3);
  color: #c084fc;
}

.brand-arrow {
  color: var(--vp-c-text-3);
  font-size: 1.2rem;
}

/* Stats Bar */
.stats-bar {
  display: flex;
  justify-content: center;
  gap: 2rem;
  padding: 1.5rem 0;
  margin: 2rem auto;
  max-width: 700px;
  border-top: 1px solid var(--vp-c-divider);
  border-bottom: 1px solid var(--vp-c-divider);
  flex-wrap: wrap;
}

.stat-item {
  text-align: center;
}

.stat-number {
  font-size: 1.8rem;
  font-weight: 800;
  background: linear-gradient(135deg, #818cf8, #c084fc);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.stat-label {
  font-size: 0.8rem;
  color: var(--vp-c-text-3);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Section Styles */
.nous-section {
  max-width: 900px;
  margin: 0 auto;
  padding: 3rem 1rem;
}

.nous-section h2 {
  font-size: 1.8rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
  margin-top: 0 !important;
  padding-top: 0 !important;
  border-top: none !important;
}

.nous-section .section-sub {
  color: var(--vp-c-text-3);
  margin-bottom: 2rem;
  font-size: 1rem;
}

/* Card Grid */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.25rem;
  margin-top: 1.5rem;
}

.card {
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  padding: 1.5rem;
  transition: all 0.25s ease;
}

.card:hover {
  border-color: #6366f1;
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.1);
}

.card .card-icon {
  font-size: 1.5rem;
  margin-bottom: 0.5rem;
}

.card h3 {
  font-size: 1.1rem;
  font-weight: 600;
  margin: 0 0 0.5rem 0;
  border-top: none !important;
  padding-top: 0 !important;
}

.card p {
  color: var(--vp-c-text-2);
  font-size: 0.9rem;
  line-height: 1.5;
  margin: 0;
}

/* Two Organs Layout */
.organs-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-top: 1.5rem;
}

@media (max-width: 640px) {
  .organs-grid {
    grid-template-columns: 1fr;
  }
}

.organ-card {
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  padding: 1.5rem;
}

.organ-card {
  transition: all 0.25s ease;
}

.organ-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
}

.organ-card.heart {
  border-top: 3px solid #f472b6;
}

.organ-card.brain {
  border-top: 3px solid #6366f1;
}

.organ-card h3 {
  font-size: 1.3rem;
  font-weight: 700;
  margin: 0 0 0.25rem 0;
  border-top: none !important;
  padding-top: 0 !important;
}

.organ-card .organ-sub {
  color: var(--vp-c-text-3);
  font-size: 0.85rem;
  margin-bottom: 1rem;
}

.organ-card ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.organ-card li {
  padding: 0.4rem 0;
  font-size: 0.9rem;
  color: var(--vp-c-text-2);
  border-bottom: 1px solid var(--vp-c-divider);
}

.organ-card li:last-child {
  border-bottom: none;
}

.organ-card li strong {
  color: var(--vp-c-text-1);
}

/* Cognitive Loop */
.loop-steps {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-top: 1.5rem;
  position: relative;
}

.loop-step {
  display: flex;
  gap: 1.25rem;
  align-items: flex-start;
  padding: 1rem 0;
  position: relative;
}

.loop-step::before {
  content: '';
  position: absolute;
  left: 20px;
  top: 42px;
  bottom: 0;
  width: 2px;
  background: linear-gradient(to bottom, #6366f1, var(--vp-c-divider));
}

.loop-step:last-child::before {
  display: none;
}

.step-marker {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 1.1rem;
  flex-shrink: 0;
  z-index: 1;
  color: white;
}

.step-marker.f { background: #6366f1; }
.step-marker.o { background: #8b5cf6; }
.step-marker.r { background: #a78bfa; }
.step-marker.g { background: #c084fc; }
.step-marker.e { background: #e879f9; }

.step-content h4 {
  margin: 0 0 0.25rem;
  font-size: 1rem;
  font-weight: 600;
}

.step-content p {
  margin: 0;
  color: var(--vp-c-text-2);
  font-size: 0.9rem;
  line-height: 1.5;
}

/* Chat Demo */
.chat-demo {
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  padding: 1.5rem;
  margin-top: 1.5rem;
  max-width: 700px;
}

.chat-msg {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1rem;
  align-items: flex-start;
}

.chat-msg:last-child {
  margin-bottom: 0;
}

.chat-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  flex-shrink: 0;
  font-weight: 600;
}

.chat-avatar.user {
  background: rgba(99, 102, 241, 0.2);
  color: #818cf8;
}

.chat-avatar.nous {
  background: rgba(192, 132, 252, 0.2);
  color: #c084fc;
}

.chat-bubble {
  background: var(--vp-c-bg);
  border: 1px solid var(--vp-c-divider);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  font-size: 0.9rem;
  line-height: 1.5;
  color: var(--vp-c-text-1);
}

.chat-bubble .meta {
  font-size: 0.75rem;
  color: var(--vp-c-text-3);
  margin-top: 0.5rem;
  font-style: italic;
}

/* Sleep Cards */
.sleep-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
  margin-top: 1.5rem;
}

.sleep-card {
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  padding: 1.25rem;
  text-align: center;
  transition: all 0.25s ease;
}

.sleep-card:hover {
  border-color: #6366f1;
  transform: translateY(-3px);
}

.sleep-card .sleep-icon {
  font-size: 1.5rem;
  margin-bottom: 0.5rem;
}

.sleep-card h4 {
  margin: 0 0 0.4rem;
  font-size: 0.95rem;
  font-weight: 600;
}

.sleep-card p {
  margin: 0;
  font-size: 0.8rem;
  color: var(--vp-c-text-3);
  line-height: 1.4;
}

/* Censor Table */
.censor-grid {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 1.5rem;
}

.censor-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-divider);
  border-radius: 8px;
  padding: 0.75rem 1rem;
}

.censor-badge {
  padding: 0.25rem 0.6rem;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  flex-shrink: 0;
  min-width: 70px;
  text-align: center;
}

.censor-badge.warn {
  background: rgba(251, 191, 36, 0.2);
  color: #fbbf24;
}

.censor-badge.block {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.censor-badge.absolute {
  background: rgba(220, 38, 38, 0.3);
  color: #fca5a5;
  border: 1px solid rgba(220, 38, 38, 0.4);
}

.censor-text {
  font-size: 0.85rem;
  color: var(--vp-c-text-2);
}

/* Quote */
.minsky-quote {
  text-align: center;
  max-width: 600px;
  margin: 3rem auto;
  padding: 2rem;
  border-left: 3px solid #6366f1;
  background: var(--vp-c-bg-soft);
  border-radius: 0 12px 12px 0;
}

.minsky-quote blockquote {
  font-size: 1.1rem;
  font-style: italic;
  color: var(--vp-c-text-1);
  margin: 0 0 0.5rem;
  border: none;
  padding: 0;
}

.minsky-quote .attribution {
  color: var(--vp-c-text-3);
  font-size: 0.85rem;
}

/* CTA */
.nous-cta {
  text-align: center;
  padding: 3rem 1rem;
  max-width: 600px;
  margin: 0 auto;
}

.nous-cta h2 {
  font-size: 1.6rem;
  font-weight: 700;
  margin-bottom: 1rem;
  border-top: none !important;
}

.nous-cta p {
  color: var(--vp-c-text-2);
  margin-bottom: 2rem;
  font-size: 1rem;
}

.cta-buttons {
  display: flex;
  gap: 1rem;
  justify-content: center;
  flex-wrap: wrap;
}

.cta-btn {
  padding: 0.75rem 1.5rem;
  border-radius: 8px;
  font-weight: 600;
  text-decoration: none;
  font-size: 0.95rem;
  transition: opacity 0.2s;
}

.cta-btn:hover {
  opacity: 0.9;
}

.cta-btn.primary {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: white;
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.3);
}

.cta-btn.primary:hover {
  box-shadow: 0 6px 24px rgba(99, 102, 241, 0.45);
  transform: translateY(-2px);
}

.cta-btn.secondary {
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-divider);
  color: var(--vp-c-text-1);
}

/* Cognitive Frames */
.frames-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-top: 1.5rem;
}

.frame-card {
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  padding: 1.25rem;
  transition: all 0.25s ease;
}

.frame-card:hover {
  border-color: #6366f1;
  transform: translateY(-3px);
}

.frame-card h4 {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
  font-weight: 600;
}

.frame-card p {
  margin: 0;
  font-size: 0.8rem;
  color: var(--vp-c-text-3);
  line-height: 1.4;
}

.frame-card .frame-tag {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
  text-transform: uppercase;
}

.frame-tag.debug { background: rgba(239, 68, 68, 0.15); color: #f87171; }
.frame-tag.research { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.frame-tag.decision { background: rgba(167, 139, 250, 0.15); color: #a78bfa; }
.frame-tag.task { background: rgba(52, 211, 153, 0.15); color: #34d399; }
.frame-tag.conversation { background: rgba(251, 191, 36, 0.15); color: #fbbf24; }
</style>

<!-- Hero -->
<div class="nous-hero">

<h1>Nous</h1>
<div class="subtitle">A Mind That Remembers</div>
<div class="tagline">
  The first cognitive agent built on the FORGE architecture.<br/>
  It remembers every conversation, learns from every decision, sleeps to consolidate, and never forgets who you are.
</div>

<div class="brand-hierarchy">
  <span class="brand-pill company">Cognition Engines</span>
  <span class="brand-arrow">→</span>
  <span class="brand-pill arch">FORGE Architecture</span>
  <span class="brand-arrow">→</span>
  <span class="brand-pill agent">Nous Agent</span>
</div>

<div class="stats-bar">
  <div class="stat-item">
    <div class="stat-number">44K+</div>
    <div class="stat-label">Lines of Code</div>
  </div>
  <div class="stat-item">
    <div class="stat-number">1,900+</div>
    <div class="stat-label">Tests</div>
  </div>
  <div class="stat-item">
    <div class="stat-number">53+</div>
    <div class="stat-label">Features Shipped</div>
  </div>
  <div class="stat-item">
    <div class="stat-number">5</div>
    <div class="stat-label">Memory Types</div>
  </div>
  <div class="stat-item">
    <div class="stat-number">18</div>
    <div class="stat-label">DB Tables</div>
  </div>
</div>

</div>

---

<!-- What Makes Nous Different -->
<div class="nous-section">

## What Makes Nous Different

<div class="section-sub">Not a chatbot with a longer context window. A mind with actual cognitive architecture.</div>

<div class="card-grid">
  <div class="card">
    <div class="card-icon">🧠</div>
    <h3>It Remembers</h3>
    <p>Five distinct memory stores — episodic, semantic, procedural, facts, and decisions. Not just "context stuffing" but structured recall across memory types, with semantic search and temporal awareness.</p>
  </div>
  <div class="card">
    <div class="card-icon">⚖️</div>
    <h3>It Decides</h3>
    <p>Every significant decision is recorded with confidence, reasoning traces, and outcome tracking. Nous queries past decisions before making new ones and calibrates against its own track record.</p>
  </div>
  <div class="card">
    <div class="card-icon">📚</div>
    <h3>It Learns</h3>
    <p>Facts extracted from conversations. Skills registered from documentation. Procedures that auto-activate when relevant. Knowledge compounds across sessions, not just within them.</p>
  </div>
  <div class="card">
    <div class="card-icon">😴</div>
    <h3>It Sleeps</h3>
    <p>Scheduled consolidation cycles prune redundant memories, strengthen important ones, recalibrate confidence scores, and surface overlooked connections — just like biological sleep.</p>
  </div>
  <div class="card">
    <div class="card-icon">🛡️</div>
    <h3>It Self-Monitors</h3>
    <p>Execution Ledger tracks every tool call. Censors prevent policy violations before they happen. Three severity levels — warn, block, absolute — create layered safety guarantees.</p>
  </div>
  <div class="card">
    <div class="card-icon">🔄</div>
    <h3>It Adapts</h3>
    <p>Cognitive frames match thinking mode to task type. Debugging mode prioritizes procedural memory. Research mode shifts to semantic recall. The agent thinks differently for different problems.</p>
  </div>
</div>

</div>

---

<!-- Two Organs -->
<div class="nous-section">

## Two Organs, One Mind

<div class="section-sub">Inspired by Minsky's Society of Mind — specialized agents cooperating, not one monolithic system.</div>

<div class="organs-grid">
  <div class="organ-card heart">
    <h3>❤️ Heart — Memory System</h3>
    <div class="organ-sub">What happened, what we know, how to do things</div>
    <ul>
      <li><strong>Episodic</strong> — Conversation summaries with timestamps</li>
      <li><strong>Semantic</strong> — Extracted facts and knowledge</li>
      <li><strong>Procedural</strong> — Skills and how-to procedures</li>
      <li><strong>Facts</strong> — Structured key-value knowledge</li>
      <li><strong>Censors</strong> — Guardrail rules and triggers</li>
    </ul>
  </div>
  <div class="organ-card brain">
    <h3>🧠 Brain — Decision Intelligence</h3>
    <div class="organ-sub">What we decided, why, and how it turned out</div>
    <ul>
      <li><strong>Decision Log</strong> — Every choice with full reasoning</li>
      <li><strong>Deliberation Traces</strong> — The thinking behind decisions</li>
      <li><strong>Bridge-Definitions</strong> — Structure ↔ function mappings</li>
      <li><strong>Calibration Engine</strong> — Brier scores and accuracy tracking</li>
      <li><strong>Pattern Detection</strong> — Recurring decision patterns</li>
    </ul>
  </div>
</div>

</div>

---

<!-- FORGE Cognitive Loop -->
<div class="nous-section">

## The FORGE Cognitive Loop

<div class="section-sub">Every interaction flows through this five-phase cycle. Not a prompt chain — a cognitive architecture.</div>

<div class="loop-steps">
  <div class="loop-step">
    <div class="step-marker f">F</div>
    <div class="step-content">
      <h4>Fetch — Load Context</h4>
      <p>Recall relevant memories across all five stores. Pull similar past decisions from the Brain. Load user profile, active censors, and session state. The agent enters the conversation already knowing what matters.</p>
    </div>
  </div>
  <div class="loop-step">
    <div class="step-marker o">O</div>
    <div class="step-content">
      <h4>Orient — Frame the Problem</h4>
      <p>Select the right cognitive frame: debugging, research, decision, task, or conversation. Each frame shifts memory weights and reasoning strategy. Check guardrails and constraints before any action is taken.</p>
    </div>
  </div>
  <div class="loop-step">
    <div class="step-marker r">R</div>
    <div class="step-content">
      <h4>Resolve — Decide with Evidence</h4>
      <p>Deliberate using retrieved context. Record the decision with confidence level, supporting reasons (typed: analysis, empirical, pattern, constraint), and alternative paths considered.</p>
    </div>
  </div>
  <div class="loop-step">
    <div class="step-marker g">G</div>
    <div class="step-content">
      <h4>Go — Execute with Guardrails</h4>
      <p>Execute the chosen action. The Execution Ledger logs every tool call with timestamps and parameters. Censors run in real-time — warn, block, or absolutely prevent policy violations.</p>
    </div>
  </div>
  <div class="loop-step">
    <div class="step-marker e">E</div>
    <div class="step-content">
      <h4>Extract — Learn from Outcomes</h4>
      <p>Extract facts, update memory stores, recalibrate confidence. Summarize the episode for future recall. Every interaction makes the next one better — compounding intelligence, not compounding context.</p>
    </div>
  </div>
</div>

</div>

---

<!-- Cognitive Frames -->
<div class="nous-section">

## Cognitive Frames

<div class="section-sub">Different problems require different thinking. Nous automatically matches its cognitive mode to the task.</div>

<div class="frames-grid">
  <div class="frame-card">
    <div class="frame-tag debug">Debug</div>
    <h4>🔧 Debugging</h4>
    <p>Prioritizes procedural memory and systematic elimination. Pulls error patterns and known fixes first. Thinks in hypotheses.</p>
  </div>
  <div class="frame-card">
    <div class="frame-tag research">Research</div>
    <h4>🔬 Research</h4>
    <p>Shifts weight to semantic memory and wider recall radius. Casts a broad net across knowledge stores. Explores connections.</p>
  </div>
  <div class="frame-card">
    <div class="frame-tag decision">Decision</div>
    <h4>⚖️ Decision</h4>
    <p>Activates the Brain's decision log. Pulls similar past decisions with outcomes. Calibrates against historical accuracy.</p>
  </div>
  <div class="frame-card">
    <div class="frame-tag task">Task</div>
    <h4>🎯 Task Execution</h4>
    <p>Focuses on procedures and facts. Minimizes exploration, maximizes execution efficiency. Tracks progress through steps.</p>
  </div>
  <div class="frame-card">
    <div class="frame-tag conversation">Conversation</div>
    <h4>💬 Conversation</h4>
    <p>Balances all memory types. Prioritizes episodic recall for continuity. Proactively surfaces relevant context.</p>
  </div>
</div>

</div>

---

<!-- Memory in Action -->
<div class="nous-section">

## Memory in Action

<div class="section-sub">This isn't theoretical. Here's what actual memory recall looks like in conversation.</div>

<div class="chat-demo">
  <div class="chat-msg">
    <div class="chat-avatar user">TF</div>
    <div class="chat-bubble">What were we working on with the article last week?</div>
  </div>
  <div class="chat-msg">
    <div class="chat-avatar nous">N</div>
    <div class="chat-bubble">
      Last week we worked on the FORGE architecture article for LinkedIn. Here's what happened:
      <br/><br/>
      • <strong>Thursday</strong> — Wrote the initial draft covering the two-organ architecture (Heart + Brain), the cognitive loop, and sleep cycles
      <br/>• <strong>Friday</strong> — Added the Minsky "Frame Problem" section and cognitive frame deep dive based on reviewer feedback
      <br/>• <strong>Saturday</strong> — Renamed from "Nous" to "FORGE" architecture to avoid the Nous Research brand collision. Updated 14 references across the article.
      <br/><br/>
      The latest version (v3) is in your email with both .md and .docx formats. Ready to add the 7 image placeholders or publish?
      <div class="meta">📍 Sources: Episodic memory (3 episodes) · Decision log (rename decision, 0.92 confidence) · Fact store (brand hierarchy)</div>
    </div>
  </div>
</div>

</div>

---

<!-- Sleep Architecture -->
<div class="nous-section">

## Sleep Architecture

<div class="section-sub">Like biological brains, Nous has scheduled consolidation cycles that run during downtime.</div>

<div class="sleep-grid">
  <div class="sleep-card">
    <div class="sleep-icon">🧹</div>
    <h4>Prune</h4>
    <p>Remove redundant memories. Merge near-duplicate episodes. Clear expired session data.</p>
  </div>
  <div class="sleep-card">
    <div class="sleep-icon">🔗</div>
    <h4>Consolidate</h4>
    <p>Strengthen important memories. Cross-link related decisions. Build semantic bridges.</p>
  </div>
  <div class="sleep-card">
    <div class="sleep-icon">📐</div>
    <h4>Calibrate</h4>
    <p>Recalculate Brier scores. Update accuracy metrics. Flag overconfident patterns.</p>
  </div>
  <div class="sleep-card">
    <div class="sleep-icon">💡</div>
    <h4>Surface</h4>
    <p>Find overlooked connections. Identify emerging patterns. Generate insight summaries.</p>
  </div>
</div>

</div>

---

<!-- Guardrails -->
<div class="nous-section">

## Guardrails — Three Severity Levels

<div class="section-sub">Safety isn't a prompt instruction. It's enforced architecture with escalating severity.</div>

<div class="censor-grid">
  <div class="censor-row">
    <div class="censor-badge warn">Warn</div>
    <div class="censor-text">Flag but allow. "You're about to notify Tim at 2am — are you sure this is urgent enough?"</div>
  </div>
  <div class="censor-row">
    <div class="censor-badge block">Block</div>
    <div class="censor-text">Prevent and explain. "Blocked: Cannot commit directly to main. Create a branch and PR instead."</div>
  </div>
  <div class="censor-row">
    <div class="censor-badge absolute">Absolute</div>
    <div class="censor-text">Cannot be overridden, even by the user. API keys, credentials, and secrets are never stored as facts. Period.</div>
  </div>
</div>

<div style="margin-top: 1rem; font-size: 0.85rem; color: var(--vp-c-text-3);">
  Censors are learned from experience and policy. They persist across sessions, survive restarts, and cannot be prompt-injected away.
</div>

</div>

---

<!-- Minsky Quote -->
<div class="minsky-quote">
  <blockquote>"You don't really understand something until you can explain it to a computer. But you don't really understand intelligence until you can explain it as a society."</blockquote>
  <div class="attribution">— Marvin Minsky, <em>The Society of Mind</em> (1986)</div>
</div>

---

<!-- Get Started -->
<div class="nous-section">

## Get Started

Nous runs on the FORGE architecture via Cognition Engines. Two ways to start:

**Docker (full stack):**

```bash
git clone https://github.com/tfatykhov/cognition-agent-decisions
cd cognition-agent-decisions
cp .env.example .env
docker compose up -d
```

**MCP Integration (Claude Desktop / any MCP client):**

```json
{
  "mcpServers": {
    "nous": {
      "url": "http://localhost:8383/mcp/"
    }
  }
}
```

Nous exposes a Streamable HTTP MCP server. Tools: `nous_recall`, `nous_chat`, `nous_teach`, `nous_decide`. Full REST API also available for programmatic access.

→ [Nous on GitHub](https://github.com/tfatykhov/nous) · [Full Installation Guide](/reference/installation) · [MCP Quick Start](/reference/mcp-quickstart) · [Agent Quick Start](/guide/agent-quickstart)

</div>

---

<!-- CTA -->
<div class="nous-cta">

## FORGE is the architecture. Nous is the mind.

<p>Built on Minsky's Society of Mind. Powered by Cognition Engines.<br/>An agent that doesn't just respond — it remembers, decides, learns, and evolves.</p>

<div class="cta-buttons">
  <a href="https://github.com/tfatykhov/nous" class="cta-btn primary">Nous on GitHub</a>
  <a href="/guide/what-is-cognition-engines" class="cta-btn secondary">Learn About FORGE</a>
</div>

</div>
