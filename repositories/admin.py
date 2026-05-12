from django.contrib import admin

from .models import Repository


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "url",
        "default_branch",
        "last_indexed_at",
        "created_at",
    )
    search_fields = ("name", "url", "local_clone_path")
