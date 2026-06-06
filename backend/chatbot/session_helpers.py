from rest_framework.exceptions import NotFound, PermissionDenied

from .models import ChatSession


def get_user_session(user, session_id, *, active_only=True) -> ChatSession:
    """
    Resolve a session for the authenticated user.

    - 404 when the session does not exist or is inactive (when active_only=True)
    - 403 when the session belongs to another user
    """
    try:
        session = ChatSession.objects.get(pk=session_id)
    except (ChatSession.DoesNotExist, ValueError):
        raise NotFound("Chat session not found.")

    if session.user_id != user.id:
        raise PermissionDenied("You do not have access to this chat session.")

    if active_only and not session.is_active:
        raise NotFound("Chat session not found.")

    return session
