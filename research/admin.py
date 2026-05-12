from django.contrib import admin

from .models import Finding, ResearchSession, ToolCall


@admin.register(ResearchSession)
class ResearchSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "repository",
        "status",
        "input_tokens",
        "output_tokens",
        "created_at",
    )
    search_fields = ("question", "final_answer", "repository__name", "repository__url")


@admin.register(ToolCall)
class ToolCallAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "step_number",
        "tool_name",
        "duration_ms",
        "created_at",
    )
    search_fields = ("tool_name", "tool_output", "session__question")


@admin.register(Finding)
class FindingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "file_path",
        "line_start",
        "line_end",
        "created_at",
    )
    search_fields = ("file_path", "note", "session__question")
