from fastapi import APIRouter, Depends, HTTPException, Request

from app.db.models import Project
from app.security import require_token
from app.workspace import git as workspace_git
from app.workspace.files import MAX_FILE_BYTES, WorkspaceError, WorkspaceFiles

router = APIRouter(prefix="/api", tags=["engineering"], dependencies=[Depends(require_token)])


def _workspace(request: Request, project_id: str) -> WorkspaceFiles:
    with request.app.state.session_factory() as s:
        p = s.get(Project, project_id)
        if p is None or p.deleted_at is not None:
            raise HTTPException(404, "Proyek tidak ditemukan")
    root = request.app.state.settings.projects_dir / project_id / "workspace" / "source-code"
    return WorkspaceFiles(root)


@router.get("/sandbox")
async def sandbox_status(request: Request):
    cfg = request.app.state.settings
    st = await request.app.state.sandbox.status()
    selftest = st.details.get("selftest") if st.details else None
    return {
        "configured_backend": cfg.sandbox_backend, "backend": st.backend, "available": st.available,
        "reason": st.reason, "message": st.message, "selftest": selftest,
        "limits": {"timeout_s": cfg.sandbox_timeout_s, "memory_mb": cfg.sandbox_memory_mb,
                   "max_output_kb": cfg.sandbox_max_output_kb, "network": False},
    }


@router.post("/sandbox/selftest")
async def sandbox_selftest(request: Request):
    sandbox = request.app.state.sandbox
    basic = await sandbox.status() if sandbox.name == "none" else None
    if basic is not None and not basic.available:
        return {"passed": False, "checks": [], "ran_at": None, "reason": basic.reason, "message": basic.message}
    return await sandbox.selftest()


@router.get("/projects/{project_id}/workspace")
def workspace_overview(project_id: str, request: Request):
    files = _workspace(request, project_id)
    return {"files": [{"path": f.path, "size": f.size} for f in files.list()], "commits": workspace_git.log(files.root)}


@router.get("/projects/{project_id}/workspace/file")
def workspace_file(project_id: str, path: str, request: Request):
    files = _workspace(request, project_id)
    try:
        content = files.read(path)
    except WorkspaceError as e:
        raise HTTPException(404, str(e))
    return {"path": path, "size": len(content.encode("utf-8")), "content": content[: MAX_FILE_BYTES]}
