"""Minimal string-replace templating — no Jinja dependency needed for one template."""

from __future__ import annotations


def render_template(template_text: str, **values: str) -> str:
    rendered = template_text
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered
