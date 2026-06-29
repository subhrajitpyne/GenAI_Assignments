import os
from langchain_core.tools import tool


# ── Language to file extension mapping ────────────────────────────────────────
_LANGUAGE_EXTENSIONS: dict[str, str] = {
    "python":     ".py",
    "javascript": ".js",
    "typescript": ".ts",
    "java":       ".java",
    "go":         ".go",
    "ruby":       ".rb",
    "rust":       ".rs",
    "cpp":        ".cpp",
    "c":          ".c",
}


def get_file_extension(language: str) -> str:
    """Returns the file extension for a given programming language."""
    return _LANGUAGE_EXTENSIONS.get(language.lower().strip(), ".py")


@tool
def write_file(file_path: str, content: str) -> str:
    """
    Write content to a file at the given path.
    Creates parent directories automatically if they do not exist.
    Returns a success message or an error string.
    """
    try:
        parent = os.path.dirname(file_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully written to {file_path}"
    except Exception as e:
        return f"Error writing file {file_path}: {str(e)}"


@tool
def read_file(file_path: str) -> str:
    """
    Read and return the full content of a file.
    Returns the file content as a string, or an error message if not found.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File not found at {file_path}"
    except Exception as e:
        return f"Error reading file {file_path}: {str(e)}"


# export
file_tools: list = [write_file, read_file]
