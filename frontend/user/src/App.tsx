import { useEffect, useRef, useState } from "react";
import { Layout, Select, Button, Alert, Input, Spin, Typography, Avatar } from "antd";
import { SendOutlined, UserOutlined, RobotOutlined, ClearOutlined } from "@ant-design/icons";
import api, { extractErrorMessage } from "./api/client";
import type { Customer, ChatHistoryTurn } from "./types";

const { Sider, Content } = Layout;
const { Title, Text } = Typography;
const { TextArea } = Input;

export default function App() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [sidebarError, setSidebarError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | undefined>();

  const [history, setHistory] = useState<ChatHistoryTurn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .get<Customer[]>("/customers")
      .then((res) => {
        setCustomers(res.data);
        if (res.data.length > 0) setActiveId(res.data[0].customer_id);
        else setSidebarError("⚠️ Database is completely empty!");
      })
      .catch((err) => {
        setSidebarError(extractErrorMessage(err));
        setActiveId("CUST-101");
      });
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, sending]);

  const handleSend = async () => {
    const message = input.trim();
    if (!message || !activeId) return;

    const nextHistory: ChatHistoryTurn[] = [...history, { role: "user", content: message }];
    setHistory(nextHistory);
    setInput("");
    setSending(true);

    try {
      // Sending full prior history (not just the latest message) so the
      // agent has real multi-turn context - the original Streamlit app
      // always sent an empty history array here, which broke flows like
      // "file a complaint" -> "what category?" -> "billing" losing context
      // between turns.
      const res = await api.post("/chat", {
        customer_id: activeId,
        message,
        history,
      });
      const reply = res.data?.response ?? "No response.";
      setHistory([...nextHistory, { role: "assistant", content: reply }]);
    } catch (err) {
      setHistory([...nextHistory, { role: "assistant", content: `Error: ${extractErrorMessage(err)}` }]);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <Layout className="min-h-screen">
      <Sider width={300} theme="light" className="border-r border-gray-200 p-4">
        <Title level={5}>🔑 Customer Workspace Login</Title>

        {sidebarError && <Alert type="error" showIcon message={sidebarError} className="mb-3 text-xs" />}

        <Select
          className="w-full mb-3"
          value={activeId}
          onChange={setActiveId}
          placeholder="Select Active Account Profile"
          options={customers.map((c) => ({
            value: c.customer_id,
            label: `${c.customer_id} (${c.name})`,
          }))}
        />

        {activeId && (
          <Alert
            type="info"
            showIcon
            message={
              <span>
                Connected as: <Text strong>{activeId}</Text>
              </span>
            }
            className="mb-3"
          />
        )}

        <Button
          icon={<ClearOutlined />}
          block
          onClick={() => setHistory([])}
          disabled={history.length === 0}
        >
          Clear History
        </Button>
      </Sider>

      <Layout>
        <div className="px-8 py-4 border-b border-gray-200 bg-white">
          <Title level={3} className="!mb-0">🤖 Telecom Agentic Support Hub</Title>
        </div>

        <Content className="flex flex-col bg-gray-50" style={{ height: "calc(100vh - 73px)" }}>
          <div className="flex-1 overflow-y-auto px-8 py-6 space-y-4">
            {history.length === 0 && (
              <div className="text-center text-gray-400 mt-20">
                How can I help you with your account today?
              </div>
            )}

            {history.map((msg, idx) => (
              <div
                key={idx}
                className={`flex items-start gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
              >
                <Avatar
                  icon={msg.role === "user" ? <UserOutlined /> : <RobotOutlined />}
                  className={msg.role === "user" ? "bg-blue-500" : "bg-gray-500"}
                />
                <div
                  className={`max-w-2xl rounded-lg px-4 py-3 whitespace-pre-wrap ${
                    msg.role === "user"
                      ? "bg-blue-500 text-white"
                      : "bg-white border border-gray-200 text-gray-800"
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}

            {sending && (
              <div className="flex items-center gap-3">
                <Avatar icon={<RobotOutlined />} className="bg-gray-500" />
                <div className="bg-white border border-gray-200 rounded-lg px-4 py-3">
                  <Spin size="small" /> <Text type="secondary" className="ml-2">Agent running checks...</Text>
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          <div className="border-t border-gray-200 bg-white px-8 py-4">
            <div className="flex gap-2 max-w-4xl mx-auto">
              <TextArea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="How can I help you with your account today?"
                autoSize={{ minRows: 1, maxRows: 4 }}
                disabled={!activeId || sending}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                disabled={!activeId || !input.trim()}
                loading={sending}
              >
                Send
              </Button>
            </div>
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}
