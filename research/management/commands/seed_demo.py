from django.core.management.base import BaseCommand, CommandError

from agent.providers import AllProvidersFailed, has_configured_provider, run_research_session
from repositories.services import RepositoryService
from research.models import ResearchSession


DEMO_RUNS = [
    {
        "repo_url": "https://github.com/pallets/click",
        "question": "Where is the main CLI entry point defined?",
    },
    {
        "repo_url": "https://github.com/pallets/click",
        "question": "How does Click handle command groups?",
    },
    {
        "repo_url": "https://github.com/kennethreitz/requests",
        "question": "Where is the core HTTP request method implemented?",
    },
    {
        "repo_url": "https://github.com/kennethreitz/requests",
        "question": "How are HTTP sessions and connection pooling handled?",
    },
]


class Command(BaseCommand):
    help = "Run the research agent on demo repositories to populate sample data."

    def handle(self, *args, **options) -> None:
        if not has_configured_provider():
            raise CommandError(
                "No LLM provider configured. Set GROQ_API_KEY, OPENAI_API_KEY, "
                "or ANTHROPIC_API_KEY in .env"
            )

        deleted, _ = ResearchSession.objects.filter(
            status=ResearchSession.Status.FAILED,
        ).delete()
        if deleted:
            self.stdout.write(
                self.style.WARNING(
                    f"Removed {deleted} failed session(s) from earlier runs."
                )
            )

        for index, run in enumerate(DEMO_RUNS, start=1):
            self.stdout.write(
                f"[{index}/{len(DEMO_RUNS)}] {run['repo_url']} — {run['question']}"
            )
            repository = RepositoryService.get_or_clone(run["repo_url"])
            session = ResearchSession.objects.create(
                repository=repository,
                question=run["question"],
            )
            try:
                run_research_session(session)
            except AllProvidersFailed as exc:
                session.refresh_from_db()
                self.stdout.write(self.style.ERROR(f"  All providers failed: {exc}"))
                continue
            except Exception as exc:
                session.refresh_from_db()
                self.stdout.write(
                    self.style.ERROR(f"  Session {session.id} failed: {exc}")
                )
                continue

            session.refresh_from_db()
            style = (
                self.style.SUCCESS
                if session.status == ResearchSession.Status.COMPLETED
                else self.style.WARNING
            )
            self.stdout.write(
                style(
                    f"  Session {session.id}: {session.status} "
                    f"({session.tool_calls.count()} tool calls, "
                    f"{session.findings.count()} findings)"
                )
            )

        self.stdout.write(self.style.SUCCESS("Demo seed complete."))
        session_ids = list(
            ResearchSession.objects.order_by("-id").values_list("id", flat=True)[:4]
        )
        if session_ids:
            self.stdout.write(
                f"Try: curl http://127.0.0.1:8000/api/sessions/{session_ids[0]}/"
            )
