"""CrewAI deep-dive pipeline (P6): Company Scout → Networker → Fact-Checker.

Runs entirely on local Ollama (PRD §2: privacy-first, zero API cost).
Web context is prefetched with DuckDuckGo (free, keyless) and injected into
the task prompt, keeping the agent loop simple and offline-tolerant.
"""

import logging

from app.config import settings

logger = logging.getLogger("synapse.agents")


def _web_context(company: str) -> str:
    """Best-effort free web search; the pipeline works without it."""
    try:
        try:
            from ddgs import DDGS  # current package name
        except ImportError:
            from duckduckgo_search import DDGS  # legacy name

        results = list(DDGS().text(f'"{company}" company', max_results=5))
        if not results:
            return "(no web results found)"
        return "\n".join(
            f"- {r.get('title', '')}: {r.get('body', '')[:300]} [{r.get('href', '')}]"
            for r in results
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("web search unavailable: %s", str(exc)[:200])
        return "(web search unavailable — rely on the job description only)"


def run_deep_dive(title: str, company: str, description: str) -> str:
    """Blocking CrewAI run; call via asyncio.to_thread. Returns markdown."""
    from crewai import LLM, Agent, Crew, Process, Task

    llm = LLM(
        model=f"ollama/{settings.ollama_model}",
        base_url=settings.ollama_base_url,
        temperature=0.4,
    )

    web_context = _web_context(company)
    description = description[:6000]  # keep local context window comfortable

    scout = Agent(
        role="Company Scout",
        goal=f"Build an accurate intelligence profile of {company} as an employer",
        backstory=(
            "A meticulous research analyst who profiles companies for senior "
            "job candidates: business model, size, funding, AI maturity, "
            "remote-work culture, and red flags."
        ),
        llm=llm,
        verbose=False,
    )
    networker = Agent(
        role="Networker",
        goal="Identify who likely owns this hire and craft outreach angles",
        backstory=(
            "A career strategist who reads job descriptions for organizational "
            "signals: which team is hiring, what pain drove the opening, and "
            "what a compelling first message to the hiring manager looks like."
        ),
        llm=llm,
        verbose=False,
    )
    fact_checker = Agent(
        role="Fact-Checker",
        goal="Strip or flag every claim not supported by the provided sources",
        backstory=(
            "A skeptical editor. Anything not grounded in the job description "
            "or the web context gets marked '[unverified]' or removed."
        ),
        llm=llm,
        verbose=False,
    )

    scout_task = Task(
        description=(
            f"Research {company} for a candidate considering this role.\n\n"
            f"# Job Posting: {title}\n{description}\n\n"
            f"# Web Context\n{web_context}\n\n"
            "Produce markdown sections: ## Company Overview, ## AI Maturity "
            "Signals, ## Remote Culture & Benefits Signals, ## Red Flags."
        ),
        expected_output="Markdown company intelligence report with the four sections.",
        agent=scout,
    )
    networker_task = Task(
        description=(
            f"Using the job posting below and the scout's report, produce: "
            "## Likely Hiring Owner (role/title, not invented names), "
            "## Why This Role Is Open (inference, labeled as such), "
            "## Outreach Angles (3 specific talking points connecting a "
            "senior AI architect's background to this company's needs).\n\n"
            f"# Job Posting: {title} at {company}\n{description}"
        ),
        expected_output="Markdown networking strategy with the three sections.",
        agent=networker,
        context=[scout_task],
    )
    factcheck_task = Task(
        description=(
            "Combine the scout report and networking strategy into ONE final "
            "markdown dossier. Verify every factual claim against the job "
            "posting and web context provided earlier. Mark anything "
            "unsupported as *[unverified]*. Keep all section headers. "
            "Start with '# Deep-Dive Dossier: {title} @ {company}' and a "
            "3-bullet executive summary."
        ),
        expected_output="The final verified markdown dossier.",
        agent=fact_checker,
        context=[scout_task, networker_task],
    )

    crew = Crew(
        agents=[scout, networker, fact_checker],
        tasks=[scout_task, networker_task, factcheck_task],
        process=Process.sequential,
        verbose=False,
    )
    result = crew.kickoff()
    return str(result)
