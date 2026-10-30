# PyInstaller spec — bundles the FastAPI backend into a single executable.
import os

block_cipher = None

a = Analysis(
    ["run.py"],
    pathex=[os.getcwd()],
    binaries=[],
    datas=[],
    hiddenimports=[
        # Application modules
        "app",
        "app.main",
        "app.db",
        "app.models",
        "app.models.circuit",
        "app.models.netlist",
        "app.models.results",
        "app.routers",
        "app.routers.circuits",
        "app.routers.simulation",
        "app.simulation",
        "app.simulation.mna",
        "app.simulation.dc_analysis",
        "app.simulation.ac_analysis",
        "app.simulation.transient",
        # uvicorn internals (not auto-detected)
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        # numpy / scipy
        "numpy",
        "numpy.core._multiarray_umath",
        "scipy",
        "scipy.linalg",
        "scipy.sparse",
        "scipy.sparse.csgraph._validation",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="circuit-simulator-backend",
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
)
