const { spawn } = require("child_process");
const path = require("path");
const http = require("http");

let pythonProcess = null;
const API_PORT = 9800;
const HEALTH_URL = `http://127.0.0.1:${API_PORT}/health`;

/**
 * 启动 Python FastAPI 后端。
 * - 开发模式：python -m agentloom.api.server
 * - 生产模式：打包的 agentloom-api.exe
 */
function startPythonBackend() {
  return new Promise((resolve, reject) => {
    const isDev = !!(
      process.env.VITE_DEV_SERVER_URL || process.env.NODE_ENV === "development"
    );

    let cmd, args, cwd;

    if (isDev) {
      cmd = process.platform === "win32" ? "python" : "python3";
      args = ["-m", "agentloom.api.server"];
      // 项目根目录（client/../）
      cwd = path.resolve(__dirname, "../../");
    } else {
      // 生产模式：打包的可执行文件在 resources/backend/ 下
      const exeName =
        process.platform === "win32" ? "agentloom-api.exe" : "agentloom-api";
      cmd = path.join(process.resourcesPath, "backend", exeName);
      args = [];
      cwd = path.dirname(cmd);
    }

    console.log(`[PythonManager] Starting: ${cmd} ${args.join(" ")} (cwd: ${cwd})`);

    pythonProcess = spawn(cmd, args, {
      cwd,
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env, AGENTLOOM_ROOT: cwd },
    });

    let resolved = false;

    pythonProcess.stdout.on("data", (data) => {
      const text = data.toString();
      console.log("[Python:stdout]", text.trim());
      if (!resolved && text.includes("Uvicorn running")) {
        resolved = true;
        resolve();
      }
    });

    pythonProcess.stderr.on("data", (data) => {
      console.error("[Python:stderr]", data.toString().trim());
    });

    pythonProcess.on("error", (err) => {
      console.error("[PythonManager] Spawn error:", err.message);
      if (!resolved) {
        resolved = true;
        reject(err);
      }
    });

    pythonProcess.on("exit", (code) => {
      console.log(`[PythonManager] Process exited with code ${code}`);
      pythonProcess = null;
      if (!resolved) {
        resolved = true;
        reject(new Error(`Python exited with code ${code}`));
      }
    });

    // 超时 fallback：如果 10 秒内没收到 stdout 信号，尝试健康检查
    setTimeout(() => {
      if (!resolved) {
        resolved = true;
        resolve();
      }
    }, 10000);
  });
}

/**
 * 停止 Python 后端进程
 */
function stopPythonBackend() {
  if (pythonProcess) {
    console.log("[PythonManager] Stopping Python backend...");
    pythonProcess.kill();
    pythonProcess = null;
  }
}

/**
 * 轮询健康检查，等待后端就绪
 * @param {number} maxWaitMs 最大等待毫秒数
 * @param {number} intervalMs 轮询间隔
 * @returns {Promise<boolean>}
 */
function waitForBackend(maxWaitMs = 15000, intervalMs = 500) {
  return new Promise((resolve) => {
    const start = Date.now();

    function check() {
      if (Date.now() - start > maxWaitMs) {
        resolve(false);
        return;
      }

      const req = http.get(HEALTH_URL, (res) => {
        if (res.statusCode === 200) {
          resolve(true);
        } else {
          setTimeout(check, intervalMs);
        }
      });

      req.on("error", () => {
        setTimeout(check, intervalMs);
      });

      req.setTimeout(2000, () => {
        req.destroy();
        setTimeout(check, intervalMs);
      });
    }

    check();
  });
}

module.exports = { startPythonBackend, stopPythonBackend, waitForBackend };
