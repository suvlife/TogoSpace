![TogoSpace](image/togo_agent_team.png)

# TogoSpace 🚀

[English](README_EN.md) | [中文](README.md)

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-Tornado-orange.svg)](https://www.tornadoweb.org/)
[![UI](https://img.shields.io/badge/UI-Textual%20%2B%20Vue3-green.svg)](https://textual.textualize.io/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#)

**TogoSpace** is an open-source multi-agent collaboration software designed for Large Language Models (LLM). It allows multiple AI Agents to communicate freely and collaborate in real-time like a human team to solve complex tasks.

> **About the Name**: The project is named after the legendary sled dog **Togo** from the 1925 Serum Run to Nome. In a harsh winter, Togo led his team through the longest and most dangerous leg of the journey. We use this name to pay tribute to the spirit of fearless collaboration and mission-driven determination, which is the core quality we want to empower multi-agent teams with.

### Powered by TSP

TogoSpace's tool execution layer is powered by [TSP (Tool Service Protocol)](https://github.com/alexazhou/TSP) — a lightweight protocol for building LLM tool servers. With TSP, you can **build your own agent tools in 10 lines of code**.

---

## ✨ Key Features

### 1. True Team Collaboration
Multiple agents communicate freely in a unified group chat, inspiring each other and collaborating to achieve a 1+1>2 effect, simulating a real human team communication model.

![Chat Interface](image/en/chat.png)

### 2. Freely Defined Agent Personas
You can define each agent's role, professional skills, and personality. From a rigorous code reviewer to a creative product planner, you can build your exclusive AI dream team.

### 3. No Tedious Workflow Orchestration
No need to pre-plan rigid flowcharts. Thanks to powerful scheduling logic, agents can autonomously decide "who's next" based on the task progress, making it ideal for dynamic and complex scenarios.

### 4. Powerful Multi-level Team Architecture
Supports multi-department and multi-level organizational management. You can divide departments (Dept) like a real company to handle large-scale complex engineering tasks with many agents.

![Team Editor](image/en/team_editor.png)

### 5. Fully Visualized Experience
No more "black box" operations. Equipped with a modern Web frontend, everything from team configuration to every step of an agent's reasoning and message flow is visualized in real-time.

### 6. Ultimate Cross-platform Compatibility
Built with Python and modern frontend technologies, it perfectly supports macOS, Windows, and Linux.

### 7. Stock Technical Analysis Team (New)
Built-in AI team based on four classic technical analysis schools: Wyckoff, Gann, Dow Theory, and Elliott Wave. Supports web search to fetch the latest data for stock trend analysis.

### 8. One-click Multi-provider LLM Config (New)
Supports mainstream providers including Kimi, Xiaomi MiMo, Volcengine AgentPlan, DeepSeek, Qwen, OpenAI, and Anthropic. Just select from the dropdown in Settings and enter your API key.

### 9. Token Usage Visualization (New)
The Settings page now has a "Usage" panel showing Prompt / Completion / Total token consumption trends and distribution by Agent / Model.

### 10. Skills Import & Web Search (New)
Supports uploading zip files to import custom Skills. Agents can call `web_search` / `web_fetch` tools to retrieve real-time web information for more comprehensive analysis.

---

## 🚀 Quick Start

### Try the Demo
- **English Demo**: [https://demo2.togoagent.org](https://demo2.togoagent.org)

### Method 1: Download Pre-built App Package (Recommended for macOS Users)
We currently provide a **macOS** Release package for a quick start.
- **Download**: [Go to the Releases page](https://github.com/alexazhou/TogoAgent/releases)
- **Usage**: Once running, TogoSpace stays in your system status bar. Click the icon to open the console, manage teams, or execute tasks.

![Status Bar Entry](image/en/entry.png)

### Method 2: Run from Source
```bash
# Clone the repository
git clone https://github.com/suvlife/togospace.git
cd togospace

# Install backend dependencies
pip install -r requirements.txt

# Start backend service (reads dev_storage_root/setting.json by default)
./scripts/start_backend.sh

# Start Web console (requires entering frontend directory)
cd frontend && npm install && npm run dev
```

Configure Tavily web search (optional):
```bash
# Option 1: Environment variable
export TAVILY_API_KEY=your_tavily_api_key
./scripts/start_backend.sh

# Option 2: Add to provider_params in setting.json
# In dev_storage_root/setting.json, add inside any llm_service's provider_params:
# "tavily_api_key": "your_tavily_api_key"
```

### Method 3: Docker Deployment
```bash
# Pull the image from GitHub Container Registry (recommended)
docker pull ghcr.io/alexazhou/togospace:latest

# Or from Docker Hub
# docker pull alexazhou/togospace:latest

# Run with storage persistence and port mapping
# /path/to/your/storage is the directory where TogoSpace data will be stored
docker run \
  --name togospace \
  -p 8080:8080 \
  -v /path/to/your/storage:/storage \
  ghcr.io/alexazhou/togospace:latest

# Access the Web console at http://localhost:8080
```

---

## 📂 Project Structure

- `src/`: Backend core logic, including agent scheduling, drivers, and persistence.
- `frontend/`: Visualization console based on Vue 3 + TypeScript.
- `tui/`: Terminal interface based on Textual.
- `assets/`: Preset role templates, team configurations, LLM provider catalog, and i18n support.
- `dev_storage_root/`: Development mode runtime data (setting.json, SQLite, logs, etc.; not committed).
- `docs/`: In-depth documentation on architecture, scheduling logic, task lifecycle, etc.

---

## 🛠️ Troubleshooting

1.  **Accessing Backend Settings**: The entry to the backend settings page is located at the **gear icon** in the top-left corner.
2.  **Repetitive Model Responses**: If the model keeps repeating itself, it might be because "Thought/Reasoning" is not enabled. Try enabling the **Reasoning Mode** configuration in the **Advanced Settings**.
3.  **Agent Execution Failures**: If an agent fails to call the LLM or stops running due to other errors, you can click on the **agent card** in the bottom-left corner and then click **Retry**.
4.  **Data Corruption/Errors**: If you encounter data-related issues that prevent the system from running, you can use the **Clear Team Data** option in the backend settings to reset and fix the state.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
