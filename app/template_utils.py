import re


def render_template_string(template: str, data: dict) -> str:
    """Replace {var} placeholders in *template* using values from *data*."""

    def repl(match: re.Match) -> str:
        key = match.group(1)
        return str(data.get(key, match.group(0)))

    return re.sub(r"{([^{}]+)}", repl, template or "")
