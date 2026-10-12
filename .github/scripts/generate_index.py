import json
from pathlib import Path
from datetime import datetime, timezone


def get_cover_image(data, base_path, default_filename="cover.png"):
    """
    Determine cover image path with priority:
    1. data['cover_image'] if exists (full path provided)
    2. data['images'] array — find role='hero' and build path
    3. fallback to base_path/images/{default_filename}
    """
    # Priority 1: explicit cover_image in JSON
    if data.get("cover_image"):
        return data["cover_image"]
    
    # Priority 2: derive from images array (new format v1.2)
    images = data.get("images", [])
    if isinstance(images, list):
        for img in images:
            if img.get("role") == "hero" and img.get("image_path"):
                return f"{base_path}/{img['image_path']}"
    
    # Priority 3: fallback to legacy default
    return f"{base_path}/images/{default_filename}"


def get_images_array(data, base_path):
    """
    Return normalized images array if exists (v1.2 schema).
    Each image with full path.
    Returns None if no images array found.
    """
    images = data.get("images", [])
    if not isinstance(images, list) or len(images) == 0:
        return None
    
    normalized = []
    for img in images:
        if not img.get("image_path"):
            continue
        normalized_img = {
            "role": img.get("role"),
            "aspect_ratio": img.get("aspect_ratio"),
            "narrative_caption": img.get("narrative_caption", ""),
            "image_path": f"{base_path}/{img['image_path']}"
        }
        if img.get("scene_text"):
            normalized_img["scene_text"] = img["scene_text"]
        # v3 (storyboard por planos): metadatos del plano para el visor
        if img.get("beat"):
            normalized_img["beat"] = img["beat"]
        if isinstance(img.get("shot"), dict):
            normalized_img["shot"] = img["shot"]
        normalized.append(normalized_img)
    
    return normalized if normalized else None


def get_chapter_meta(data):
    """v3: resumen del capítulo (sin los planos, que ya van en images[].shot)."""
    ch = data.get("chapter")
    if not isinstance(ch, dict):
        return None
    return {
        "schema_version": ch.get("schema_version"),
        "structure": ch.get("structure"),
        "duration_s": ch.get("duration_s"),
        "logline": ch.get("logline", ""),
        "entry_question": ch.get("entry_question", ""),
        "exit_question": ch.get("exit_question", ""),
        "acts": [
            {"key": a.get("key"), "label": a.get("label"), "start_s": a.get("start_s"), "end_s": a.get("end_s")}
            for a in ch.get("acts", []) if isinstance(a, dict)
        ],
    }


worlds = []
worlds_dir = Path("worlds")

for world_path in sorted(worlds_dir.iterdir()):
    if not world_path.is_dir():
        continue
    world_json = world_path / "world.json"
    if not world_json.exists():
        continue
    
    with open(world_json) as f:
        w = json.load(f)
    
    world_base_path = f"worlds/{world_path.name}"
    cover_rel = get_cover_image(w, world_base_path)
    world_images = get_images_array(w, world_base_path)
    
    branches = []
    branches_dir = world_path / "branches"
    if branches_dir.exists():
        for branch_path in sorted(branches_dir.rglob("branch.json")):
            with open(branch_path) as bf:
                b = json.load(bf)
            
            branch_dir = branch_path.parent
            branch_slug = branch_dir.name
            branch_base_path = str(branch_dir).replace("\\", "/")
            
            cover_branch = get_cover_image(b, branch_base_path)
            branch_images = get_images_array(b, branch_base_path)
            
            branch_entry = {
                "branch_id": b["branch_id"],
                "branch_slug": branch_slug,
                "name": b["name"],
                "description": b.get("description", ""),
                "parent_branch": b["parent_branch"],
                "created_by": b["created_by"],
                "created_at": b.get("created_at", ""),
                "divergence_event": b.get("divergence_event", None),
                "cover_image": cover_branch
            }
            
            if branch_images:
                branch_entry["images"] = branch_images

            chapter_meta = get_chapter_meta(b)
            if chapter_meta:
                branch_entry["chapter_meta"] = chapter_meta
            
            branches.append(branch_entry)
    
    world_entry = {
        "world_id": w["world_id"],
        "slug": w["slug"],
        "name": w["name"],
        "description": w["description"],
        "tags": w.get("tags", []),
        "cover_image": cover_rel,
        "created_by": w["created_by"],
        "created_at": w["created_at"],
        "status": w.get("status", "developing"),
        "branches": branches,
        "characters": w.get("characters", []),
        "places": w.get("places", []),
        "story_bible": w.get("story_bible", {}),
    }
    
    if world_images:
        world_entry["images"] = world_images

    # v3: carátula (logline, pregunta central, semillas de rama)
    if isinstance(w.get("cover"), dict):
        world_entry["cover"] = w["cover"]
    world_chapter = get_chapter_meta(w)
    if world_chapter:
        world_entry["chapter_meta"] = world_chapter

    worlds.append(world_entry)


index = {
    "schema_version": "1.2",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "total_worlds": len(worlds),
    "total_branches": sum(len(w["branches"]) for w in worlds),
    "worlds": worlds
}

with open("worlds-index.json", "w", encoding="utf-8") as f:
    json.dump(index, f, indent=2, ensure_ascii=False)

print(f"Generated index with {len(worlds)} worlds")
