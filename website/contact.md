# Contact

<style>
.contact-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1.5rem;
  margin: 2rem 0;
}
.contact-card {
  padding: 2rem;
  border-radius: 16px;
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-divider);
  transition: border-color 0.3s, box-shadow 0.3s;
}
.contact-card:hover {
  border-color: var(--vp-c-brand-1);
  box-shadow: 0 4px 24px rgba(99, 102, 241, 0.12);
}
.contact-card .card-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.2rem;
}
.contact-card .card-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  object-fit: cover;
}
.contact-card .card-title {
  font-size: 1.3rem;
  font-weight: 600;
  margin: 0;
}
.contact-card .card-subtitle {
  font-size: 0.9rem;
  color: var(--vp-c-text-3);
  margin: 0;
}
.contact-card .card-body {
  color: var(--vp-c-text-2);
  line-height: 1.7;
}
.contact-card .card-body a {
  color: var(--vp-c-brand-1);
  text-decoration: none;
  font-weight: 500;
}
.contact-card .card-body a:hover {
  text-decoration: underline;
}
.contact-card .card-links {
  display: flex;
  gap: 1rem;
  margin-top: 1rem;
  flex-wrap: wrap;
}
.contact-card .card-link {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 1rem;
  border-radius: 8px;
  background: var(--vp-c-bg-alt);
  border: 1px solid var(--vp-c-divider);
  color: var(--vp-c-text-1);
  text-decoration: none;
  font-size: 0.9rem;
  font-weight: 500;
  transition: border-color 0.2s, background 0.2s;
}
.contact-card .card-link:hover {
  border-color: var(--vp-c-brand-1);
  background: var(--vp-c-bg-soft);
}
</style>

<div class="contact-cards">

<div class="contact-card">
  <div class="card-header">
    <img src="/icon-team.png" alt="Team" class="card-icon" />
    <div>
      <p class="card-title">Team</p>
      <p class="card-subtitle">People behind Cognition Engines</p>
    </div>
  </div>
  <div class="card-body">
    <p><strong>Timur Fatykhov</strong> — Creator & Lead Developer</p>
    <p>📧 <a href="mailto:timur.fatykhov@cognition-engines.ai">timur.fatykhov@cognition-engines.ai</a></p>
  </div>
</div>

<div class="contact-card">
  <div class="card-header">
    <img src="/icon-project.png" alt="Project" class="card-icon" />
    <div>
      <p class="card-title">Project</p>
      <p class="card-subtitle">Links & resources</p>
    </div>
  </div>
  <div class="card-body">
    <p>Open source decision intelligence for AI agents. Built with Python, FastAPI, and ChromaDB.</p>
    <div class="card-links">
      <a href="https://github.com/tfatykhov/cognition-agent-decisions" class="card-link">GitHub</a>
      <a href="https://github.com/tfatykhov/cognition-agent-decisions/issues" class="card-link">Issues</a>
      <a href="/changelog" class="card-link">Changelog</a>
    </div>
  </div>
</div>

</div>

## Contributing

We welcome contributions! Open an [issue](https://github.com/tfatykhov/cognition-agent-decisions/issues) or submit a pull request on GitHub.
