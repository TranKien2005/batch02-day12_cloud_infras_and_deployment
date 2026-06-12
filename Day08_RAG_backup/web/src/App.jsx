import { useMemo, useState } from 'react'

const API_URL = import.meta.env.VITE_RAG_API_URL || 'http://127.0.0.1:8000'

const EXAMPLE_QUESTIONS = [
  'Hình phạt cho tội tàng trữ trái phép chất ma túy là gì?',
  'Luật phòng chống ma túy quy định gì về cai nghiện?',
  'Các bài báo nói gì về nghệ sĩ liên quan đến ma túy?',
]

const INITIAL_ASSISTANT = {
  role: 'assistant',
  content:
    'Xin chào! Mình là hệ thống RAG đa tác tử về pháp luật ma túy và tin tức liên quan. Hãy đặt câu hỏi, Supervisor sẽ điều phối các agent, truy xuất nguồn và trả lời kèm citation.',
  sources: [],
  retrievalSource: 'none',
  intent: 'general',
  graphRuntime: 'langgraph-supervisor',
  citationsOk: true,
  trace: [
    {
      name: 'Supervisor',
      role: 'A2A supervisor',
      status: 'ready',
      detail: 'Sẵn sàng nhận câu hỏi, lập kế hoạch và phân công cho các agent.',
    },
  ],
  a2aMessages: [],
  mcpTools: [],
}

function SourceCard({ source, index }) {
  const metadata = source.metadata || {}
  const title = metadata.source || metadata.path || `Nguồn ${index + 1}`

  return (
    <details className="source-card">
      <summary>
        <span>{title}</span>
        {typeof source.score === 'number' && <small>{source.score.toFixed(3)}</small>}
      </summary>
      <p>{source.content}</p>
      <div className="metadata">
        {source.source && <span>{source.source}</span>}
        {metadata.type && <span>{metadata.type}</span>}
        {metadata.path && <span>{metadata.path}</span>}
      </div>
    </details>
  )
}

function Message({ item }) {
  const isUser = item.role === 'user'
  return (
    <article className={`message ${isUser ? 'user' : 'assistant'}`}>
      <div className="bubble">
        <div className="role">{isUser ? 'Bạn' : 'Multi-Agent RAG'}</div>
        <div className="text">{item.content}</div>
        {!isUser && (
          <div className="badges">
            <span>{item.intent || 'general'}</span>
            <span>{item.graphRuntime || 'runtime'}</span>
            <span>{item.citationsOk ? 'citation ổn' : 'cần kiểm tra citation'}</span>
            {item.sources?.length > 0 && <span>{item.sources.length} nguồn</span>}
          </div>
        )}
      </div>

      {!isUser && item.sources?.length > 0 && (
        <div className="sources">
          <h3>Nguồn đã dùng</h3>
          {item.sources.map((source, index) => (
            <SourceCard key={`${source.metadata?.path || source.metadata?.source || index}-${index}`} source={source} index={index} />
          ))}
        </div>
      )}
    </article>
  )
}

function AgentPanel({ activeMessage }) {
  const trace = activeMessage?.trace || []
  const a2aMessages = activeMessage?.a2aMessages || []
  const mcpTools = activeMessage?.mcpTools || []

  return (
    <aside className="agent-panel">
      <section className="panel-section status-grid">
        <div>
          <span className="label">Runtime</span>
          <strong>{activeMessage?.graphRuntime || 'waiting'}</strong>
        </div>
        <div>
          <span className="label">Intent</span>
          <strong>{activeMessage?.intent || 'general'}</strong>
        </div>
        <div>
          <span className="label">Citation</span>
          <strong>{activeMessage?.citationsOk ? 'OK' : 'Review'}</strong>
        </div>
      </section>

      <section className="panel-section">
        <div className="panel-heading">
          <h2>Agent Flow</h2>
          <span>{trace.length} bước</span>
        </div>
        <div className="timeline">
          {trace.map((step, index) => (
            <div className="timeline-item" key={`${step.name}-${index}`}>
              <div className="timeline-dot" />
              <div>
                <strong>{step.name}</strong>
                <span>{step.role}</span>
                <p>{step.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="panel-section">
        <div className="panel-heading">
          <h2>MCP Tools</h2>
          <span>{mcpTools.length}</span>
        </div>
        {mcpTools.length === 0 ? (
          <p className="muted">Tool sẽ hiện sau lượt hỏi đầu tiên.</p>
        ) : (
          mcpTools.map((tool) => (
            <div className="tool-chip" key={tool.name}>
              <strong>{tool.name}</strong>
              <span>{tool.description}</span>
            </div>
          ))
        )}
      </section>

      <section className="panel-section">
        <div className="panel-heading">
          <h2>A2A Supervisor</h2>
          <span>{a2aMessages.length}</span>
        </div>
        <div className="a2a-list">
          {a2aMessages.slice(-4).map((message, index) => (
            <div className="a2a-item" key={`${message.sender}-${message.receiver}-${index}`}>
              <span>{message.sender} → {message.receiver}</span>
              <strong>{message.message_type || 'message'}: {message.task}</strong>
            </div>
          ))}
          {a2aMessages.length === 0 && <p className="muted">Chưa có message qua Supervisor.</p>}
        </div>
      </section>
    </aside>
  )
}

export default function App() {
  const [messages, setMessages] = useState([INITIAL_ASSISTANT])
  const [input, setInput] = useState('')
  const [topK, setTopK] = useState(5)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const activeAssistant = useMemo(
    () => [...messages].reverse().find((msg) => msg.role === 'assistant'),
    [messages],
  )
  const canSend = useMemo(() => input.trim().length > 0 && !loading, [input, loading])

  async function sendMessage(question = input) {
    const message = question.trim()
    if (!message || loading) return

    const chatHistory = messages
      .filter((msg) => msg.role === 'user' || msg.role === 'assistant')
      .map((msg) => ({ role: msg.role, content: msg.content }))

    setError('')
    setInput('')
    setLoading(true)
    setMessages((prev) => [...prev, { role: 'user', content: message }])

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, history: chatHistory, top_k: Number(topK) }),
      })

      if (!response.ok) {
        const detail = await response.text()
        throw new Error(detail || `HTTP ${response.status}`)
      }

      const data = await response.json()
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.answer || 'Không có câu trả lời.',
          sources: data.sources || [],
          retrievalSource: data.retrieval_source || 'none',
          intent: data.intent || 'general',
          graphRuntime: data.graph_runtime || 'unknown',
          citationsOk: Boolean(data.citations_ok),
          trace: data.trace || [],
          a2aMessages: data.a2a_messages || [],
          mcpTools: data.mcp_tools || [],
        },
      ])
    } catch (err) {
      setError(`Không gọi được backend tại ${API_URL}. Chi tiết: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  function handleSubmit(event) {
    event.preventDefault()
    sendMessage()
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Group Lab Upgrade</p>
          <h1>Drug Law Multi-Agent RAG</h1>
        </div>
        <div className="api-pill">API {API_URL}</div>
      </header>

      <section className="layout">
        <section className="workspace">
          <div className="examples">
            {EXAMPLE_QUESTIONS.map((question) => (
              <button key={question} type="button" onClick={() => sendMessage(question)} disabled={loading}>
                {question}
              </button>
            ))}
          </div>

          <section className="chat-panel">
            <div className="messages">
              {messages.map((message, index) => (
                <Message key={index} item={message} />
              ))}
              {loading && <div className="loading">Đang điều phối agent, truy xuất tài liệu và kiểm tra citation...</div>}
            </div>

            {error && <div className="error">{error}</div>}

            <form className="composer" onSubmit={handleSubmit}>
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Nhập câu hỏi của bạn..."
                rows={3}
              />
              <div className="controls">
                <label>
                  <span>top_k</span>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={topK}
                    onChange={(event) => setTopK(event.target.value)}
                  />
                </label>
                <button type="submit" disabled={!canSend}>{loading ? 'Đang gửi...' : 'Gửi câu hỏi'}</button>
              </div>
            </form>
          </section>
        </section>

        <AgentPanel activeMessage={activeAssistant} />
      </section>
    </main>
  )
}