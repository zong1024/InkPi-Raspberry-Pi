import { lazy, Suspense, useEffect, useMemo, useState } from "react";

const EMPTY_DASHBOARD = {
  snapshot: null,
  logs: [],
  pipeline: [],
  runtime_logs: {},
};

const HEALTH_LABELS = {
  good: "正常",
  warn: "关注",
  bad: "异常",
};

const HEALTH_CLASSES = {
  good: "good",
  warn: "warn",
  bad: "bad",
};

const DIMENSION_LABELS = {
  structure: "结构",
  stroke: "笔画",
  integrity: "完整",
  stability: "稳定",
};

const ThreeBackdrop = lazy(() => import("./ThreeBackdrop"));

function useOpsDashboard() {
  const [dashboard, setDashboard] = useState(EMPTY_DASHBOARD);
  const [connection, setConnection] = useState("connecting");

  useEffect(() => {
    let disposed = false;

    async function loadBootstrap() {
      try {
        const response = await fetch("/api/ops/bootstrap");
        const payload = await response.json();
        if (!disposed) {
          setDashboard(payload);
          setConnection("ready");
        }
      } catch (error) {
        if (!disposed) {
          setConnection("error");
        }
      }
    }

    loadBootstrap();
    return () => {
      disposed = true;
    };
  }, []);

  useEffect(() => {
    const stream = new EventSource("/api/ops/stream");

    stream.onopen = () => setConnection("ready");
    stream.onerror = () => setConnection("degraded");
    stream.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      setDashboard((current) => ({
        snapshot: payload.snapshot ?? current.snapshot,
        logs: mergeById(current.logs, payload.logs || []),
        pipeline: mergeById(current.pipeline, payload.pipeline || []),
        runtime_logs: payload.runtime_logs || current.runtime_logs,
      }));
    };

    return () => {
      stream.close();
    };
  }, []);

  return { dashboard, connection };
}

function mergeById(current, incoming) {
  const map = new Map();
  [...current, ...incoming].forEach((item) => {
    if (item && item.id !== undefined) {
      map.set(item.id, item);
    }
  });
  return [...map.values()].slice(-160);
}

function App() {
  const { dashboard, connection } = useOpsDashboard();
  const snapshot = dashboard.snapshot;
  const runtimeLogKeys = Object.keys(dashboard.runtime_logs || {});
  const [activeRuntimeLog, setActiveRuntimeLog] = useState("web_ui");

  useEffect(() => {
    if (!runtimeLogKeys.length) {
      return;
    }
    if (!runtimeLogKeys.includes(activeRuntimeLog)) {
      setActiveRuntimeLog(runtimeLogKeys[0]);
    }
  }, [activeRuntimeLog, runtimeLogKeys]);

  const summaryCards = useMemo(() => {
    if (!snapshot) {
      return [];
    }
    return [
      {
        title: "主机温度",
        value: snapshot.host?.temperature_c != null ? `${snapshot.host.temperature_c}°C` : "--",
        meta: snapshot.host?.platform || "Unknown",
      },
      {
        title: "内存占用",
        value:
          snapshot.host?.memory?.percent != null ? `${snapshot.host.memory.percent}%` : "--",
        meta:
          snapshot.host?.memory?.used_mb != null && snapshot.host?.memory?.total_mb != null
            ? `${snapshot.host.memory.used_mb} / ${snapshot.host.memory.total_mb} MB`
            : "Memory offline",
      },
      {
        title: "磁盘占用",
        value: snapshot.host?.disk?.percent != null ? `${snapshot.host.disk.percent}%` : "--",
        meta:
          snapshot.host?.disk?.used_gb != null && snapshot.host?.disk?.total_gb != null
            ? `${snapshot.host.disk.used_gb} / ${snapshot.host.disk.total_gb} GB`
            : "Disk offline",
      },
      {
        title: "运行时长",
        value: formatUptime(snapshot.app?.uptime_seconds || 0),
        meta: `${snapshot.app?.mode || "unknown"} / PID ${snapshot.app?.pid || "--"}`,
      },
    ];
  }, [snapshot]);

  return (
    <div className="console-shell">
      <Suspense fallback={null}>
        <ThreeBackdrop />
      </Suspense>

      <header className="topbar">
        <div className="topbar-copy">
          <span className="eyebrow">INKPI OPERATIONS CENTER</span>
          <h1>InkPi 设备运行中心</h1>
          <p>实时查看树莓派主机状态、评测链路、模型加载、硬件健康和结果输出。</p>
        </div>
        <div className={`connection-chip ${connection}`}>
          <span className="dot" />
          <div>
            <strong>
              {connection === "ready"
                ? "实时连接正常"
                : connection === "degraded"
                  ? "实时流波动"
                  : "正在连接"}
            </strong>
            <small>SSE / /api/ops/stream</small>
          </div>
        </div>
      </header>

      <section className="hero-grid">
        <div className="panel hero-panel">
          <div className="panel-heading">
            <span>运行总览</span>
            <strong>{snapshot?.app?.name || "InkPi"}</strong>
          </div>
          <div className="summary-grid">
            {summaryCards.map((card) => (
              <div className="summary-card" key={card.title}>
                <span>{card.title}</span>
                <strong>{card.value}</strong>
                <small>{card.meta}</small>
              </div>
            ))}
          </div>
          <div className="host-meta">
            <span>主机名：{snapshot?.host?.hostname || "--"}</span>
            <span>IP：{snapshot?.host?.ip_address || "--"}</span>
            <span>Python：{snapshot?.app?.python || "--"}</span>
          </div>
        </div>

        <div className="panel service-panel">
          <div className="panel-heading">
            <span>栈状态</span>
            <strong>STACK STATUS</strong>
          </div>
          <StatusList items={stackItems(snapshot)} />
        </div>
      </section>

      <section className="dashboard-grid">
        <div className="panel">
          <div className="panel-heading">
            <span>评测流程</span>
            <strong>PIPELINE</strong>
          </div>
          <PipelineTimeline items={dashboard.pipeline} />
        </div>

        <div className="panel">
          <div className="panel-heading">
            <span>模型状态</span>
            <strong>MODELS</strong>
          </div>
          <StatusList items={modelItems(snapshot)} dense />
        </div>

        <div className="panel">
          <div className="panel-heading">
            <span>硬件健康</span>
            <strong>HARDWARE</strong>
          </div>
          <StatusList items={hardwareItems(snapshot)} dense />
        </div>

        <div className="panel">
          <div className="panel-heading">
            <span>最近结果</span>
            <strong>RESULTS</strong>
          </div>
          <ResultFeed results={snapshot?.storage?.recent_results || []} />
        </div>
      </section>

      <section className="wide-grid">
        <div className="panel trend-panel">
          <div className="panel-heading">
            <span>评分走势</span>
            <strong>TREND</strong>
          </div>
          <TrendChart points={snapshot?.storage?.score_trend || []} />
        </div>

        <div className="panel console-panel">
          <div className="panel-heading">
            <span>后台输出</span>
            <strong>RUNTIME LOGS</strong>
          </div>
          <div className="runtime-tabs">
            {runtimeLogKeys.map((key) => (
              <button
                key={key}
                type="button"
                className={key === activeRuntimeLog ? "active" : ""}
                onClick={() => setActiveRuntimeLog(key)}
              >
                {key}
              </button>
            ))}
          </div>
          <LogPanel lines={dashboard.runtime_logs?.[activeRuntimeLog] || []} />
        </div>
      </section>

      <section className="wide-grid">
        <div className="panel console-panel">
          <div className="panel-heading">
            <span>应用日志缓冲</span>
            <strong>BUFFERED LOGS</strong>
          </div>
          <BufferedLogPanel logs={dashboard.logs} />
        </div>

        <div className="panel diagnostics-panel">
          <div className="panel-heading">
            <span>云同步与输出</span>
            <strong>SYNC STATUS</strong>
          </div>
          <CloudPanel snapshot={snapshot} />
        </div>
      </section>
    </div>
  );
}

function StatusList({ items, dense = false }) {
  return (
    <div className={`status-list ${dense ? "dense" : ""}`}>
      {items.map((item) => (
        <div className="status-row" key={item.title}>
          <div>
            <div className="status-title">{item.title}</div>
            <div className="status-meta">{item.message}</div>
          </div>
          <div className={`health-tag ${HEALTH_CLASSES[item.health] || "warn"}`}>
            {HEALTH_LABELS[item.health] || "关注"}
          </div>
        </div>
      ))}
    </div>
  );
}

function PipelineTimeline({ items }) {
  if (!items?.length) {
    return <div className="empty-state">等待新的评测链路事件进入监控视图。</div>;
  }

  const ordered = [...items].reverse();
  return (
    <div className="pipeline-list">
      {ordered.map((item) => (
        <div className="pipeline-item" key={item.id}>
          <div className={`pipeline-state ${item.status}`} />
          <div className="pipeline-body">
            <div className="pipeline-head">
              <span>{item.stage}</span>
              <small>{item.timestamp}</small>
            </div>
            <p>{item.message}</p>
            {item.details && Object.keys(item.details).length ? (
              <code>{JSON.stringify(item.details)}</code>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  );
}

function ResultFeed({ results }) {
  if (!results?.length) {
    return <div className="empty-state">还没有新的评测结果进入后台。</div>;
  }

  return (
    <div className="result-feed">
      {results.map((item) => (
        <div className="result-card" key={item.id}>
          <div className="result-score">{item.total_score}</div>
          <div className="result-body">
            <strong>{item.character_name || "未识别"}</strong>
            <span>{item.quality_level || "unknown"}</span>
            <small>{item.timestamp || "--"}</small>
            <div className="dimension-strip">
              {Object.entries(item.dimension_scores || {}).map(([key, value]) => (
                <span key={key}>
                  {DIMENSION_LABELS[key] || key} {value}
                </span>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function TrendChart({ points }) {
  if (!points?.length) {
    return <div className="empty-state">暂无评分趋势数据。</div>;
  }

  const values = points.map((item) => Number(item.total_score || 0));
  const maxValue = Math.max(...values, 100);
  const minValue = Math.min(...values, 0);
  const range = Math.max(maxValue - minValue, 1);
  const line = points
    .map((item, index) => {
      const x = (index / Math.max(points.length - 1, 1)) * 100;
      const y = 100 - ((Number(item.total_score || 0) - minValue) / range) * 100;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="trend-wrap">
      <svg viewBox="0 0 100 100" className="trend-svg" preserveAspectRatio="none">
        <polyline points={line} />
      </svg>
      <div className="trend-labels">
        {points.map((item) => (
          <div key={`${item.timestamp}-${item.total_score}`}>
            <strong>{item.total_score}</strong>
            <span>{item.character_name || "字"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function LogPanel({ lines }) {
  return (
    <div className="terminal-window">
      {lines.length ? (
        lines.map((line, index) => <div key={`${line}-${index}`}>{line}</div>)
      ) : (
        <div className="empty-state">当前没有运行日志输出。</div>
      )}
    </div>
  );
}

function BufferedLogPanel({ logs }) {
  return (
    <div className="terminal-window buffered">
      {logs.length ? (
        logs.slice(-90).map((item) => (
          <div key={item.id} className={`log-row level-${(item.level || "").toLowerCase()}`}>
            <span>[{item.timestamp}]</span>
            <span>{item.level}</span>
            <span>{item.source}</span>
            <span>{item.message}</span>
          </div>
        ))
      ) : (
        <div className="empty-state">应用日志缓冲暂时为空。</div>
      )}
    </div>
  );
}

function CloudPanel({ snapshot }) {
  const remote = snapshot?.cloud?.remote_health;
  const lastResult = snapshot?.last_result;
  return (
    <div className="cloud-panel">
      <div className="cloud-summary">
        <div>
          <span>云端后端</span>
          <strong>{snapshot?.cloud?.backend_url || "未配置"}</strong>
        </div>
        <div
          className={`health-tag ${remote?.ok ? "good" : snapshot?.cloud?.configured ? "warn" : "bad"}`}
        >
          {remote?.ok ? "已连通" : snapshot?.cloud?.configured ? "待检查" : "未配置"}
        </div>
      </div>
      <div className="cloud-meta">
        <span>设备名：{snapshot?.cloud?.device_name || "--"}</span>
        <span>同步超时：{snapshot?.cloud?.timeout_seconds || "--"}s</span>
      </div>
      <div className="cloud-last-result">
        <h3>最近一次输出</h3>
        {lastResult ? (
          <>
            <strong>
              {lastResult.character_name || "未识别"} / {lastResult.total_score}
            </strong>
            <p>{lastResult.feedback}</p>
          </>
        ) : (
          <div className="empty-state">还没有进入结果输出阶段。</div>
        )}
      </div>
    </div>
  );
}

function stackItems(snapshot) {
  if (!snapshot?.stack) return [];
  return [
    mapStatus("PyQt 正式端", snapshot.stack.qt_ui),
    mapStatus("Web 运维后台", snapshot.stack.web_ui),
    mapStatus("Cloud API", snapshot.stack.cloud_api),
  ];
}

function modelItems(snapshot) {
  if (!snapshot?.models) return [];
  return [
    {
      title: "OCR 本地模型",
      message: snapshot.models.ocr?.local_ready ? "PaddleOCR 本地推理可用" : "本地 OCR 不可用",
      health: snapshot.models.ocr?.local_ready ? "good" : snapshot.models.ocr?.remote_ready ? "warn" : "bad",
    },
    {
      title: "OCR 云端回退",
      message: snapshot.models.ocr?.remote_ready
        ? `远程 OCR 已配置：${snapshot.models.ocr?.backend_url}`
        : "远程 OCR 未配置",
      health: snapshot.models.ocr?.remote_ready ? "good" : "warn",
    },
    {
      title: "ONNX 评分模型",
      message: snapshot.models.quality_scorer?.ready
        ? `输入尺寸 ${snapshot.models.quality_scorer?.input_size}`
        : `模型缺失：${snapshot.models.quality_scorer?.model_path}`,
      health: snapshot.models.quality_scorer?.ready ? "good" : "bad",
    },
    {
      title: "四维解释层",
      message: "结构 / 笔画 / 完整 / 稳定",
      health: snapshot.models.dimension_scorer?.ready ? "good" : "warn",
    },
  ];
}

function hardwareItems(snapshot) {
  if (!snapshot?.hardware) return [];
  return Object.entries(snapshot.hardware).map(([key, value]) => ({
    title: hardwareTitle(key),
    message: value?.message || "No signal",
    health: value?.healthy ? "good" : key === "camera" || key === "led" ? "warn" : "bad",
  }));
}

function hardwareTitle(key) {
  const map = {
    camera: "摄像头",
    audio: "音频输出",
    led: "LED 灯带",
    gpio: "GPIO",
    spi: "SPI 总线",
    i2c: "I2C 总线",
  };
  return map[key] || key;
}

function mapStatus(title, status) {
  return {
    title,
    message: status?.message || "No signal",
    health: status?.healthy ? "good" : status?.running ? "warn" : "bad",
  };
}

function formatUptime(value) {
  const seconds = Number(value || 0);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  return `${hours}h ${minutes}m ${secs}s`;
}

export default App;
