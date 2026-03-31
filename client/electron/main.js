const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const {
  startPythonBackend,
  stopPythonBackend,
  waitForBackend,
} = require("./python-manager");

let mainWindow = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    frame: false,
    titleBarStyle: "hidden",
    backgroundColor: "#09090f",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

// 窗口控制 IPC
ipcMain.on("window:minimize", () => mainWindow?.minimize());
ipcMain.on("window:maximize", () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize();
  } else {
    mainWindow?.maximize();
  }
});
ipcMain.on("window:close", () => mainWindow?.close());

// 后端状态 IPC
ipcMain.handle("backend:status", async () => {
  const http = require("http");
  return new Promise((resolve) => {
    const req = http.get("http://127.0.0.1:9800/health", (res) => {
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(2000, () => {
      req.destroy();
      resolve(false);
    });
  });
});

app.whenReady().then(async () => {
  try {
    console.log("[Main] Starting Python backend...");
    await startPythonBackend();
    console.log("[Main] Waiting for backend health check...");
    const ready = await waitForBackend();
    if (ready) {
      console.log("[Main] Backend is ready!");
    } else {
      console.warn("[Main] Backend health check timed out, continuing anyway...");
    }
  } catch (err) {
    console.error("[Main] Failed to start Python backend:", err.message);
    // 开发模式下后端可能已手动启动，继续创建窗口
  }

  createWindow();
});

app.on("before-quit", () => {
  stopPythonBackend();
});

app.on("window-all-closed", () => {
  stopPythonBackend();
  app.quit();
});
