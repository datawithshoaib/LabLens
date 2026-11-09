"""Request body limits for the report upload route."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class UploadBodyLimitMiddleware:
    """Stop oversized multipart bodies before Starlette spools them to disk."""

    def __init__(self, app: ASGIApp, max_upload_bytes: int, multipart_overhead: int = 64 * 1024):
        self.app = app
        self.limit = max_upload_bytes + multipart_overhead

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if (
            scope.get("type") != "http"
            or scope.get("method") != "POST"
            or not path.endswith("/reports")
        ):
            await self.app(scope, receive, send)
            return

        raw_length = dict(scope.get("headers", [])).get(b"content-length")
        if raw_length is not None:
            try:
                if int(raw_length) > self.limit:
                    await self._reject(send)
                    return
            except ValueError:
                await self._reject(send)
                return

        received = 0
        oversized = False

        async def limited_receive() -> Message:
            nonlocal received, oversized
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.limit:
                    oversized = True
                    return {"type": "http.disconnect"}
            return message

        async def limited_send(message: Message) -> None:
            if not oversized:
                await send(message)

        try:
            await self.app(scope, limited_receive, limited_send)
        except Exception:
            if not oversized:
                raise
        if oversized:
            await self._reject(send)

    @staticmethod
    async def _reject(send: Send) -> None:
        body = b'{"detail":"Report exceeds the upload size limit"}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
