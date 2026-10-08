import hashlib

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


EMAIL = "23f2004539@ds.study.iitm.ac.in".strip().lower()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


TOOL = {
    "name": "solve_challenge",
    "description": "Reads the X-Exam-Challenge HTTP header and returns the exam response token.",
    "inputSchema": {
        "type": "object",
        "properties": {},
    },
}


def solve(challenge: str) -> str:
    value = f"{challenge}:{EMAIL}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def ok(request_id, result):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }


def err(request_id, code, message):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }


def handle(msg: dict, headers):
    method = msg.get("method")
    request_id = msg.get("id")

    # JSON-RPC notification: no response body is required.
    if request_id is None:
        return None

    if method == "initialize":
        return ok(
            request_id,
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {
                    "tools": {
                        "listChanged": False
                    }
                },
                "serverInfo": {
                    "name": "exam-mcp",
                    "version": "1.0.0",
                },
            },
        )

    if method == "ping":
        return ok(request_id, {})

    if method == "tools/list":
        return ok(
            request_id,
            {
                "tools": [TOOL]
            },
        )

    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")

        if name != "solve_challenge":
            return err(
                request_id,
                -32602,
                f"Unknown tool: {name}",
            )

        # The grader supplies the challenge in the HTTP header.
        # It is intentionally NOT read from the JSON request body.
        challenge = headers.get("x-exam-challenge", "")

        if not challenge:
            return ok(
                request_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": "missing X-Exam-Challenge header",
                        }
                    ],
                    "isError": True,
                },
            )

        return ok(
            request_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": solve(challenge),
                    }
                ]
            },
        )

    return err(
        request_id,
        -32601,
        f"Method not found: {method}",
    )


@app.post("/mcp")
async def mcp(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            err(None, -32700, "Parse error"),
            status_code=400,
        )

    if isinstance(body, list):
        responses = []

        for message in body:
            response = handle(message, request.headers)
            if response is not None:
                responses.append(response)

        if not responses:
            return Response(status_code=202)

        return JSONResponse(responses)

    response = handle(body, request.headers)

    if response is None:
        return Response(status_code=202)

    return JSONResponse(response)


@app.get("/mcp")
async def mcp_get():
    return Response(
        status_code=405,
        headers={"Allow": "POST"},
    )


@app.get("/")
async def health():
    return {"status": "ok"}
