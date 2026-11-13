"""The two web endpoints the phone calls (the contract, CLAUDE.md section 6).  (Owner: Voice)

The server mounts this with one line. Without ELEVENLABS_API_KEY both return 501
and the phone falls back to the browser's own voice. Both need the pairing code
(X-HomeCall-Code header or ?code=), because they spend ElevenLabs credits.
"""
from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from fastapi.responses import Response

from pc.voice import duplex, engine

router = APIRouter(prefix="/voice")
router.include_router(duplex.router)  # /voice/call (duplex call page) and /voice/llm/... (ElevenLabs -> Brain)


def _paired(code: str | None) -> None:
    """These endpoints spend ElevenLabs credits: only for someone who knows the pairing code.
    The phone sends it as the X-HomeCall-Code header (or ?code=...)."""
    duplex._check_code(code or "")


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), code: str | None = None,
                     x_homecall_code: str | None = Header(default=None)) -> dict:
    _paired(x_homecall_code or code)
    data = await audio.read()
    try:
        text = engine.transcribe(data, audio.content_type or "")
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:  # noqa: BLE001 - provider down/out of credits: say so, the phone falls back
        raise HTTPException(status_code=502, detail=f"Voice provider error: {e}")
    return {"text": text}


@router.get("/speak")
def speak(text: str, code: str | None = None, x_homecall_code: str | None = Header(default=None)) -> Response:
    _paired(x_homecall_code or code)
    try:
        mp3 = engine.speak(text)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Voice provider error: {e}")
    return Response(mp3, media_type="audio/mpeg")
