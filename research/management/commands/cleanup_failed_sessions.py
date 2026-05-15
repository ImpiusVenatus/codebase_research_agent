from django.core.management.base import BaseCommand

from research.models import ResearchSession


class Command(BaseCommand):
    help = "Delete research sessions that failed (e.g. from earlier broken runs)."

    def handle(self, *args, **options) -> None:
        deleted, _ = ResearchSession.objects.filter(
            status=ResearchSession.Status.FAILED,
        ).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} failed session(s)."))
