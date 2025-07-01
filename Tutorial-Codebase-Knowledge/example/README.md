<h1 align="center">PocketFlow-Tutorial-Codebase-Knowledge Streamlit Web App</h1>

## Running with Docker

1. Download this example folder

2. Copy .env.example file:
   ```bash
   cp .env.example .env
   ```
3. Enter GEMINI_MODEL and GEMINI_API_KEY on .env file

4. Edit docker-compose.yml to change custom port for nginx. Default port is :80. You need to change this port if your localhost :80 port already in use by another webserver, for example apache or nginx is already installed in your computer.

5. Run docker compose in detach mode

   ```bash
   docker-compose up --detach
   ```

6. open http://localhost:80 or your custom port.
