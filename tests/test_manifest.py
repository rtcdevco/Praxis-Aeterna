import json

from core.manifest import MANIFEST_VERSION, discover_skills, generate_manifest


def _make_skill(skills_dir, name, extra_files=()):
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nkeywords: []\n---\n# Skill\n", encoding="utf-8")
    for filename in extra_files:
        (skill_dir / filename).write_text("content", encoding="utf-8")
    return skill_dir


def test_discover_skills_requires_skill_md(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _make_skill(skills_dir, "productivity")
    (skills_dir / "not_a_skill").mkdir()  # no SKILL.md — should be ignored

    skills = discover_skills(skills_dir)

    assert list(skills.keys()) == ["productivity"]
    assert skills["productivity"]["path"] == "skills/productivity"
    assert skills["productivity"]["skill_md"] == "skills/productivity/SKILL.md"


def test_discover_skills_detects_scripts_and_lists_files(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _make_skill(skills_dir, "research", extra_files=["sources.md", "helper.py"])

    skills = discover_skills(skills_dir)

    assert skills["research"]["has_scripts"] is True
    assert set(skills["research"]["files"]) == {"SKILL.md", "sources.md", "helper.py"}


def test_discover_skills_sorted_order(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _make_skill(skills_dir, "zeta")
    _make_skill(skills_dir, "alpha")

    skills = discover_skills(skills_dir)

    assert list(skills.keys()) == ["alpha", "zeta"]


def test_generate_manifest_shape_matches_spec(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _make_skill(skills_dir, "productivity", extra_files=["tasks.md"])

    out_path = tmp_path / "skills_manifest.json"
    manifest = generate_manifest(skills_dir, out_path)

    assert manifest["version"] == MANIFEST_VERSION
    assert "skills" in manifest
    assert out_path.is_file()

    on_disk = json.loads(out_path.read_text(encoding="utf-8"))
    assert on_disk == manifest
