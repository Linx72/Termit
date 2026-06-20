def slugify(text: str) -> str:
    if not text:
        raise ValueError("empty")
    return text.strip().lower().replace(" ", "-")
