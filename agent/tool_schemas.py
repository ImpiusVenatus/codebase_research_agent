TOOLS = [
    {
        "name": "list_files",
        "description": (
            "List repository files under a directory. Use this first at the repo root "
            "to understand project structure, then call it on likely source directories. "
            "Do not use it to recursively dump the entire repository."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Repository-relative directory or file path.",
                    "default": ".",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum directory depth to traverse from path.",
                    "default": 1,
                    "minimum": 1,
                    "maximum": 3,
                },
            },
            "required": [],
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read a repository-relative text file with optional line bounds. Prefer "
            "specific line ranges after using search_code or get_file_outline. The "
            "tool caps output at 500 lines or 20KB."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Repository-relative file path to read.",
                },
                "start_line": {
                    "type": "integer",
                    "description": "Optional 1-based starting line.",
                    "minimum": 1,
                },
                "end_line": {
                    "type": "integer",
                    "description": "Optional 1-based ending line.",
                    "minimum": 1,
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_code",
        "description": (
            "Search code for exact terms, symbols, error messages, route names, or "
            "other concrete clues. Use targeted queries and optional file globs. "
            "Results are capped at 50 matches."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Regular expression or literal term to search for.",
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Optional glob such as '*.py' or 'src/**/*.ts'.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_file_outline",
        "description": (
            "Get a compact outline of likely declarations in a file. Use this before "
            "reading large files so you can request only relevant line ranges."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Repository-relative file path to outline.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "save_finding",
        "description": (
            "Persist a finding that supports the final answer. Call this for each "
            "file citation you plan to include, with a concise note explaining why "
            "the referenced code matters."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Repository-relative path supporting the finding.",
                },
                "note": {
                    "type": "string",
                    "description": "Concise explanation of the finding.",
                },
                "line_start": {
                    "type": "integer",
                    "description": "Optional starting line for the cited code.",
                    "minimum": 1,
                },
                "line_end": {
                    "type": "integer",
                    "description": "Optional ending line for the cited code.",
                    "minimum": 1,
                },
            },
            "required": ["file_path", "note"],
        },
    },
    {
        "name": "get_previous_findings",
        "description": (
            "Retrieve up to 20 prior findings for this repository URL. Call this once "
            "at the start of a research session to avoid repeating already-known work."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "repo_url": {
                    "type": "string",
                    "description": "The repository URL for the active session.",
                },
            },
            "required": ["repo_url"],
        },
    },
]
