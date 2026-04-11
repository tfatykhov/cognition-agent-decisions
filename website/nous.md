---
layout: page
title: "Nous — Continuous Memory Platform for AI Agents"
description: "AI that remembers, learns, and gets smarter. Built on the FORGE cognitive architecture, grounded in Minsky's Society of Mind and 12+ research papers."
---

<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');

  /* ===== CSS VARIABLES ===== */
  .nous-page {
    --bg-primary: #0a0a0f;
    --bg-secondary: #12121a;
    --bg-card: #1a1a2e;
    --bg-card-hover: #222240;
    --accent-blue: #4f7df5;
    --accent-cyan: #00d4ff;
    --accent-purple: #8b5cf6;
    --accent-pink: #ec4899;
    --accent-green: #10b981;
    --accent-orange: #f59e0b;
    --accent-red: #ef4444;
    --text-primary: #f0f0f5;
    --text-secondary: #a0a0b8;
    --text-muted: #6b6b80;
    --border: #2a2a40;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: var(--text-primary);
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 1rem;
  }

  /* Override VitePress defaults */
  .nous-page h1, .nous-page h2, .nous-page h3, .nous-page h4, .nous-page h5 {
    border: none !important;
    margin-top: 0 !important;
    padding-top: 0 !important;
    letter-spacing: -0.02em;
  }
  .nous-page a { text-decoration: none; }
  .nous-page ul { list-style: none; padding: 0; margin: 0; }
  .nous-page p { margin: 0; }

  /* ===== ANIMATED BACKGROUND ===== */
  .nous-bg-grid {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background-image:
      linear-gradient(rgba(79, 125, 245, 0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(79, 125, 245, 0.03) 1px, transparent 1px);
    background-size: 60px 60px;
    z-index: 0;
    pointer-events: none;
  }
  .nous-bg-glow-1 {
    position: fixed;
    top: -200px; right: -200px;
    width: 600px; height: 600px;
    background: radial-gradient(circle, rgba(79, 125, 245, 0.08) 0%, transparent 70%);
    border-radius: 50%;
    z-index: 0;
    pointer-events: none;
    animation: nousFloat1 20s ease-in-out infinite;
  }
  .nous-bg-glow-2 {
    position: fixed;
    bottom: -200px; left: -200px;
    width: 600px; height: 600px;
    background: radial-gradient(circle, rgba(139, 92, 246, 0.08) 0%, transparent 70%);
    border-radius: 50%;
    z-index: 0;
    pointer-events: none;
    animation: nousFloat2 25s ease-in-out infinite;
  }
  @keyframes nousFloat1 {
    0%, 100% { transform: translate(0, 0); }
    50% { transform: translate(-80px, 80px); }
  }
  @keyframes nousFloat2 {
    0%, 100% { transform: translate(0, 0); }
    50% { transform: translate(80px, -80px); }
  }

  /* ===== SECTIONS ===== */
  .nous-section {
    padding: 4rem 0;
    position: relative;
    z-index: 1;
  }
  .nous-section:nth-child(even) {
    background: linear-gradient(180deg, transparent, rgba(79, 125, 245, 0.02), transparent);
  }

  /* ===== HERO ===== */
  .nous-hero {
    min-height: 85vh;
    display: flex;
    align-items: center;
    padding-top: 2rem;
  }
  .nous-hero-content {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 3rem;
    align-items: center;
    width: 100%;
  }
  .nous-hero-text { max-width: 560px; }
  .nous-hero-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: rgba(79, 125, 245, 0.1);
    border: 1px solid rgba(79, 125, 245, 0.2);
    color: var(--accent-cyan);
    padding: 0.4rem 1rem;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-bottom: 1.5rem;
  }
  .nous-hero-eyebrow .dot {
    width: 6px; height: 6px;
    background: var(--accent-green);
    border-radius: 50%;
    animation: nousPulse 2s ease-in-out infinite;
  }
  @keyframes nousPulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
  .nous-hero h1 {
    font-size: 3.2rem !important;
    font-weight: 900 !important;
    line-height: 1.1 !important;
    margin-bottom: 1.5rem !important;
    color: var(--text-primary) !important;
  }
  .nous-gradient-text {
    background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue), var(--accent-purple));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .nous-hero-subtitle {
    font-size: 1.15rem;
    color: var(--text-secondary);
    line-height: 1.7;
    margin-bottom: 2rem;
  }
  .nous-hero-stats {
    display: flex;
    gap: 2.5rem;
  }
  .nous-hero-stat-value {
    font-size: 2rem;
    font-weight: 800;
    font-family: 'JetBrains Mono', monospace;
    background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .nous-hero-stat-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
  }
  .nous-hero-diagram svg {
    width: 100%;
    height: auto;
  }

  /* ===== SECTION HEADERS ===== */
  .nous-section-header {
    text-align: center;
    margin-bottom: 3rem;
  }
  .nous-section-tag {
    display: inline-block;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--accent-blue);
    margin-bottom: 0.75rem;
  }
  .nous-section-header h2 {
    font-size: 2.25rem !important;
    font-weight: 800 !important;
    color: var(--text-primary) !important;
    margin-bottom: 0.75rem !important;
  }
  .nous-section-header p {
    color: var(--text-secondary);
    font-size: 1.05rem;
    max-width: 600px;
    margin: 0 auto;
  }

  /* ===== PROBLEM / SOLUTION ===== */
  .nous-ps-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2rem;
  }
  .nous-ps-card {
    border-radius: 16px;
    padding: 2.5rem;
    border: 1px solid var(--border);
    position: relative;
    overflow: hidden;
  }
  .nous-ps-card.problem {
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.05), rgba(239, 68, 68, 0.02));
    border-color: rgba(239, 68, 68, 0.15);
  }
  .nous-ps-card.solution {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.05), rgba(16, 185, 129, 0.02));
    border-color: rgba(16, 185, 129, 0.15);
  }
  .nous-ps-icon {
    width: 48px; height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    margin-bottom: 1.25rem;
  }
  .problem .nous-ps-icon { background: rgba(239, 68, 68, 0.1); }
  .solution .nous-ps-icon { background: rgba(16, 185, 129, 0.1); }
  .nous-ps-card h3 {
    font-size: 1.25rem !important;
    font-weight: 700 !important;
    margin-bottom: 0.75rem !important;
  }
  .problem h3 { color: var(--accent-red) !important; }
  .solution h3 { color: var(--accent-green) !important; }
  .nous-ps-card > p {
    color: var(--text-secondary);
    font-size: 0.95rem;
    line-height: 1.7;
  }
  .nous-ps-list li {
    padding: 0.4rem 0;
    color: var(--text-secondary);
    font-size: 0.9rem;
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
  }
  .nous-ps-list li::before {
    content: '';
    width: 6px; height: 6px;
    border-radius: 50%;
    margin-top: 0.5rem;
    flex-shrink: 0;
  }
  .problem .nous-ps-list li::before { background: var(--accent-red); }
  .solution .nous-ps-list li::before { background: var(--accent-green); }

  /* ===== BRAIN/HEART DUALITY ===== */
  .nous-duality-grid {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    gap: 2rem;
    align-items: stretch;
  }
  .nous-duality-card {
    border-radius: 16px;
    padding: 2.5rem;
    border: 1px solid var(--border);
  }
  .nous-duality-card.brain-card {
    background: linear-gradient(135deg, rgba(79, 125, 245, 0.06), rgba(139, 92, 246, 0.04));
    border-color: rgba(79, 125, 245, 0.2);
  }
  .nous-duality-card.heart-card {
    background: linear-gradient(135deg, rgba(236, 72, 153, 0.06), rgba(245, 158, 11, 0.04));
    border-color: rgba(236, 72, 153, 0.2);
  }
  .nous-duality-card h3 {
    font-size: 1.5rem !important;
    font-weight: 800 !important;
    margin-bottom: 0.5rem !important;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .nous-duality-subtitle {
    color: var(--text-muted);
    font-size: 0.85rem;
    margin-bottom: 1.25rem;
    font-style: italic;
  }
  .nous-duality-list li {
    padding: 0.5rem 0;
    font-size: 0.9rem;
    color: var(--text-secondary);
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
    border-bottom: 1px solid rgba(255,255,255,0.04);
  }
  .nous-duality-list li:last-child { border-bottom: none; }
  .nous-duality-list .icon { font-size: 0.8rem; margin-top: 0.15rem; }
  .nous-duality-connector {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    color: var(--text-muted);
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.05em;
  }
  .nous-connector-line {
    width: 2px;
    height: 40px;
    background: linear-gradient(to bottom, var(--accent-blue), var(--accent-pink));
    border-radius: 1px;
  }
  .nous-connector-icon {
    width: 40px; height: 40px;
    border-radius: 50%;
    background: var(--bg-card);
    border: 2px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
  }

  /* ===== LOOP DIAGRAM ===== */
  .nous-loop-container {
    display: flex;
    justify-content: center;
    margin: 2rem 0;
  }
  .nous-loop-container svg {
    max-width: 600px;
    width: 100%;
    height: auto;
  }

  /* ===== MEMORY TYPES ===== */
  .nous-memory-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 1rem;
  }
  .nous-memory-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    text-align: center;
    transition: all 0.3s ease;
    position: relative;
  }
  .nous-memory-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 40px rgba(0,0,0,0.3);
  }
  .nous-mt-icon { font-size: 2rem; margin-bottom: 0.75rem; }
  .nous-memory-card h4 {
    font-size: 0.9rem !important;
    font-weight: 700 !important;
    margin-bottom: 0.4rem !important;
    color: var(--text-primary) !important;
  }
  .nous-memory-card p {
    font-size: 0.75rem;
    color: var(--text-muted);
    line-height: 1.5;
  }
  .nous-mt-accent {
    position: absolute;
    top: 0; left: 50%;
    transform: translateX(-50%);
    width: 40px; height: 3px;
    border-radius: 0 0 3px 3px;
  }

  /* ===== FEATURES GRID ===== */
  .nous-features-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.25rem;
  }
  .nous-feature-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.75rem;
    transition: all 0.3s ease;
  }
  .nous-feature-card:hover {
    border-color: var(--accent-purple);
    box-shadow: 0 4px 20px rgba(139, 92, 246, 0.08);
  }
  .nous-f-icon { font-size: 1.5rem; margin-bottom: 0.75rem; }
  .nous-feature-card h4 {
    font-size: 0.95rem !important;
    font-weight: 700 !important;
    margin-bottom: 0.4rem !important;
    color: var(--text-primary) !important;
  }
  .nous-feature-card p {
    font-size: 0.8rem;
    color: var(--text-secondary);
    line-height: 1.6;
  }
  .nous-f-tag {
    display: inline-block;
    margin-top: 0.6rem;
    font-size: 0.65rem;
    font-weight: 600;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .nous-f-tag.shipped { background: rgba(16,185,129,0.1); color: var(--accent-green); }
  .nous-f-tag.live { background: rgba(0,212,255,0.1); color: var(--accent-cyan); }
  .nous-f-tag.unique { background: rgba(139,92,246,0.1); color: var(--accent-purple); }

  /* ===== COMPETITIVE MOAT ===== */
  .nous-moat-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1.25rem;
  }
  .nous-moat-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    display: flex;
    gap: 1rem;
    align-items: flex-start;
    transition: all 0.3s ease;
  }
  .nous-moat-card:hover {
    border-color: var(--accent-green);
  }
  .nous-moat-number {
    font-size: 1.5rem;
    font-weight: 900;
    font-family: 'JetBrains Mono', monospace;
    color: var(--accent-blue);
    opacity: 0.4;
    flex-shrink: 0;
    width: 2rem;
  }
  .nous-moat-card h4 {
    font-size: 0.95rem !important;
    font-weight: 700 !important;
    margin-bottom: 0.3rem !important;
    color: var(--text-primary) !important;
  }
  .nous-moat-card p {
    font-size: 0.8rem;
    color: var(--text-secondary);
    line-height: 1.5;
  }

  /* ===== METRICS BAR ===== */
  .nous-metrics-bar {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 1rem;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 2rem;
  }
  .nous-metric-item { text-align: center; }
  .nous-metric-value {
    font-size: 1.75rem;
    font-weight: 800;
    font-family: 'JetBrains Mono', monospace;
    background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .nous-metric-label {
    font-size: 0.7rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    margin-top: 0.25rem;
  }

  /* ===== RESEARCH GRID ===== */
  .nous-research-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
  }
  .nous-research-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.25rem;
    text-align: center;
  }
  .nous-research-card .emoji { font-size: 1.5rem; margin-bottom: 0.5rem; }
  .nous-research-card h5 {
    font-size: 0.8rem !important;
    font-weight: 700 !important;
    margin-bottom: 0.25rem !important;
    color: var(--text-primary) !important;
  }
  .nous-research-card p {
    font-size: 0.7rem;
    color: var(--text-muted);
    line-height: 1.4;
  }

  /* ===== BRAND BAR ===== */
  .nous-brand-bar {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 2rem;
    padding: 2rem;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 16px;
    margin-top: 3rem;
  }
  .nous-brand-item { text-align: center; }
  .nous-brand-item .label {
    font-size: 0.65rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 600;
  }
  .nous-brand-item .name {
    font-size: 1.25rem;
    font-weight: 800;
    margin-top: 0.2rem;
  }
  .nous-brand-arrow {
    color: var(--text-muted);
    font-size: 1.25rem;
  }

  /* ===== FOOTER ===== */
  .nous-footer {
    padding: 3rem 0;
    border-top: 1px solid var(--border);
    text-align: center;
  }
  .nous-footer p {
    color: var(--text-muted);
    font-size: 0.85rem;
  }
  .nous-footer a {
    color: var(--accent-cyan);
    text-decoration: none;
  }

  /* ===== RESPONSIVE ===== */
  @media (max-width: 900px) {
    .nous-hero-content { grid-template-columns: 1fr; }
    .nous-hero h1 { font-size: 2.5rem !important; }
    .nous-duality-grid { grid-template-columns: 1fr; }
    .nous-duality-connector { flex-direction: row; }
    .nous-connector-line { width: 40px; height: 2px; }
    .nous-memory-grid { grid-template-columns: repeat(2, 1fr); }
    .nous-features-grid { grid-template-columns: 1fr; }
    .nous-moat-grid { grid-template-columns: 1fr; }
    .nous-metrics-bar { grid-template-columns: repeat(3, 1fr); gap: 1.5rem; }
    .nous-research-grid { grid-template-columns: repeat(2, 1fr); }
    .nous-ps-grid { grid-template-columns: 1fr; }
    .nous-brand-bar { flex-direction: column; gap: 1rem; }
    .nous-brand-arrow { transform: rotate(90deg); }
  }

  /* ===== SCROLL ANIMATIONS ===== */
  .nous-fade-up {
    opacity: 0;
    transform: translateY(30px);
    transition: all 0.6s ease;
  }
  .nous-fade-up.visible {
    opacity: 1;
    transform: translateY(0);
  }
</style>

<div class="nous-page">

<div class="nous-bg-grid"></div>
<div class="nous-bg-glow-1"></div>
<div class="nous-bg-glow-2"></div>

<!-- ===== HERO ===== -->
<div class="nous-section nous-hero">
  <div class="nous-hero-content">
    <div class="nous-hero-text">
      <div class="nous-hero-eyebrow">
        <span class="dot"></span>
        Cognition Engines → FORGE Architecture
      </div>
      <h1>AI That <span class="nous-gradient-text">Remembers, Learns,</span> and <span class="nous-gradient-text">Gets Smarter</span></h1>
      <p class="nous-hero-subtitle">
        Nous is a <strong>continuous memory platform</strong> for AI agents — inspired by Minsky's <em>Society of Mind</em> and grounded in cognitive science. It gives any LLM persistent memory, decision intelligence, and the ability to learn from its own mistakes.
      </p>
      <div class="nous-hero-stats">
        <div>
          <div class="nous-hero-stat-value">86.6K</div>
          <div class="nous-hero-stat-label">Lines of Code</div>
        </div>
        <div>
          <div class="nous-hero-stat-value">2,625</div>
          <div class="nous-hero-stat-label">Automated Tests</div>
        </div>
        <div>
          <div class="nous-hero-stat-value">39</div>
          <div class="nous-hero-stat-label">Shipped Features</div>
        </div>
        <div>
          <div class="nous-hero-stat-value">860+</div>
          <div class="nous-hero-stat-label">Commits</div>
        </div>
      </div>
    </div>

    <!-- Hero Architecture Diagram -->
    <div class="nous-hero-diagram">
      <svg viewBox="0 0 500 480" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <radialGradient id="bgGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="#4f7df5" stop-opacity="0.06"/>
            <stop offset="100%" stop-color="#4f7df5" stop-opacity="0"/>
          </radialGradient>
          <linearGradient id="brainGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#4f7df5"/>
            <stop offset="100%" stop-color="#8b5cf6"/>
          </linearGradient>
          <linearGradient id="heartGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#ec4899"/>
            <stop offset="100%" stop-color="#f59e0b"/>
          </linearGradient>
          <linearGradient id="loopGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#00d4ff"/>
            <stop offset="100%" stop-color="#10b981"/>
          </linearGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="blur"/>
            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
          <marker id="arrowOrange" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <path d="M0,0 L8,3 L0,6" fill="#f59e0b" opacity="0.5"/>
          </marker>
        </defs>
        <rect width="500" height="480" fill="url(#bgGlow)"/>
        <!-- Cognitive Loop rings -->
        <circle cx="250" cy="220" r="120" stroke="url(#loopGrad)" stroke-width="2" fill="none" stroke-dasharray="8 4" opacity="0.5">
          <animateTransform attributeName="transform" type="rotate" from="0 250 220" to="360 250 220" dur="60s" repeatCount="indefinite"/>
        </circle>
        <circle cx="250" cy="220" r="90" stroke="url(#loopGrad)" stroke-width="1" fill="none" opacity="0.2">
          <animateTransform attributeName="transform" type="rotate" from="360 250 220" to="0 250 220" dur="45s" repeatCount="indefinite"/>
        </circle>
        <!-- Brain Module -->
        <rect x="30" y="120" width="160" height="200" rx="16" fill="#1a1a2e" stroke="url(#brainGrad)" stroke-width="1.5"/>
        <text x="110" y="152" text-anchor="middle" fill="#4f7df5" font-size="12" font-weight="800" font-family="Inter, sans-serif">🧠 BRAIN</text>
        <text x="110" y="172" text-anchor="middle" fill="#a0a0b8" font-size="8" font-family="Inter, sans-serif">Evaluation &amp; Judgment</text>
        <line x1="50" y1="182" x2="170" y2="182" stroke="#2a2a40" stroke-width="1"/>
        <text x="55" y="200" fill="#a0a0b8" font-size="8.5" font-family="Inter, sans-serif">◆ Quality Scoring</text>
        <text x="55" y="216" fill="#a0a0b8" font-size="8.5" font-family="Inter, sans-serif">◆ Brier Calibration</text>
        <text x="55" y="232" fill="#a0a0b8" font-size="8.5" font-family="Inter, sans-serif">◆ Decision Tracking</text>
        <text x="55" y="248" fill="#a0a0b8" font-size="8.5" font-family="Inter, sans-serif">◆ Knowledge Graph</text>
        <text x="55" y="264" fill="#a0a0b8" font-size="8.5" font-family="Inter, sans-serif">◆ Bridge Definitions</text>
        <text x="55" y="280" fill="#a0a0b8" font-size="8.5" font-family="Inter, sans-serif">◆ CEL Guardrails</text>
        <!-- Heart Module -->
        <rect x="310" y="120" width="160" height="200" rx="16" fill="#1a1a2e" stroke="url(#heartGrad)" stroke-width="1.5"/>
        <text x="390" y="152" text-anchor="middle" fill="#ec4899" font-size="12" font-weight="800" font-family="Inter, sans-serif">❤️ HEART</text>
        <text x="390" y="172" text-anchor="middle" fill="#a0a0b8" font-size="8" font-family="Inter, sans-serif">Memory &amp; Identity</text>
        <line x1="330" y1="182" x2="450" y2="182" stroke="#2a2a40" stroke-width="1"/>
        <text x="335" y="200" fill="#a0a0b8" font-size="8.5" font-family="Inter, sans-serif">◆ Episodic Memory</text>
        <text x="335" y="216" fill="#a0a0b8" font-size="8.5" font-family="Inter, sans-serif">◆ Semantic Facts</text>
        <text x="335" y="232" fill="#a0a0b8" font-size="8.5" font-family="Inter, sans-serif">◆ Procedural Skills</text>
        <text x="335" y="248" fill="#a0a0b8" font-size="8.5" font-family="Inter, sans-serif">◆ Working Memory</text>
        <text x="335" y="264" fill="#a0a0b8" font-size="8.5" font-family="Inter, sans-serif">◆ Censors</text>
        <text x="335" y="280" fill="#a0a0b8" font-size="8.5" font-family="Inter, sans-serif">◆ Identity Store</text>
        <!-- Connections -->
        <line x1="190" y1="220" x2="220" y2="220" stroke="#4f7df5" stroke-width="1.5" opacity="0.5" stroke-dasharray="4 3"/>
        <line x1="280" y1="220" x2="310" y2="220" stroke="#ec4899" stroke-width="1.5" opacity="0.5" stroke-dasharray="4 3"/>
        <!-- Center -->
        <circle cx="250" cy="220" r="38" fill="#1a1a2e" stroke="#2a2a40" stroke-width="1.5"/>
        <text x="250" y="214" text-anchor="middle" fill="#00d4ff" font-size="9" font-weight="700" font-family="Inter, sans-serif">COGNITIVE</text>
        <text x="250" y="228" text-anchor="middle" fill="#00d4ff" font-size="9" font-weight="700" font-family="Inter, sans-serif">LOOP</text>
        <!-- Phase labels -->
        <text x="250" y="88" text-anchor="middle" fill="#10b981" font-size="8" font-weight="600" font-family="Inter, sans-serif">SENSE</text>
        <text x="345" y="138" text-anchor="middle" fill="#10b981" font-size="8" font-weight="600" font-family="Inter, sans-serif">FRAME</text>
        <text x="345" y="310" text-anchor="middle" fill="#10b981" font-size="8" font-weight="600" font-family="Inter, sans-serif">DELIBERATE</text>
        <text x="250" y="355" text-anchor="middle" fill="#10b981" font-size="8" font-weight="600" font-family="Inter, sans-serif">ACT</text>
        <text x="155" y="310" text-anchor="middle" fill="#10b981" font-size="8" font-weight="600" font-family="Inter, sans-serif">MONITOR</text>
        <text x="155" y="138" text-anchor="middle" fill="#10b981" font-size="8" font-weight="600" font-family="Inter, sans-serif">RECALL</text>
        <!-- Phase dots -->
        <circle cx="250" cy="100" r="4" fill="#10b981" filter="url(#glow)"/>
        <circle cx="340" cy="145" r="4" fill="#10b981" filter="url(#glow)"/>
        <circle cx="340" cy="300" r="4" fill="#10b981" filter="url(#glow)"/>
        <circle cx="250" cy="340" r="4" fill="#10b981" filter="url(#glow)"/>
        <circle cx="160" cy="300" r="4" fill="#10b981" filter="url(#glow)"/>
        <circle cx="160" cy="145" r="4" fill="#10b981" filter="url(#glow)"/>
        <!-- Sleep -->
        <rect x="150" y="390" width="200" height="60" rx="12" fill="#1a1a2e" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="6 3"/>
        <text x="250" y="416" text-anchor="middle" fill="#f59e0b" font-size="10" font-weight="700" font-family="Inter, sans-serif">🌙 SLEEP CONSOLIDATION</text>
        <text x="250" y="434" text-anchor="middle" fill="#a0a0b8" font-size="7.5" font-family="Inter, sans-serif">5-Phase Autonomous Memory Optimization</text>
        <path d="M250 345 L250 388" stroke="#f59e0b" stroke-width="1" stroke-dasharray="4 3" opacity="0.5" marker-end="url(#arrowOrange)"/>
      </svg>
    </div>
  </div>
</div>

<!-- ===== PROBLEM / SOLUTION ===== -->
<div class="nous-section">
  <div class="nous-section-header nous-fade-up">
    <div class="nous-section-tag">The Problem</div>
    <h2>AI Agents Are Goldfish with PhDs</h2>
    <p>Every major AI agent today forgets everything between sessions. They're brilliant — and amnesiac.</p>
  </div>
  <div class="nous-ps-grid nous-fade-up">
    <div class="nous-ps-card problem">
      <div class="nous-ps-icon">💀</div>
      <h3>Without Continuous Memory</h3>
      <p>Today's AI agents are stateless by default. Every conversation starts from zero.</p>
      <ul class="nous-ps-list">
        <li>Repeated mistakes — no correction learning</li>
        <li>Lost context — user re-explains preferences every session</li>
        <li>No skill accumulation — can't get better at what it does</li>
        <li>No decision tracking — no idea what worked or failed</li>
        <li>No identity — each session is a different agent</li>
      </ul>
    </div>
    <div class="nous-ps-card solution">
      <div class="nous-ps-icon">🧠</div>
      <h3>With Nous</h3>
      <p>A cognitive memory layer that makes any LLM agent persistent, learning, and self-improving.</p>
      <ul class="nous-ps-list">
        <li>Correction Learning — mistakes become permanent guardrails</li>
        <li>5 memory types — episodic, semantic, procedural, working, censors</li>
        <li>Sleep consolidation — autonomous overnight memory optimization</li>
        <li>Decision intelligence — Brier-scored prediction calibration</li>
        <li>Persistent identity — same agent personality across all sessions</li>
      </ul>
    </div>
  </div>
</div>

<!-- ===== ARCHITECTURE: BRAIN / HEART ===== -->
<div class="nous-section" id="architecture">
  <div class="nous-section-header nous-fade-up">
    <div class="nous-section-tag">Architecture</div>
    <h2>Brain / Heart Duality</h2>
    <p>Inspired by Minsky's Society of Mind — cognition split into evaluation (Brain) and memory (Heart)</p>
  </div>
  <div class="nous-duality-grid nous-fade-up">
    <div class="nous-duality-card brain-card">
      <h3>🧠 Brain</h3>
      <div class="nous-duality-subtitle">Evaluation, judgment, and meta-cognition</div>
      <ul class="nous-duality-list">
        <li><span class="icon">⚡</span> <div><strong>Quality Scoring</strong> — LLM-judged response quality with multi-dimensional rubric</div></li>
        <li><span class="icon">🎯</span> <div><strong>Brier Calibration</strong> — tracks prediction accuracy over time, self-correcting confidence</div></li>
        <li><span class="icon">📊</span> <div><strong>Decision Tracking</strong> — every decision logged with outcome, enabling learning from history</div></li>
        <li><span class="icon">🕸️</span> <div><strong>Knowledge Graph</strong> — relationships between facts, entities, episodes via pgvector + spreading activation</div></li>
        <li><span class="icon">🔗</span> <div><strong>Bridge Definitions</strong> — cross-concept connections that enrich retrieval</div></li>
        <li><span class="icon">🛡️</span> <div><strong>CEL Guardrails</strong> — Common Expression Language rules enforcing behavioral bounds</div></li>
      </ul>
    </div>
    <div class="nous-duality-connector">
      <div class="nous-connector-line"></div>
      <div class="nous-connector-icon">⚡</div>
      <div class="nous-connector-line"></div>
      <span style="writing-mode: vertical-rl; transform: rotate(180deg); font-size: 0.65rem; letter-spacing: 0.15em;">EVENT BUS</span>
    </div>
    <div class="nous-duality-card heart-card">
      <h3>❤️ Heart</h3>
      <div class="nous-duality-subtitle">Memory, identity, and persistent self</div>
      <ul class="nous-duality-list">
        <li><span class="icon">📖</span> <div><strong>Episodes</strong> — conversation summaries with emotional valence, temporally indexed</div></li>
        <li><span class="icon">💡</span> <div><strong>Facts</strong> — extracted knowledge with confidence scores, categories, decay tracking</div></li>
        <li><span class="icon">⚙️</span> <div><strong>Procedures</strong> — learned skills with triggers, tools, and effectiveness ratings</div></li>
        <li><span class="icon">🔄</span> <div><strong>Working Memory</strong> — dynamic per-session context: frame, task, loaded facts, recent episodes</div></li>
        <li><span class="icon">🚫</span> <div><strong>Censors</strong> — behavioral guardrails that block harmful patterns before they execute</div></li>
        <li><span class="icon">🪪</span> <div><strong>Identity</strong> — persistent personality and initiation protocol across all sessions</div></li>
      </ul>
    </div>
  </div>
</div>

<!-- ===== COGNITIVE LOOP ===== -->
<div class="nous-section">
  <div class="nous-section-header nous-fade-up">
    <div class="nous-section-tag">Core Engine</div>
    <h2>The 7-Phase Cognitive Loop</h2>
    <p>Every interaction passes through a biologically-inspired processing pipeline</p>
  </div>
  <div class="nous-loop-container nous-fade-up">
    <svg viewBox="0 0 600 520" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="lg1" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#10b981"/><stop offset="100%" stop-color="#00d4ff"/></linearGradient>
        <linearGradient id="lg2" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#00d4ff"/><stop offset="100%" stop-color="#4f7df5"/></linearGradient>
        <linearGradient id="lg3" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#4f7df5"/><stop offset="100%" stop-color="#8b5cf6"/></linearGradient>
        <linearGradient id="lg4" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#8b5cf6"/><stop offset="100%" stop-color="#ec4899"/></linearGradient>
        <linearGradient id="lg5" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#ec4899"/><stop offset="100%" stop-color="#f59e0b"/></linearGradient>
        <linearGradient id="lg6" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#f59e0b"/><stop offset="100%" stop-color="#ef4444"/></linearGradient>
        <linearGradient id="lg7" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#ef4444"/><stop offset="100%" stop-color="#10b981"/></linearGradient>
        <marker id="arrowG" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6" fill="#00d4ff"/></marker>
        <marker id="arrowB" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6" fill="#4f7df5"/></marker>
        <marker id="arrowP" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6" fill="#8b5cf6"/></marker>
        <marker id="arrowPk" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6" fill="#ec4899"/></marker>
        <marker id="arrowO" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6" fill="#f59e0b"/></marker>
        <marker id="arrowR" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6" fill="#ef4444"/></marker>
        <marker id="arrowG2" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6" fill="#10b981"/></marker>
      </defs>
      <!-- Central ring -->
      <circle cx="300" cy="240" r="155" stroke="#2a2a40" stroke-width="2" fill="none"/>
      <circle cx="300" cy="240" r="155" stroke="url(#lg1)" stroke-width="2" fill="none" stroke-dasharray="140 840" stroke-dashoffset="0" opacity="0.6">
        <animateTransform attributeName="transform" type="rotate" from="0 300 240" to="360 300 240" dur="30s" repeatCount="indefinite"/>
      </circle>
      <!-- SENSE -->
      <circle cx="300" cy="75" r="32" fill="#1a1a2e" stroke="#10b981" stroke-width="2"/>
      <text x="300" y="70" text-anchor="middle" fill="#10b981" font-size="14" font-family="Inter, sans-serif">👁️</text>
      <text x="300" y="87" text-anchor="middle" fill="#10b981" font-size="9" font-weight="700" font-family="Inter, sans-serif">SENSE</text>
      <text x="300" y="42" text-anchor="middle" fill="#6b6b80" font-size="7" font-family="Inter, sans-serif">Parse input, detect intent</text>
      <!-- FRAME -->
      <circle cx="443" cy="130" r="32" fill="#1a1a2e" stroke="#00d4ff" stroke-width="2"/>
      <text x="443" y="125" text-anchor="middle" fill="#00d4ff" font-size="14" font-family="Inter, sans-serif">🖼️</text>
      <text x="443" y="142" text-anchor="middle" fill="#00d4ff" font-size="9" font-weight="700" font-family="Inter, sans-serif">FRAME</text>
      <text x="500" y="108" text-anchor="start" fill="#6b6b80" font-size="7" font-family="Inter, sans-serif">Select cognitive mode</text>
      <!-- RECALL -->
      <circle cx="475" cy="280" r="32" fill="#1a1a2e" stroke="#4f7df5" stroke-width="2"/>
      <text x="475" y="275" text-anchor="middle" fill="#4f7df5" font-size="14" font-family="Inter, sans-serif">🔍</text>
      <text x="475" y="292" text-anchor="middle" fill="#4f7df5" font-size="9" font-weight="700" font-family="Inter, sans-serif">RECALL</text>
      <text x="520" y="280" text-anchor="start" fill="#6b6b80" font-size="7" font-family="Inter, sans-serif">Retrieve memories</text>
      <!-- DELIBERATE -->
      <circle cx="400" cy="395" r="32" fill="#1a1a2e" stroke="#8b5cf6" stroke-width="2"/>
      <text x="400" y="390" text-anchor="middle" fill="#8b5cf6" font-size="14" font-family="Inter, sans-serif">🤔</text>
      <text x="400" y="407" text-anchor="middle" fill="#8b5cf6" font-size="8" font-weight="700" font-family="Inter, sans-serif">DELIBERATE</text>
      <text x="445" y="420" text-anchor="start" fill="#6b6b80" font-size="7" font-family="Inter, sans-serif">Reason &amp; plan</text>
      <!-- ACT -->
      <circle cx="300" cy="420" r="32" fill="#1a1a2e" stroke="#ec4899" stroke-width="2"/>
      <text x="300" y="415" text-anchor="middle" fill="#ec4899" font-size="14" font-family="Inter, sans-serif">⚡</text>
      <text x="300" y="432" text-anchor="middle" fill="#ec4899" font-size="9" font-weight="700" font-family="Inter, sans-serif">ACT</text>
      <text x="300" y="465" text-anchor="middle" fill="#6b6b80" font-size="7" font-family="Inter, sans-serif">Execute with tools</text>
      <!-- MONITOR -->
      <circle cx="200" cy="395" r="32" fill="#1a1a2e" stroke="#f59e0b" stroke-width="2"/>
      <text x="200" y="390" text-anchor="middle" fill="#f59e0b" font-size="14" font-family="Inter, sans-serif">📡</text>
      <text x="200" y="407" text-anchor="middle" fill="#f59e0b" font-size="8" font-weight="700" font-family="Inter, sans-serif">MONITOR</text>
      <text x="130" y="420" text-anchor="end" fill="#6b6b80" font-size="7" font-family="Inter, sans-serif">Verify execution</text>
      <!-- LEARN -->
      <circle cx="125" cy="280" r="32" fill="#1a1a2e" stroke="#ef4444" stroke-width="2"/>
      <text x="125" y="275" text-anchor="middle" fill="#ef4444" font-size="14" font-family="Inter, sans-serif">📚</text>
      <text x="125" y="292" text-anchor="middle" fill="#ef4444" font-size="9" font-weight="700" font-family="Inter, sans-serif">LEARN</text>
      <text x="72" y="280" text-anchor="end" fill="#6b6b80" font-size="7" font-family="Inter, sans-serif">Extract &amp; store</text>
      <!-- Arcs -->
      <path d="M328 82 Q390 80 435 108" stroke="url(#lg1)" stroke-width="1.5" fill="none" marker-end="url(#arrowG)"/>
      <path d="M465 155 Q485 210 478 248" stroke="url(#lg2)" stroke-width="1.5" fill="none" marker-end="url(#arrowB)"/>
      <path d="M460 305 Q445 350 420 370" stroke="url(#lg3)" stroke-width="1.5" fill="none" marker-end="url(#arrowP)"/>
      <path d="M372 405 Q340 420 330 420" stroke="url(#lg4)" stroke-width="1.5" fill="none" marker-end="url(#arrowPk)"/>
      <path d="M270 420 Q240 418 228 405" stroke="url(#lg5)" stroke-width="1.5" fill="none" marker-end="url(#arrowO)"/>
      <path d="M180 372 Q155 340 135 310" stroke="url(#lg6)" stroke-width="1.5" fill="none" marker-end="url(#arrowR)"/>
      <path d="M140 250 Q155 170 270 82" stroke="url(#lg7)" stroke-width="1.5" fill="none" marker-end="url(#arrowG2)"/>
      <!-- Center -->
      <circle cx="300" cy="240" r="50" fill="#0a0a0f" stroke="#2a2a40" stroke-width="1.5"/>
      <text x="300" y="232" text-anchor="middle" fill="#f0f0f5" font-size="11" font-weight="800" font-family="Inter, sans-serif">COGNITIVE</text>
      <text x="300" y="248" text-anchor="middle" fill="#f0f0f5" font-size="11" font-weight="800" font-family="Inter, sans-serif">LOOP</text>
      <text x="300" y="262" text-anchor="middle" fill="#6b6b80" font-size="7" font-family="Inter, sans-serif">7 phases per turn</text>
    </svg>
  </div>
</div>

<!-- ===== MEMORY TYPES ===== -->
<div class="nous-section" id="memory">
  <div class="nous-section-header nous-fade-up">
    <div class="nous-section-tag">Memory Architecture</div>
    <h2>Five Memory Types</h2>
    <p>Modeled after human cognitive memory systems — each type serves a distinct purpose</p>
  </div>
  <div class="nous-memory-grid nous-fade-up">
    <div class="nous-memory-card">
      <div class="nous-mt-accent" style="background: linear-gradient(90deg, #4f7df5, #00d4ff);"></div>
      <div class="nous-mt-icon">📖</div>
      <h4>Episodic</h4>
      <p>Conversation summaries with emotional valence, temporal ordering, and importance scoring. What happened and when.</p>
    </div>
    <div class="nous-memory-card">
      <div class="nous-mt-accent" style="background: linear-gradient(90deg, #10b981, #00d4ff);"></div>
      <div class="nous-mt-icon">💡</div>
      <h4>Semantic</h4>
      <p>Extracted facts with confidence scores, categories, tags, and staleness decay. What the agent knows.</p>
    </div>
    <div class="nous-memory-card">
      <div class="nous-mt-accent" style="background: linear-gradient(90deg, #8b5cf6, #ec4899);"></div>
      <div class="nous-mt-icon">⚙️</div>
      <h4>Procedural</h4>
      <p>Learned skills with triggers, tool lists, instructions, and effectiveness ratings. Self-evolving via EvoSkill.</p>
    </div>
    <div class="nous-memory-card">
      <div class="nous-mt-accent" style="background: linear-gradient(90deg, #f59e0b, #ef4444);"></div>
      <div class="nous-mt-icon">🔄</div>
      <h4>Working</h4>
      <p>Per-session dynamic context — current frame, loaded facts, recent episodes, active task, execution ledger.</p>
    </div>
    <div class="nous-memory-card">
      <div class="nous-mt-accent" style="background: linear-gradient(90deg, #ef4444, #8b5cf6);"></div>
      <div class="nous-mt-icon">🛡️</div>
      <h4>Censors</h4>
      <p>Behavioral guardrails that block harmful patterns before execution. Regex + semantic matching with severity levels.</p>
    </div>
  </div>
</div>

<!-- ===== KEY FEATURES ===== -->
<div class="nous-section" id="features">
  <div class="nous-section-header nous-fade-up">
    <div class="nous-section-tag">Capabilities</div>
    <h2>39 Shipped Features</h2>
    <p>Production-hardened capabilities that no other memory platform offers</p>
  </div>
  <div class="nous-features-grid nous-fade-up">
    <div class="nous-feature-card">
      <div class="nous-f-icon">🌙</div>
      <h4>Sleep Consolidation</h4>
      <p>5-phase autonomous cycle: compaction, fact extraction, knowledge graph enrichment, decision calibration, amnesia prevention. Runs between sessions.</p>
      <span class="nous-f-tag unique">Unique</span>
    </div>
    <div class="nous-feature-card">
      <div class="nous-f-icon">🔧</div>
      <h4>Correction Learning (F039)</h4>
      <p>Dual-path detection of user corrections → dual-write to facts + censors. Mistakes become permanent guardrails. MemAlign-inspired.</p>
      <span class="nous-f-tag live">Live</span>
    </div>
    <div class="nous-feature-card">
      <div class="nous-f-icon">🧬</div>
      <h4>EvoSkill</h4>
      <p>Self-evolving procedural memory. Skills are proposed, tested, merged, and improved autonomously. Transferable and composable.</p>
      <span class="nous-f-tag unique">Unique</span>
    </div>
    <div class="nous-feature-card">
      <div class="nous-f-icon">🎯</div>
      <h4>Decision Intelligence</h4>
      <p>Every decision tracked with confidence, outcome, Brier scoring. The agent literally calibrates its own judgment over time.</p>
      <span class="nous-f-tag unique">Unique</span>
    </div>
    <div class="nous-feature-card">
      <div class="nous-f-icon">🕸️</div>
      <h4>Knowledge Graph</h4>
      <p>Spreading activation across entities and relationships. Graph-expanded retrieval surfaces connections vector search alone would miss.</p>
      <span class="nous-f-tag shipped">Shipped</span>
    </div>
    <div class="nous-feature-card">
      <div class="nous-f-icon">🔍</div>
      <h4>Hybrid Retrieval</h4>
      <p>Vector + keyword + graph expansion, fused via Reciprocal Rank Fusion (RRF), then MMR diversity re-ranking. Research-grade retrieval.</p>
      <span class="nous-f-tag shipped">Shipped</span>
    </div>
    <div class="nous-feature-card">
      <div class="nous-f-icon">🖼️</div>
      <h4>Cognitive Frames</h4>
      <p>Dynamic context modes (task, research, creative, etc.) that reshape working memory, tool access, and retrieval strategy per situation.</p>
      <span class="nous-f-tag shipped">Shipped</span>
    </div>
    <div class="nous-feature-card">
      <div class="nous-f-icon">⚡</div>
      <h4>DAG Orchestration</h4>
      <p>Multi-step workflow pipelines with dependency tracking, 3-state exit codes, wave-based execution, and dashboard monitoring.</p>
      <span class="nous-f-tag live">Live</span>
    </div>
    <div class="nous-feature-card">
      <div class="nous-f-icon">🛡️</div>
      <h4>Execution Integrity</h4>
      <p>Action gating, claim verification, execution ledger, intent tracking. Prevents hallucinated actions and duplicate operations.</p>
      <span class="nous-f-tag shipped">Shipped</span>
    </div>
  </div>
</div>

<!-- ===== COMPETITIVE MOAT ===== -->
<div class="nous-section" id="moat">
  <div class="nous-section-header nous-fade-up">
    <div class="nous-section-tag">Competitive Advantage</div>
    <h2>What Makes Nous Different</h2>
    <p>Head-to-head advantages vs. Mem0, Letta, MemOS, and stateless agents</p>
  </div>
  <div class="nous-moat-grid nous-fade-up">
    <div class="nous-moat-card">
      <div class="nous-moat-number">01</div>
      <div>
        <h4>Cognitive Architecture, Not Just Storage</h4>
        <p>Competitors store memories. Nous <em>thinks</em> with them — cognitive loop, frames, deliberation, monitoring. Memory is part of cognition, not bolted on.</p>
      </div>
    </div>
    <div class="nous-moat-card">
      <div class="nous-moat-number">02</div>
      <div>
        <h4>Self-Improving Intelligence</h4>
        <p>Brier scoring, correction learning, EvoSkill, sleep consolidation. Nous gets measurably smarter with every interaction — competitors don't.</p>
      </div>
    </div>
    <div class="nous-moat-card">
      <div class="nous-moat-number">03</div>
      <div>
        <h4>Research-Grounded Design</h4>
        <p>Built on 12+ cognitive science and AI research papers (Minsky, MemAlign, A-MEM, TIM, ACC). Every feature traces to published research.</p>
      </div>
    </div>
    <div class="nous-moat-card">
      <div class="nous-moat-number">04</div>
      <div>
        <h4>Production-Grade Safety</h4>
        <p>Censors, action gating, claim verification, CEL guardrails, execution ledger. Enterprise-ready safety that memory-only platforms lack entirely.</p>
      </div>
    </div>
    <div class="nous-moat-card">
      <div class="nous-moat-number">05</div>
      <div>
        <h4>Brain/Heart Duality</h4>
        <p>Unique organ architecture separating evaluation from memory. No other agent platform has this — it enables independent scaling and specialization.</p>
      </div>
    </div>
    <div class="nous-moat-card">
      <div class="nous-moat-number">06</div>
      <div>
        <h4>4 Unique Capabilities</h4>
        <p>Pre-prune fact extraction, usage tracking feedback, anti-hallucination safety, and SmartCompress type-aware compression. Verified unique in competitive analysis.</p>
      </div>
    </div>
  </div>
</div>

<!-- ===== METRICS ===== -->
<div class="nous-section" id="metrics">
  <div class="nous-section-header nous-fade-up">
    <div class="nous-section-tag">By the Numbers</div>
    <h2>Built to Scale</h2>
  </div>
  <div class="nous-metrics-bar nous-fade-up">
    <div class="nous-metric-item">
      <div class="nous-metric-value">86.6K</div>
      <div class="nous-metric-label">Lines of Code</div>
    </div>
    <div class="nous-metric-item">
      <div class="nous-metric-value">2,625</div>
      <div class="nous-metric-label">Tests</div>
    </div>
    <div class="nous-metric-item">
      <div class="nous-metric-value">104</div>
      <div class="nous-metric-label">Modules</div>
    </div>
    <div class="nous-metric-item">
      <div class="nous-metric-value">860+</div>
      <div class="nous-metric-label">Commits</div>
    </div>
    <div class="nous-metric-item">
      <div class="nous-metric-value">28</div>
      <div class="nous-metric-label">DB Migrations</div>
    </div>
    <div class="nous-metric-item">
      <div class="nous-metric-value">39</div>
      <div class="nous-metric-label">Features Shipped</div>
    </div>
  </div>

  <!-- Research Foundation -->
  <div style="margin-top: 4rem;">
    <div class="nous-section-header nous-fade-up">
      <div class="nous-section-tag">Research Foundation</div>
      <h2>Standing on Giants</h2>
      <p>Every architectural decision traces to published cognitive science and AI research</p>
    </div>
    <div class="nous-research-grid nous-fade-up">
      <div class="nous-research-card">
        <div class="emoji">📚</div>
        <h5>Minsky (1986)</h5>
        <p>Society of Mind — organ duality, frames, censors, K-lines</p>
      </div>
      <div class="nous-research-card">
        <div class="emoji">🧬</div>
        <h5>MemAlign (2025)</h5>
        <p>Correction learning — dual-memory mistake capture</p>
      </div>
      <div class="nous-research-card">
        <div class="emoji">🔮</div>
        <h5>A-MEM (2025)</h5>
        <p>Agentic memory — self-organizing knowledge evolution</p>
      </div>
      <div class="nous-research-card">
        <div class="emoji">⏰</div>
        <h5>TIM (2025)</h5>
        <p>Trajectory learning — improving from execution paths</p>
      </div>
      <div class="nous-research-card">
        <div class="emoji">🌊</div>
        <h5>ACC (2025)</h5>
        <p>Adaptive context control — dynamic memory management</p>
      </div>
      <div class="nous-research-card">
        <div class="emoji">🧠</div>
        <h5>tinyHippo</h5>
        <p>Biological memory model — hippocampal consolidation</p>
      </div>
      <div class="nous-research-card">
        <div class="emoji">🏗️</div>
        <h5>Membrain</h5>
        <p>Engineering memory taxonomy — type classification</p>
      </div>
      <div class="nous-research-card">
        <div class="emoji">📐</div>
        <h5>xMemory (2025)</h5>
        <p>Diversity-aware retrieval — MMR re-ranking</p>
      </div>
    </div>
  </div>

  <!-- Brand Hierarchy -->
  <div class="nous-brand-bar nous-fade-up">
    <div class="nous-brand-item">
      <div class="label">Company</div>
      <div class="name" style="color: #00d4ff;">Cognition Engines</div>
    </div>
    <div class="nous-brand-arrow">→</div>
    <div class="nous-brand-item">
      <div class="label">Architecture</div>
      <div class="name" style="color: #8b5cf6;">FORGE</div>
    </div>
    <div class="nous-brand-arrow">→</div>
    <div class="nous-brand-item">
      <div class="label">Agent</div>
      <div class="name" style="color: #10b981;">Nous</div>
    </div>
  </div>
</div>

<!-- ===== FOOTER ===== -->
<div class="nous-footer">
  <p style="margin-bottom: 0.5rem;">
    <strong style="font-size: 1.1rem;">Nous</strong> — A Continuous Memory Platform by
    <a href="https://cognition-engines.ai">Cognition Engines</a>
  </p>
  <p>Built by a single engineer. Powered by cognitive science. Ready to scale.</p>
  <p style="margin-top: 1rem; font-size: 0.75rem; color: #4a4a60;">© 2026 Cognition Engines. All rights reserved.</p>
</div>

</div>

<script setup>
import { onMounted } from 'vue'

onMounted(() => {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible')
      }
    })
  }, { threshold: 0.1 })

  document.querySelectorAll('.nous-fade-up').forEach(el => observer.observe(el))
})
</script>
