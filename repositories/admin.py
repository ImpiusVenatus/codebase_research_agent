from django.contrib import admin

from .models import Repository


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "url",
        "session_count",
        "default_branch",
        "last_indexed_at",
        "created_at",
    )
    search_fields = ("name", "url", "local_clone_path")
    readonly_fields = ("local_clone_path", "created_at")

    @admin.display(description="Sessions")
    def session_count(self, obj) -> int:
        return obj.sessions.count()
