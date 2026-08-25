from __future__ import annotations


def should_update_event_message_after_join(was_added: bool) -> bool:
    return was_added


def join_feedback_text(was_added: bool) -> str:
    return "Вы записаны!" if was_added else "Вы уже в списке."
