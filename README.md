# Modeling Copilot

Modeling Copilot is a research prototype for creating, managing, and using
configurable graphical modeling languages in higher education. It combines a
generic browser-based modeling editor with versioned language definitions,
modeling tasks, models, syntax constraints, and addressable feedback.

The long-term goal is a language-independent learning environment that supports
students while they learn graphical modeling. Future agentic support should not
simply generate solutions. It should select pedagogically appropriate actions,
such as asking a question, highlighting a relevant model element, invoking a
diagnostic service, giving a graduated hint, waiting, or escalating an
uncertain case to an educator.

> **Project status:** Active research prototype. Core modeling and
> configuration workflows are under development. Agentic tutoring, adaptive
> learner support, and learning effectiveness are research goals and are not
> yet production-ready or empirically established by this repository.

## Architecture

| Component             | Technology                                 | Responsibility                                   |
| --------------------- | ------------------------------------------ | ------------------------------------------------ |
| `web/`                | Vue 3, TypeScript, Vite, Vuetify, maxGraph | Modeling UI, language editor, and task editor    |
| `api/`                | Python 3.13, FastAPI, Pydantic, PyMongo    | Authenticated API and versioned persistence      |
| MongoDB               | MongoDB 8                                  | Languages, tasks, models, versions, and feedback |
| `docker-compose.yaml` | Docker Compose                             | Local MongoDB and API services                   |

## Local development

### Prerequisites

- Git
- Docker with Docker Compose
- Node.js 20 or newer with npm
- Python 3.13 when running the API outside Docker

### Clone the repository

```sh
git clone https://github.com/thm-mni-ii/modeling-copilot.git
cd modeling-copilot
```

### Start the API and database with Docker

```sh
docker compose up -d --build
```

The API is available at <http://localhost:8000>. Swagger UI is available at
<http://localhost:8000/docs> while API documentation is enabled.

Useful Docker commands:

```sh
docker compose logs -f api
docker compose logs -f mongo
docker compose down
```

### Start the web application

In a second terminal:

```sh
cd web
npm ci
npm run dev
```

The Vite development server proxies API requests to the backend at <http://localhost:8085>.

### Run the API without Docker

Keep MongoDB in Docker and run FastAPI in a Python virtual environment:

```powershell
py -3.13 -m venv api/.venv
api/.venv/Scripts/python.exe -m pip install -r api/requirements.txt
docker compose up -d mongo
api/.venv/Scripts/Activate.ps1
uvicorn modeling_api.main:app --app-dir api/src --reload
```

On Linux or macOS, activate the environment with:

```sh
source api/.venv/bin/activate
```

Local development defaults are defined in
`api/src/modeling_api/core/config.py`. The application currently expects a JWT
bearer token issued by an external system; it does not provide user
registration or password login.

## Checks

Build and type-check the web application:

```sh
cd web
npm run build
```

Lint and automatically format supported web files:

```sh
cd web
npm run lint
```

The lint command currently applies fixes. Review its changes before committing.
Automated API and frontend test suites are not yet configured as repository
scripts.

## Contributing

Contributions are welcome through issues and pull requests. Before starting a
larger change, open an issue so that its scope, educational intent, and
architectural fit can be discussed. See [CONTRIBUTING.md](CONTRIBUTING.md) for
the development and review process.

Do not add real learner data, credentials, private teaching material, or
confidential research data to the repository.

## License

Modeling Copilot is licensed under the
[PolyForm Noncommercial License 1.0.0](LICENSE). The software may be used,
modified, and redistributed for permitted noncommercial purposes. Commercial
use is not granted.

Because it restricts commercial use, this is a source-available license rather
than an OSI-approved open-source license.

## Acknowledgements

Modeling Copilot is developed in a higher-education research context at the
University of Applied Sciences Mittelhessen (THM).
