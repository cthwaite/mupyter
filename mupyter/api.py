"""A Python REPL using `CompileCtx` implemented as a JSON REST API.
"""

import datetime as dt
import logging
import sys
import traceback
import uuid
from typing import Dict

from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from .compile import CompileCtx


log = logging.getLogger(__name__)


class Kernel(BaseModel):
    """Kernel metadata
    """
    class Config:
        arbitrary_types_allowed = True

    ctx: CompileCtx
    created_at: dt.datetime
    processed: int = 0

    @classmethod
    def create(cls) -> 'Kernel':
        return cls(
            ctx=CompileCtx(),
            created_at=dt.datetime.now(),
        )


class KernelAPI(FastAPI):
    """API with built-in execution context storage.

    Attributes:
        _kernels
    """
    def __init__(self):
        super().__init__()
        self._kernels: Dict[str, Kernel] = {}

    def _create_kernel_impl(self) -> str:
        """Create a kernel and add it to the list of kernels.
        """
        key = str(uuid.uuid4())
        self._kernels[key] = Kernel.create()
        return key


app = KernelAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _links_for_kernel(key: str):
    """Generate kernel manipulation paths for a given key.
    """
    return {
        "process": {"href": f"/kernels/{key}/process", "method": "POST"},
        "describe": {"href": f"/kernels/{key}", "method": "GET"},
        "delete": {"href": f"/kernels/{key}", "method": "DELETE"},
    }


@app.get("/kernels")
def get_kernels():
    """List running kernels."""
    return {
        "kernels": [
            {
                "key": key,
                "created_at": kernel.created_at,
                "processed": kernel.processed,
                "_links": _links_for_kernel(key),
            }
            for key, kernel in app._kernels.items()
        ]
    }


@app.put("/kernels")
def create_kernel():
    key = app._create_kernel_impl()
    return {
        "key": key,
        "_links": _links_for_kernel(key),
    }


@app.get("/kernels/{key}")
def kernel_info(key: str):
    try:
        kern = app._kernels[key]
        return {
            "created_at": kern.created_at,
            "processed": kern.processed,
            "_links": _links_for_kernel(key),
        }
    except KeyError:
        raise HTTPException(404, detail="No such kernel")


@app.delete("/kernels/{key}")
def delete_kernel(key: str):
    try:
        kern = app._kernels.pop(key)
        return {
            "deleted": True,
            "created_at": kern.created_at,
            "processed": kern.processed,
        }
    except KeyError:
        raise HTTPException(404, detail="No such kernel")


class CellData(BaseModel):
    code: str


@app.post("/kernels/{key}/process")
def kernel_process(key: str, cell: CellData):
    try:
        kern = app._kernels[key]
    except KeyError:
        raise HTTPException(404, detail="No such kernel")
    try:
        kid, *_ = key.split("-")
        output = kern.ctx.run_cell(cell.code, f"{kid}-input-{kern.processed}")
        kern.processed += 1
        return {
            "ok": True,
            "error": None,
            "output": output,
        }
    except Exception as err:
        kern.processed += 1
        log.info(err, exc_info=True)
        *_, tb = sys.exc_info()
        rsp = {
            "ok": False,
            "error": {
                "msg": str(err),
                "type": type(err).__name__,
            },
            "output": traceback.format_tb(tb),
        }
        log.info(rsp)
        return rsp


@app.get("/")
def main():
    return FileResponse("./static/index.html")
