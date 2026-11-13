"""The two web endpoints the phone calls (the contract, CLAUDE.md section 6).  (Owner: Voice)

The server mounts this with one line. Until engine.py is implemented, both
return 501 and the phone falls back to the browser's own voice.
"""
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from pc.voice import engine

router = APIRouter(prefix="/voice")


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> dict:
    data = await audio.read()
    try:
        text = engine.transcribe(data, audio.content_type or "")
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    return {"text": text}


@router.get("/speak")
def speak(text: str) -> Response:
    try:
        mp3 = engine.speak(text)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    return Response(mp3, media_type="audio/mpeg")
