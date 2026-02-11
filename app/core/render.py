from fastapi import Request
from app.core.config import templates
from app.core.dependencies import optional_current_user_cookie


async def render(request: Request, template: str, context: dict | None = None):

    if context is None:
        context = {}

    user = await optional_current_user_cookie(
        request.cookies.get("access_token")
    )

    context.update({
        "request": request,
        "current_user": user,
    })

    return templates.TemplateResponse(template, context)