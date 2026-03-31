export function BrowserBlocked() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-bg-base px-6 text-center">
      <div className="w-14 h-14 rounded-2xl gradient-brand flex items-center justify-center">
        <span className="text-white font-bold text-lg">AL</span>
      </div>
      <h1 className="text-lg font-semibold text-text-primary">请使用桌面客户端</h1>
      <p className="text-sm text-text-secondary max-w-md">
        AgentLoom 界面仅随 Electron 应用提供，请勿在浏览器中直接打开开发地址。
      </p>
    </div>
  );
}
