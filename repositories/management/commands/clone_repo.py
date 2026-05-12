from django.core.management.base import BaseCommand

from repositories.services import RepositoryService


class Command(BaseCommand):
    help = "Clone a GitHub repository into the local repository cache."

    def add_arguments(self, parser) -> None:
        parser.add_argument("url", help="Public GitHub repository URL to clone.")

    def handle(self, *args, **options) -> None:
        repository = RepositoryService.get_or_clone(options["url"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Repository {repository.id} cached at {repository.local_clone_path}"
            )
        )
