import uuid
from unittest.mock import Mock

from app.models.post import Post
from scripts.evaluate_matching import resolve_manifest_post


def test_resolve_manifest_post_accepts_database_uuid():
    post = Post(title="Title", content="Content")
    post.id = uuid.uuid4()
    db = Mock()
    db.get.return_value = post

    resolved = resolve_manifest_post(db, {"post_id": str(post.id)})

    assert resolved is post
    db.scalars.assert_not_called()


def test_resolve_manifest_post_uses_manifest_metadata_for_stable_id():
    post = Post(title="Title", content="Content")
    db = Mock()
    db.get.return_value = None
    db.scalars.return_value.all.return_value = [post]

    resolved = resolve_manifest_post(
        db,
        {"post_id": "post-01", "title": "Title", "content": "Content"},
    )

    assert resolved is post
