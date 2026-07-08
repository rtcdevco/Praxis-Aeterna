from core.manifest import discover_skills, MANIFEST_VERSION
from core.router import SkillRouter, parse_context_files


def _write_skill(skills_dir, name, patterns=(), keywords=(), priority=0, body="# Skill\n"):
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True)
    frontmatter_lines = ["---"]
    if patterns:
        frontmatter_lines.append("intent_patterns:")
        frontmatter_lines += [f'  - "{p}"' for p in patterns]
    if keywords:
        frontmatter_lines.append("keywords: [" + ", ".join(keywords) + "]")
    frontmatter_lines.append(f"priority: {priority}")
    frontmatter_lines.append("---")
    (skill_dir / "SKILL.md").write_text("\n".join(frontmatter_lines) + "\n" + body, encoding="utf-8")


def _build_router(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    return skills_dir


def test_regex_phase_matches_directly(tmp_path):
    skills_dir = _build_router(tmp_path)
    _write_skill(skills_dir, "productivity", patterns=[r"\\badd\\s+a\\s+task\\b"])
    _write_skill(skills_dir, "research", patterns=[r"\\bresearch\\b"])
    manifest = {"skills": discover_skills(skills_dir), "version": MANIFEST_VERSION}
    router = SkillRouter(manifest, repo_root=tmp_path)

    assert router.route("please add a task to buy milk") == "productivity"
    assert router.route("let's research the market") == "research"


def test_regex_phase_first_match_wins_in_manifest_order(tmp_path):
    skills_dir = _build_router(tmp_path)
    _write_skill(skills_dir, "aaa", patterns=[r"\\bhello\\b"])
    _write_skill(skills_dir, "bbb", patterns=[r"\\bhello\\b"])
    manifest = {"skills": discover_skills(skills_dir), "version": MANIFEST_VERSION}
    router = SkillRouter(manifest, repo_root=tmp_path)

    assert router.skill_names == ["aaa", "bbb"]
    assert router.route("hello there") == "aaa"


def test_keyword_fallback_when_no_regex_matches(tmp_path):
    skills_dir = _build_router(tmp_path)
    _write_skill(skills_dir, "productivity", keywords=["task", "todo", "deadline"])
    _write_skill(skills_dir, "research", keywords=["research", "sources", "citation"])
    manifest = {"skills": discover_skills(skills_dir), "version": MANIFEST_VERSION}
    router = SkillRouter(manifest, repo_root=tmp_path)

    assert router.route("what's my todo deadline for this task") == "productivity"


def test_keyword_fallback_below_floor_returns_none(tmp_path):
    skills_dir = _build_router(tmp_path)
    _write_skill(skills_dir, "productivity", keywords=["task", "todo", "deadline", "priority", "schedule"])
    manifest = {"skills": discover_skills(skills_dir), "version": MANIFEST_VERSION}
    router = SkillRouter(manifest, repo_root=tmp_path)

    # Only one of five keywords present -> 0.2 >= 0.15 floor, should still match.
    assert router.route("what's the priority here") == "productivity"
    # No keywords present at all.
    assert router.route("completely unrelated sentence") is None


def test_keyword_tiebreak_by_priority_then_alphabetical(tmp_path):
    skills_dir = _build_router(tmp_path)
    _write_skill(skills_dir, "aaa", keywords=["shared"], priority=0)
    _write_skill(skills_dir, "bbb", keywords=["shared"], priority=5)
    manifest = {"skills": discover_skills(skills_dir), "version": MANIFEST_VERSION}
    router = SkillRouter(manifest, repo_root=tmp_path)

    # Equal score (1/1), bbb has higher priority -> bbb wins.
    assert router.route("shared") == "bbb"


def test_keyword_tiebreak_alphabetical_when_priority_equal(tmp_path):
    skills_dir = _build_router(tmp_path)
    _write_skill(skills_dir, "zzz", keywords=["shared"], priority=0)
    _write_skill(skills_dir, "aaa", keywords=["shared"], priority=0)
    manifest = {"skills": discover_skills(skills_dir), "version": MANIFEST_VERSION}
    router = SkillRouter(manifest, repo_root=tmp_path)

    assert router.route("shared") == "aaa"


def test_no_match_returns_none(tmp_path):
    skills_dir = _build_router(tmp_path)
    _write_skill(skills_dir, "productivity", patterns=[r"\\btask\\b"], keywords=["task"])
    manifest = {"skills": discover_skills(skills_dir), "version": MANIFEST_VERSION}
    router = SkillRouter(manifest, repo_root=tmp_path)

    assert router.route("the weather is nice today") is None


def test_parse_context_files_extracts_bullets():
    text = (
        "# Skill\n\n"
        "## Context Files\n"
        "- tasks.md — the running task list\n"
        "- other.md — some other file\n\n"
        "## Capabilities\n"
        "- Do a thing\n"
    )

    assert parse_context_files(text) == ["tasks.md", "other.md"]


def test_parse_context_files_missing_section_returns_empty():
    assert parse_context_files("# Skill\n\n## Capabilities\n- Do a thing\n") == []
