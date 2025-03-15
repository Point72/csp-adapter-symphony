__all__ = ("mention_user",)


def mention_user(email_or_userid: str = ""):
    if email_or_userid:
        if "@" in str(email_or_userid):
            return f'<mention email="{email_or_userid}" />'
        else:
            return f'<mention uid="{email_or_userid}" />'
    return ""
