from django.contrib import admin

from .models import Finding, ResearchSession, ToolCall


class ToolCallInline(admin.TabularInline):
    model = ToolCall
    extra = 0
    readonly_fields = (
        "step_number",
        "tool_name",
        "tool_input",
        "tool_output",
        "duration_ms",
        "created_at",
    )
    can_delete = False
    ordering = ("step_number",)
    show_change_link = True


class FindingInline(admin.TabularInline):
    model = Finding
    extra = 0
    readonly_fields = ("file_path", "line_start", "line_end", "note", "created_at")
    can_delete = False


@admin.register(ResearchSession)
class ResearchSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "repository",
        "question_preview",
        "status",
        "tool_call_count",
        "finding_count",
        "input_tokens",
        "output_tokens",
        "created_at",
    )
    list_filter = ("status", "repository")
    search_fields = ("question", "final_answer", "repository__name", "repository__url")
    readonly_fields = (
        "repository",
        "question",
        "final_answer",
        "status",
        "input_tokens",
        "output_tokens",
        "started_at",
        "completed_at",
        "created_at",
    )
    inlines = (ToolCallInline, FindingInline)

    @admin.display(description="Question")
    def question_preview(self, obj: ResearchSession) -> str:
        return obj.question[:60] + ("…" if len(obj.question) > 60 else "")

    @admin.display(description="Tools")
    def tool_call_count(self, obj: ResearchSession) -> int:
        return obj.tool_calls.count()

    @admin.display(description="Findings")
    def finding_count(self, obj: ResearchSession) -> int:
        return obj.findings.count()


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
    list_filter = ("tool_name",)
    search_fields = ("tool_name", "tool_output", "session__question")
    readonly_fields = (
        "session",
        "step_number",
        "tool_name",
        "tool_input",
        "tool_output",
        "duration_ms",
        "created_at",
    )


@admin.register(Finding)
class FindingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "file_path",
        "line_start",
        "line_end",
        "note_preview",
        "created_at",
    )
    search_fields = ("file_path", "note", "session__question")
    readonly_fields = ("session", "file_path", "line_start", "line_end", "note", "created_at")

    @admin.display(description="Note")
    def note_preview(self, obj: Finding) -> str:
        return obj.note[:80] + ("…" if len(obj.note) > 80 else "")
