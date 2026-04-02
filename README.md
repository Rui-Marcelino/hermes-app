# Hermes Web Dashboard (hermes-app)

## 🌌 A Web UI Companion for Hermes Agent

`hermes-app` is a self-hosted web dashboard designed to provide a graphical user interface for interacting with and managing your Hermes Agent. It aims to make agent interaction, monitoring, and configuration more intuitive and accessible, especially for users who prefer a browser-based workflow over a pure command-line interface.

Inspired by robust multi-agent systems like `neo-app` and `jarbas-app`, this dashboard brings observability and control to your Hermes Agent.

---

## 💡 Core Value Proposition

`hermes-app` gives you a clean, real-time browser UI for everything that's often less convenient in a terminal, running on your local machine and accessible from any device on your network.

---

## ✨ Key Features

### Agent Interaction & Sessions
- **💬 Chat Panel**: Engage with your Hermes Agent through a dynamic chat interface. Supports persistent named conversations that survive browser closes, with auto-scrolling to the latest messages.
- **📋 Sessions Viewer**: Browse a full history of all your Hermes conversations. Filter by origin (CLI, Telegram, Cron, Web), view token usage, message count, and size. Easily resume any past session.
- **📓 Diary**: Maintain a personal journal with entries categorized by date and content, stored as Markdown files.
- **🛠️ Scripts Orchestrator**: Run and monitor your defined scripts directly from the browser. Features one-click execution, live log viewing, and configurable backup destinations.

### System Monitoring & Management
- **📊 Dashboard**: A real-time system monitor displaying CPU, memory, disk, and network usage, complemented by live charts for historical data. Keep an eye on Hermes Agent service health and overall system performance.
- **⏰ Cron Jobs (Planned)**: A dedicated interface for visual management of scheduled Hermes jobs, allowing for easy creation, pausing, resuming, and monitoring.
- **🧩 Skills Management (Planned)**: Browse and manage your installed Hermes skills via the browser.
- **⚙️ Config Editor (Planned)**: Edit `config.yaml` settings through a user-friendly web interface.

---

## 🚀 Getting Started

To get `hermes-app` up and running:

1.  **Clone this repository**:
    ```bash
    git clone https://github.com/Rui-Marcelino/hermes-app.git
    cd hermes-app
    ```
2.  **Install Python dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Run the application**:
    ```bash
    ./start.sh
    ```
    This will start the Flask server, typically accessible at `http://localhost:6080`.

Ensure your main Hermes Agent gateway is running and accessible for `hermes-app` to function correctly.

---

## ⚙️ Configuration

- **Backup script**: The `scripts/hermes-app-backup.sh` now accepts an optional argument for the backup destination directory.
  ```bash
  ./scripts/hermes-app-backup.sh /path/to/your/backups
  # Or use default destination:
  ./scripts/hermes-app-backup.sh
  ```

---

## 📸 Screenshots

*(To be added)*

---

## 🤝 Contributing & Feedback

All contributions, bug reports, and feature requests are welcome! Feel free to open an issue or submit a pull request on GitHub.

---

## 📄 License

This project is licensed under the MIT License - see the `LICENSE` file for details.