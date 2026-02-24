import os
import uuid
from fastapi import UploadFile, HTTPException

UPLOAD_DIR = "static/uploads/posts"
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/avif", "image/gif"}
MAX_SIZE = 5 * 1024 * 1024  # 5MB


async def save_post_media(files: list[UploadFile] | None):
    if not files:
        return []

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    saved_urls = []

    for file in files:

        # MIME validation
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(400, "File type not allowed")

        contents = await file.read()

        # Size validation
        if len(contents) > MAX_SIZE:
            raise HTTPException(400, "File too large")

        ext = file.filename.split(".")[-1]
        filename = f"{uuid.uuid4()}.{ext}"

        path = os.path.join(UPLOAD_DIR, filename)

        with open(path, "wb") as f:
            f.write(contents)

        saved_urls.append(f"/static/uploads/posts/{filename}")

    return saved_urls
