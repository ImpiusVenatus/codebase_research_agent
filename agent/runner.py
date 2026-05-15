from __future__ import annotations

from agent.loop import ResearchAgent
from agent.providers.chain import build_provider_chain
from research.models import ResearchSession


def run_research_session(session: ResearchSession) -> ResearchSession:
    chain = build_provider_chain()
    agent = ResearchAgent(session, chain)
    return agent.run()
