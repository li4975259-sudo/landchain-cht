from fastapi import APIRouter, File, HTTPException, Request, UploadFile



from app.models.schemas import IngestResponse, UploadResponse

from app.services.ollama_client import check_ollama_health



router = APIRouter(prefix="/documents", tags=["documents"])





async def _ensure_ollama(request: Request) -> None:

    if not await check_ollama_health(request.app.state.settings):

        raise HTTPException(status_code=503, detail="Ollama service is unavailable")





@router.post("/upload", response_model=UploadResponse)

async def upload_document(

    request: Request,

    file: UploadFile = File(...),

) -> UploadResponse:

    await _ensure_ollama(request)



    settings = request.app.state.settings

    ingest_service = request.app.state.ingest_service



    if not file.filename:

        raise HTTPException(status_code=400, detail="Filename is required")



    content = await file.read()

    if len(content) > settings.max_upload_size_bytes:

        raise HTTPException(

            status_code=400,

            detail=f"File exceeds max size of {settings.max_upload_size_mb}MB",

        )



    try:

        saved_path = ingest_service.save_upload(file.filename, content)

        chunks_added, source = ingest_service.ingest_file(saved_path, force=True)

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except Exception as exc:

        raise HTTPException(status_code=500, detail=f"Ingest failed: {exc}") from exc



    return UploadResponse(

        filename=file.filename,

        chunks_added=chunks_added,

        sources=[source],

    )





@router.post("/ingest", response_model=IngestResponse)

async def ingest_data_dir(request: Request) -> IngestResponse:

    await _ensure_ollama(request)



    ingest_service = request.app.state.ingest_service

    try:

        files_processed, chunks_added, skipped = ingest_service.ingest_directory()

    except Exception as exc:

        raise HTTPException(status_code=500, detail=f"Ingest failed: {exc}") from exc



    return IngestResponse(

        files_processed=files_processed,

        chunks_added=chunks_added,

        skipped=skipped,

    )


