# Third-party components

The MIT license in this repository applies to original project code only, to the
extent contributors have the right to license it. It does not relicense third-party
code, images, Windows/Wine binaries, broker installers, trademarks or data.

Runtime components include the gmag11/metatrader5_vnc base image and its components,
Wine, Python, MetaTrader 5 / IC Markets terminal, MetaTrader5 Python bindings,
FastAPI, Uvicorn, RPyC, websockets and Swagger UI. Their respective upstream licenses,
notices and distribution terms continue to apply. This list is not an exhaustive SBOM.

Do not assume the repository MIT license authorizes redistributing a broker terminal
or a prepared Wine prefix. Check upstream distribution terms before publishing
images containing third-party binaries. Never publish account data or login secrets.
