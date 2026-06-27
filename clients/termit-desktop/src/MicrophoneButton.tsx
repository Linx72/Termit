/**
 * MicrophoneButton — компонент голосового ввода TermitPro.
 *
 * Использует Web Audio API для захвата микрофона,
 * отправляет PCM 16kHz mono чанки в whisper.cpp через IPC,
 * показывает VU-meter и live-текст во время речи.
 */

import { useCallback, useEffect, useRef, useState } from "react";

// ── Типы ────────────────────────────────────────────────────

type MicState = "idle" | "checking" | "downloading" | "recording" | "processing";

interface MicrophoneButtonProps {
  onText: (text: string) => void;       // колбэк с финальным текстом
  onPartial?: (text: string) => void;   // частичный текст во время речи
  disabled?: boolean;
}

// ── Аудио-константы ─────────────────────────────────────────

const TARGET_SAMPLE_RATE = 16000;
const CHUNK_MS = 400; // отправляем аудио каждые 400ms

// ── Компонент ───────────────────────────────────────────────

export function MicrophoneButton({ onText, onPartial, disabled }: MicrophoneButtonProps) {
  const [state, setState] = useState<MicState>("idle");
  const [level, setLevel] = useState(0);         // 0–100 громкость
  const [partialText, setPartialText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const vuRafRef = useRef<number>(0);
  const chunksRef = useRef<Float32Array[]>([]);

  // ── VU-meter (анимация громкости) ───────────────────────

  const startVuMeter = useCallback((analyser: AnalyserNode) => {
    const data = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (let i = 0; i < data.length; i++) {
        const v = (data[i] - 128) / 128;
        sum += v * v;
      }
      const rms = Math.sqrt(sum / data.length);
      // Переводим в проценты (0–100)
      const pct = Math.min(100, Math.round(rms * 200));
      setLevel(pct);
      vuRafRef.current = requestAnimationFrame(tick);
    };
    vuRafRef.current = requestAnimationFrame(tick);
  }, []);

  const stopVuMeter = useCallback(() => {
    if (vuRafRef.current) {
      cancelAnimationFrame(vuRafRef.current);
      vuRafRef.current = 0;
    }
    setLevel(0);
  }, []);

  // ── Колбэк: каждый аудио-чанк → IPC ────────────────────

  const sendChunksLoop = useCallback(() => {
    // Раз в CHUNK_MS отправляем накопленные сэмплы в whisper
    const timer = setInterval(() => {
      const chunks = chunksRef.current;
      if (chunks.length === 0) return;

      // Объединяем все чанки
      let totalLen = 0;
      for (const c of chunks) totalLen += c.length;
      const combined = new Float32Array(totalLen);
      let offset = 0;
      for (const c of chunks) {
        combined.set(c, offset);
        offset += c.length;
      }
      chunksRef.current = [];

      // Float32 → Int16 PCM
      const int16 = new Int16Array(combined.length);
      for (let i = 0; i < combined.length; i++) {
        const s = Math.max(-1, Math.min(1, combined[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }

      const buf = int16.buffer.slice(0); // копия ArrayBuffer

      // Отправляем в main process
      const api = window.termitDesktop;
      if (api) {
        void api.whisperStream(buf).then((result) => {
          const text = result.partial || "";
          setPartialText((prev) => {
            // Обновляем только если текст длиннее (фикс для глюков)
            return text.length >= prev.length ? text : prev;
          });
          onPartial?.(text);
        });
      }
    }, CHUNK_MS);

    return timer;
  }, [onPartial]);

  // ── Начать запись ──────────────────────────────────────

  const startRecording = useCallback(async () => {
    setError(null);
    setPartialText("");
    chunksRef.current = [];

    try {
      // Шаг 1: Проверить модель
      setState("checking");
      const api = window.termitDesktop;
      const status = await api.whisperModelStatus();
      if (!status.ready) {
        setState("downloading");
        const dlResult = await api.whisperDownloadModel();
        if (!dlResult.ok) {
          throw new Error(`Model download failed: ${dlResult.message}`);
        }
      }

      // Шаг 2: Запустить whisper-cli (ждёт stdin)
      const startResult = await api.whisperStart({ language: "ru" });
      if (!startResult.ok) {
        throw new Error(startResult.message);
      }

      // Шаг 3: Захват микрофона
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: { ideal: TARGET_SAMPLE_RATE },
          channelCount: { ideal: 1 },
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;

      // Шаг 4: AudioContext
      const ctx = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE });
      ctxRef.current = ctx;

      const source = ctx.createMediaStreamSource(stream);
      sourceRef.current = source;

      // Analyser для VU-meter
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyserRef.current = analyser;
      source.connect(analyser);

      // ScriptProcessorNode для захвата PCM
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (event) => {
        const input = event.inputBuffer.getChannelData(0);
        // Копируем (getChannelData возвращает ссылку, которая переиспользуется)
        chunksRef.current.push(new Float32Array(input));
      };

      source.connect(processor);
      // Важно: processor должен быть куда-то подключён (spec)
      processor.connect(ctx.destination);

      // Шаг 5: Запустить VU-meter и отправку чанков
      startVuMeter(analyser);
      const chunkTimer = sendChunksLoop();

      // Сохраняем таймер для очистки
      (processor as any).__chunkTimer = chunkTimer;

      setState("recording");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setState("idle");
      await cleanupAudio();
    }
  }, [sendChunksLoop, startVuMeter]);

  // ── Очистка аудио ──────────────────────────────────────

  const cleanupAudio = useCallback(async () => {
    // Остановить VU-meter
    stopVuMeter();

    // Отключить processor
    if (processorRef.current) {
      const p = processorRef.current as any;
      if (p.__chunkTimer) {
        clearInterval(p.__chunkTimer);
        p.__chunkTimer = null;
      }
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    // Отключить source
    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }

    // Остановить MediaStream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }

    // Закрыть AudioContext
    if (ctxRef.current && ctxRef.current.state !== "closed") {
      await ctxRef.current.close();
      ctxRef.current = null;
    }

    analyserRef.current = null;
  }, [stopVuMeter]);

  // ── Остановить запись ──────────────────────────────────

  const stopRecording = useCallback(async () => {
    if (state !== "recording") return;

    setState("processing");
    await cleanupAudio();

    // Получить финальный текст от whisper
    try {
      const api = window.termitDesktop;
      const result = await api.whisperStop();
      const text = result.text?.trim() || "";
      if (text) {
        onText(text);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    }

    setState("idle");
    setPartialText("");
  }, [state, cleanupAudio, onText]);

  // ── Очистка при размонтировании ────────────────────────

  useEffect(() => {
    return () => {
      void cleanupAudio();
    };
  }, [cleanupAudio]);

  // ── Горячая клавиша: Ctrl+Shift+Space ──────────────────

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.code === "Space") {
        e.preventDefault();
        if (state === "recording") {
          void stopRecording();
        } else if (state === "idle") {
          void startRecording();
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [state, startRecording, stopRecording]);

  // ── Рендер ─────────────────────────────────────────────

  const isIdle = state === "idle";
  const isRec = state === "recording";
  const isProcessing = state === "processing" || state === "checking";
  const isDownloading = state === "downloading";

  return (
    <div className="microphone-wrapper" style={{ position: "relative", display: "inline-flex", alignItems: "center" }}>
      {/* VU-meter */}
      {isRec && (
        <div className="vu-meter" style={{
          width: 48,
          height: 4,
          background: "#333",
          borderRadius: 2,
          marginRight: 8,
          overflow: "hidden",
        }}>
          <div style={{
            width: `${level}%`,
            height: "100%",
            background: level > 70 ? "#f85149" : level > 30 ? "#d29922" : "#3fb950",
            transition: "width 60ms linear",
          }} />
        </div>
      )}

      {/* Кнопка */}
      <button
        type="button"
        className={`microphone-btn ${isRec ? "recording" : ""} ${isProcessing ? "processing" : ""}`}
        disabled={disabled || isProcessing || isDownloading}
        title={
          isIdle
            ? "Голосовой ввод (Ctrl+Shift+Space)"
            : isRec
              ? "Остановить запись"
              : isDownloading
                ? "Загрузка модели…"
                : "Обработка…"
        }
        onClick={() => {
          if (isRec) void stopRecording();
          else if (isIdle) void startRecording();
        }}
        style={{
          width: 36,
          height: 36,
          borderRadius: 18,
          border: "none",
          cursor: isProcessing || isDownloading ? "wait" : "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 18,
          background: isRec
            ? "#f85149"
            : isDownloading
              ? "#d29922"
              : "#30363d",
          color: "#fff",
          transition: "background 0.2s, transform 0.15s",
          transform: isRec ? "scale(1.1)" : "scale(1)",
          animation: isRec ? "mic-pulse 1.5s ease-in-out infinite" : "none",
          opacity: disabled ? 0.5 : 1,
        }}
      >
        {isDownloading ? "⏳" : isProcessing ? "⏳" : isRec ? "🔴" : "🎤"}
      </button>

      {/* Live-текст */}
      {isRec && partialText && (
        <div className="mic-live-text" style={{
          position: "absolute",
          left: 0,
          bottom: "100%",
          marginBottom: 4,
          background: "rgba(0,0,0,0.85)",
          color: "#8b949e",
          fontSize: 12,
          padding: "4px 10px",
          borderRadius: 6,
          whiteSpace: "nowrap",
          maxWidth: 320,
          overflow: "hidden",
          textOverflow: "ellipsis",
          pointerEvents: "none",
        }}>
          {partialText || "…"}
        </div>
      )}

      {/* Ошибка */}
      {error && (
        <div style={{
          position: "absolute",
          left: 0,
          bottom: "100%",
          marginBottom: 4,
          background: "rgba(248,81,73,0.9)",
          color: "#fff",
          fontSize: 11,
          padding: "4px 10px",
          borderRadius: 6,
          maxWidth: 280,
        }}>
          {error}
        </div>
      )}

      {/* CSS-анимации */}
      <style>{`
        @keyframes mic-pulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(248, 81, 73, 0.4); }
          50% { box-shadow: 0 0 0 8px rgba(248, 81, 73, 0); }
        }
      `}</style>
    </div>
  );
}
