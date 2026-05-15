from rest_framework import serializers

from research.models import Finding, ResearchSession, ToolCall


class FindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Finding
        fields = [
            "id",
            "file_path",
            "line_start",
            "line_end",
            "note",
            "created_at",
        ]


class ToolCallSerializer(serializers.ModelSerializer):
    class Meta:
        model = ToolCall
        fields = [
            "id",
            "step_number",
            "tool_name",
            "tool_input",
            "tool_output",
            "duration_ms",
            "created_at",
        ]


class ResearchSessionSerializer(serializers.ModelSerializer):
    findings = FindingSerializer(many=True, read_only=True)
    tool_calls = ToolCallSerializer(many=True, read_only=True)
    repository_id = serializers.IntegerField(source="repository.id", read_only=True)
    repository_url = serializers.URLField(source="repository.url", read_only=True)
    repository_name = serializers.CharField(source="repository.name", read_only=True)

    class Meta:
        model = ResearchSession
        fields = [
            "id",
            "repository_id",
            "repository_url",
            "repository_name",
            "question",
            "final_answer",
            "status",
            "input_tokens",
            "output_tokens",
            "started_at",
            "completed_at",
            "created_at",
            "findings",
            "tool_calls",
        ]


class ResearchSessionCreateSerializer(serializers.Serializer):
    repo_url = serializers.URLField()
    question = serializers.CharField()
